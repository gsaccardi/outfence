"""CLI entry points and POSIX workload lifecycle."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import uuid
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__, console
from .demo import Fixture, demo_requests
from .modeltap import ModelTap
from .policy import DEMO_POLICY, load_policy
from .provenance import Session
from .proxy import LoopbackHTTPServer, Proxy, Service, now
from .report import format_report, terminal_text, write_report


class Interrupted(Exception):
    pass


def interrupt(signum, frame):
    raise Interrupted()


def model_upstream(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
        or not parsed.port
        or parsed.username is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "--model-upstream must be a local model server, e.g. http://127.0.0.1:8080"
        )
    return ("127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname), parsed.port


def run_workload(cmd, proxy, timeout, extra_env=None):
    url = f"http://127.0.0.1:{proxy.server_port}"
    env = dict(os.environ)
    env.update({k: url for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")})
    env.update(NO_PROXY="", no_proxy="")
    env.update(extra_env or {})
    old_handler = signal.signal(signal.SIGTERM, interrupt)
    proc = None
    try:
        proc = subprocess.Popen(cmd, env=env, start_new_session=True)
        return proc.wait(timeout=timeout), False
    except (subprocess.TimeoutExpired, KeyboardInterrupt, Interrupted):
        print("Workload interrupted or timed out; stopping its process group.", file=sys.stderr)
        return None, True
    except OSError:
        print("Could not launch workload. Check the executable and permissions.", file=sys.stderr)
        return None, True
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        signal.signal(signal.SIGTERM, old_handler)


def parser():
    result = argparse.ArgumentParser(
        prog="outfence",
        description="Inspect proxy-routed connections. A local development tool, not a network sandbox.",
    )
    result.add_argument("--version", action="version", version=f"Outfence {__version__}")
    sub = result.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Write a deny-all policy (or --demo policy)")
    init.add_argument("path", nargs="?", default="outfence.json")
    init.add_argument("--demo", action="store_true")
    check = sub.add_parser("check", help="Validate a policy without making connections")
    check.add_argument("path")
    for name in ("demo", "run"):
        p = sub.add_parser(
            name,
            help="Run synthetic local requests" if name == "demo" else "Run a proxy-aware command",
        )
        p.add_argument("--policy", required=name == "run")
        p.add_argument("--mode", choices=["enforce", "observe"], default="enforce")
        p.add_argument("--output", help="New report directory; existing directories are refused")
        if name == "run":
            p.add_argument(
                "--timeout", type=int, default=60, help="Workload timeout in seconds (default: 60)"
            )
            p.add_argument(
                "--model-upstream",
                metavar="URL",
                help="Observe chat completions sent to this local OpenAI-compatible model server",
            )
            p.add_argument("workload", nargs=argparse.REMAINDER)
    return result


def notice(style, text, alarm=False):
    if style.enabled:
        text = "  " + style.paint(text, console.ACID if alarm else style.dim)
    print(text, flush=True)


def welcome(style):
    """A short menu for people who type `outfence` in a terminal with no arguments."""
    columns = shutil.get_terminal_size((80, 24)).columns
    print("\n".join(["", *console.banner(style, f"{__version__} alpha", columns), ""]))
    choices = [
        ("1", "Watch Outfence block a request: the offline demo"),
        ("2", "Run your agent through Outfence"),
        ("3", "Create a deny-all policy here (outfence.json)"),
        ("q", "Quit"),
    ]
    for key, text in choices:
        print(f"  {style.paint(key, console.ACID, bold=True)}  {text}")
    try:
        choice = input("\n  Choose 1, 2, 3 or q: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    if choice == "1":
        return main(["demo"])
    if choice == "3":
        return main(["init"])
    if choice == "2":
        print(
            "\n  Run any proxy-aware command against a policy:\n"
            "    outfence run --policy outfence.json -- python3 my_agent.py\n\n"
            "  Add your local model server to see who named each destination:\n"
            "    outfence run --policy outfence.json --model-upstream http://127.0.0.1:11434"
            " -- python3 my_agent.py\n"
        )
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv and sys.stdin.isatty() and sys.stdout.isatty():
        return welcome(console.detect(sys.stdout))
    args = parser().parse_args(argv)
    style = console.detect(sys.stdout)
    try:
        if args.command == "init":
            data = DEMO_POLICY if args.demo else {"version": 1, "allow": []}
            with Path(args.path).open("x", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.write("\n")
            print(f"Policy created: {args.path}")
            return 0
        if args.command == "check":
            policy = load_policy(args.path)
            sources = ", ".join(policy.get("allow_from", []))
            named = f"; also hosts named by: {sources}" if sources else ""
            print(f"Valid policy: {len(policy['allow'])} exact destination rules{named}")
            return 0
        if os.name != "posix":
            raise ValueError("This alpha supports macOS and Linux only.")
        policy = load_policy(args.policy) if args.policy else DEMO_POLICY
        upstream = None
        if args.command == "run":
            cmd = args.workload[1:] if args.workload[:1] == ["--"] else args.workload
            if not cmd or args.timeout < 1:
                raise ValueError("Provide a positive timeout and a command after --.")
            if args.model_upstream:
                upstream = model_upstream(args.model_upstream)
        output = (
            Path(args.output) if args.output else Path("runs") / ("run-" + uuid.uuid4().hex[:10])
        )
        # Validate/reserve the output before starting a potentially side-effectful command.
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        coverage = "proxy + model tap" if upstream else "proxy only"
        columns = shutil.get_terminal_size((80, 24)).columns
        honest = "Direct connections can bypass this proxy. No OS/container isolation."
        if style.enabled:
            status = f"{__version__} alpha | {args.mode} | {coverage}"
            print("\n".join(["", *console.banner(style, status, columns), ""]), flush=True)
        else:
            print(f"Outfence {__version__}, local proxy alpha, coverage: {coverage}", flush=True)
        notice(style, honest)
        if args.mode == "observe":
            notice(style, "OBSERVE: out-of-policy proxy requests may connect.", alarm=True)
        if policy.get("allow_from") and not upstream:
            notice(style, "allow_from needs --model-upstream; only exact allow rules apply.", True)
        live = console.Live(style, sys.stdout) if style.enabled else None
        started, incomplete, workload_exit, session = now(), False, 0, None
        if args.command == "demo":
            fixture = LoopbackHTTPServer(("127.0.0.1", 0), Fixture)
            fixture.received = []
            with Service(fixture):
                routes = {
                    (host, 80): fixture.server_address
                    for host in ("model.example", "retrieval.example", "telemetry.example")
                }
                announce = live.decision if live else None
                with Service(Proxy(policy, args.mode, routes, on_decision=announce)) as proxy:
                    try:
                        demo_requests(proxy.server_port)
                    except (OSError, KeyboardInterrupt):
                        incomplete = True
            print(
                f"  Fixture received {len(fixture.received)} connections (destination-side evidence)."
            )
        else:
            session = Session(on_change=live.change if live else None) if upstream else None
            announce = live.decision if live else None
            with (
                Service(ModelTap(upstream, session)) if upstream else nullcontext() as tap,
                Service(Proxy(policy, args.mode, session=session, on_decision=announce)) as proxy,
            ):
                env = {}
                if tap is not None:
                    base = f"http://127.0.0.1:{tap.server_port}/v1"
                    env = {"OPENAI_BASE_URL": base, "OUTFENCE_MODEL_URL": base}
                    notice(style, f"Model tap: {base} -> {args.model_upstream}")
                workload_exit, incomplete = run_workload(cmd, proxy, args.timeout, env)
        report = write_report(
            output,
            args.mode,
            policy,
            proxy.snapshot(),
            started,
            workload_exit,
            demo=args.command == "demo",
            incomplete=incomplete or proxy.incomplete or bool(session and session.errors),
            reserved=True,
            dropped_events=proxy.dropped_events,
            model_tap=session.summary() if session else None,
        )
        evidence = terminal_text((output / "report.json").resolve())
        if style.enabled:
            print(console.render(style, report, evidence, columns))
        else:
            print(format_report(report))
            print(f"JSON: {evidence}")
        return report["exit_code"]
    except (OSError, ValueError) as exc:
        print(f"Outfence setup error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

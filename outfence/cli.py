"""CLI entry points and POSIX workload lifecycle."""

import argparse
import json
import os
import signal
import subprocess
import sys
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .demo import Fixture, demo_requests
from .policy import DEMO_POLICY, load_policy
from .proxy import Proxy, Service, now
from .report import write_report


class Interrupted(Exception):
    pass


def interrupt(signum, frame):
    raise Interrupted()


def run_workload(cmd, proxy, timeout):
    url = f"http://127.0.0.1:{proxy.server_port}"
    env = dict(os.environ)
    env.update({k: url for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")})
    env.update(NO_PROXY="", no_proxy="")
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
            p.add_argument("workload", nargs=argparse.REMAINDER)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
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
            print(f"Valid policy: {len(policy['allow'])} exact destination rules")
            return 0
        if os.name != "posix":
            raise ValueError("This alpha supports macOS and Linux only.")
        policy = load_policy(args.policy) if args.policy else DEMO_POLICY
        if args.command == "run":
            cmd = args.workload[1:] if args.workload[:1] == ["--"] else args.workload
            if not cmd or args.timeout < 1:
                raise ValueError("Provide a positive timeout and a command after --.")
        output = (
            Path(args.output) if args.output else Path("runs") / ("run-" + uuid.uuid4().hex[:10])
        )
        # Validate/reserve the output before starting a potentially side-effectful command.
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        print(f"Outfence {__version__} · local proxy alpha · coverage: proxy only", flush=True)
        print("Direct connections can bypass this proxy. No OS/container isolation.", flush=True)
        if args.mode == "observe":
            print("OBSERVE: out-of-policy proxy requests may connect.", flush=True)
        started, incomplete, workload_exit = now(), False, 0
        if args.command == "demo":
            fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
            fixture.received = []
            with Service(fixture):
                routes = {
                    (host, 80): fixture.server_address
                    for host in ("model.example", "retrieval.example", "telemetry.example")
                }
                with Service(Proxy(policy, args.mode, routes)) as proxy:
                    try:
                        demo_requests(proxy.server_port)
                    except (OSError, KeyboardInterrupt):
                        incomplete = True
            print(
                f"  Fixture received {len(fixture.received)} connections (destination-side evidence)."
            )
        else:
            with Service(Proxy(policy, args.mode)) as proxy:
                workload_exit, incomplete = run_workload(cmd, proxy, args.timeout)
        report = write_report(
            output,
            args.mode,
            policy,
            proxy.snapshot(),
            started,
            workload_exit,
            demo=args.command == "demo",
            incomplete=incomplete or proxy.incomplete,
            reserved=True,
            dropped_events=proxy.dropped_events,
        )
        print(f"\nReport: {(output / 'report.html').resolve()}")
        print(f"JSON:   {(output / 'report.json').resolve()}")
        reasons = {
            0: "no observed proxy violations",
            2: "policy violation",
            3: "incomplete run or proxy failure",
            4: "workload failed",
        }
        print(f"Exit {report['exit_code']}: {reasons[report['exit_code']]}")
        return report["exit_code"]
    except (OSError, ValueError) as exc:
        print(f"Outfence setup error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

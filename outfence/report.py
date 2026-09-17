"""Terminal reporting and local JSON evidence."""

import json
import os
from pathlib import Path

from . import __version__
from .proxy import now


def write_report(
    directory,
    mode,
    policy,
    events,
    started,
    workload_exit,
    demo=False,
    incomplete=False,
    reserved=False,
    dropped_events=0,
):
    directory = Path(directory)
    if not reserved:
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    violations = any(e["action"] in ("blocked", "would_block") for e in events)
    proxy_failed = any(e["connection"] == "failed" for e in events)
    exit_code = 3 if incomplete or proxy_failed else 2 if violations else 4 if workload_exit else 0
    report = dict(
        schema_version="1",
        version=__version__,
        mode=mode,
        started_at=started,
        finished_at=now(),
        synthetic=demo,
        policy=policy,
        events=events,
        workload_exit_code=workload_exit,
        exit_code=exit_code,
        coverage={
            "status": "incomplete" if incomplete else "proxy_only",
            "dropped_events": dropped_events,
            "boundary": "requests routed through this local proxy",
            "limitations": [
                "Direct network connections bypass this proxy.",
                "No container or OS network isolation.",
                "CONNECT tunnels are opaque; contents and downstream activity are not inspected.",
                "Tool/process attribution is unavailable.",
            ],
        },
    )

    def save(name, value):
        p = directory / name
        with p.open("x", encoding="utf-8") as stream:
            os.chmod(p, 0o600)
            stream.write(value)

    save("report.json", json.dumps(report, indent=2) + "\n")

    return report


def terminal_text(value):
    """Keep metadata from injecting terminal controls or extra report lines."""
    return "".join(char if char.isprintable() else repr(char)[1:-1] for char in str(value))


def format_report(report):
    reasons = {
        0: "no observed proxy violations",
        2: "policy violation",
        3: "incomplete run or proxy failure",
        4: "workload failed",
    }
    events = report["events"]
    counts = {
        action: sum(e["action"] == action for e in events)
        for action in ("allowed", "blocked", "would_block")
    }
    lines = [
        "",
        "Outfence report",
        f"Mode: {report['mode']} | Coverage: {report['coverage']['status']}",
        f"Allowed: {counts['allowed']} | Blocked: {counts['blocked']} | Would block: {counts['would_block']}",
        "",
    ]
    if events:
        for event in events:
            host = event["host"] or "unknown"
            if ":" in host:
                host = f"[{host}]"
            destination = terminal_text(f"{host}:{event['port'] or '?'}")
            lines.append(f"{terminal_text(event['action']).upper():<12} {destination}")
            lines.append(
                f"  {terminal_text(event['reason'])} | {terminal_text(event['connection'])}"
            )
    else:
        lines.append(
            "No proxy requests observed. This does not prove there was no network activity."
        )
    lines.extend(
        [
            "",
            f"Exit {report['exit_code']}: {reasons[report['exit_code']]}",
            f"Workload exit: {report['workload_exit_code'] if report['workload_exit_code'] is not None else 'unavailable'}",
            "Task correctness: not evaluated.",
            f"Dropped events: {report['coverage']['dropped_events']}",
            "Direct connections bypass this proxy. Encrypted contents are not inspected.",
        ]
    )
    return "\n".join(lines)

"""Terminal reporting and local JSON evidence."""

import json
import os
from pathlib import Path

from . import __version__
from .proxy import now

ORIGIN_TEXT = {
    "user": "named by the user",
    "system": "named in the system prompt",
    "tool_definition": "named in a tool definition",
    "tool_output": "named in a tool result",
    "model": "named only by the model; the user, system prompt, tools and tool results never did",
    "unattributed": "never named in the model context (a fixed tool endpoint or another process)",
}
EXIT_REASONS = {
    0: "no observed proxy violations",
    2: "policy violation",
    3: "incomplete run or proxy failure",
    4: "workload failed",
}


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
    model_tap=None,
):
    directory = Path(directory)
    if not reserved:
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    violations = any(e["action"] in ("blocked", "would_block") for e in events)
    proxy_failed = any(e["connection"] == "failed" for e in events)
    exit_code = 3 if incomplete or proxy_failed else 2 if violations else 4 if workload_exit else 0
    limitations = [
        "Direct network connections bypass this proxy.",
        "No container or OS network isolation.",
        "CONNECT tunnels are opaque; contents and downstream activity are not inspected.",
    ]
    if model_tap is None:
        limitations.append("Tool/process attribution is unavailable.")
    else:
        limitations += [
            "Only non-streaming chat completions sent through the model tap are observed.",
            "Provenance matches host names in chat text and trusts the harness's message roles.",
            "Tool attribution is inferred from tool-call arguments; it is not authenticated.",
        ]
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
        model_tap=model_tap,
        coverage={
            "status": "incomplete" if incomplete else "proxy_only",
            "dropped_events": dropped_events,
            "boundary": "requests routed through this local proxy",
            "provenance": "unavailable" if model_tap is None else "model_tap",
            "limitations": limitations,
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


def explain(event):
    """Provenance lines for one event; empty when the model tap was not used."""
    origin = event.get("origin")
    if not origin:
        return []
    lines = [f"  origin: {ORIGIN_TEXT.get(origin, terminal_text(origin))}"]
    if event.get("tool"):
        lines.append(f"  tool call: {terminal_text(event['tool'])}")
    trigger = event.get("trigger")
    # Tools offered from the first request are no change to correlate; JSON keeps at_start.
    if origin == "model" and event["action"] != "allowed" and trigger and not trigger["at_start"]:
        label = "MCP server" if trigger["servers"] else "tools"
        source = ", ".join(trigger["servers"] or trigger["tools"])
        lines.append(
            f"  trigger?: {label} {terminal_text(source)} appeared "
            f"{trigger['seconds_before']:g} s before this request"
        )
    return lines


def format_report(report):
    reasons = EXIT_REASONS
    events = report["events"]
    counts = {
        action: sum(e["action"] == action for e in events)
        for action in ("allowed", "blocked", "would_block")
    }
    lines = [
        "",
        "Outfence report",
        f"Mode: {report['mode']} | Coverage: {report['coverage']['status']}"
        f" | Provenance: {report['coverage'].get('provenance', 'unavailable')}",
        f"Allowed: {counts['allowed']} | Blocked: {counts['blocked']} | Would block: {counts['would_block']}",
        "",
    ]
    tap = report.get("model_tap")
    if tap is not None:
        lines.append(
            f"Model tap: {tap['requests']} chat requests | {len(tap['tool_calls'])} tool calls"
            f" | {tap['rejected']} rejected | {tap['errors']} errors"
        )
        for change in tap["environment"]:
            names = [f"+{n}" for n in change["added"]] + [f"-{n}" for n in change["removed"]]
            if names:
                when = terminal_text(change["time"][11:19])
                lines.append(f"  {when} UTC tools {terminal_text(' '.join(names))}")
        lines.append("")
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
            lines.extend(explain(event))
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

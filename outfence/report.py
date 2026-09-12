"""Offline report serialization; no external assets or telemetry."""

import html
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

    def esc(value):
        return html.escape(str(value))

    rows = (
        "".join(
            f"<tr><td><span class='{esc(e['action'])}'>{esc(e['action'].upper())}</span></td><td>{esc(e['host'] or 'unknown')}:{esc(e['port'] or '?')}</td><td>{esc(e['reason'])}</td><td>{esc(e['connection'])}</td></tr>"
            for e in events
        )
        or '<tr><td colspan="4">No proxy requests observed. The workload may not use this proxy.</td></tr>'
    )
    counts = {
        k: sum(e["action"] == k for e in events) for k in ("allowed", "blocked", "would_block")
    }
    title = (
        "Incomplete run"
        if incomplete
        else "Proxy connection failure"
        if proxy_failed
        else "Workload failed"
        if workload_exit
        else "Policy violations observed"
        if violations
        else "No proxy policy violations observed"
    )
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>Outfence · Run report</title><style>
body{background:#f7f5ef;color:#102b2a;font:16px Arial,sans-serif;margin:0}main{max-width:1000px;margin:64px auto;padding:0 28px}header{background:#102b2a;color:#f7f5ef;padding:30px;border-radius:16px}h1{font-size:36px;margin-bottom:12px}small{color:#a6f0cd}.notice{border-left:4px solid #865500;padding:16px;background:#eee9dd;margin:24px 0;line-height:1.6}.stats{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}.stat{min-width:140px;background:white;padding:24px;flex:1;border-radius:12px}.stat b{display:block;font-size:36px;margin-bottom:8px}.table{overflow:auto}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:18px 12px;border-bottom:1px solid #d6ddd5}th{font-size:12px;text-transform:uppercase}.allowed{color:#17664d}.blocked{color:#a43135}.would_block{color:#865500}pre{white-space:pre-wrap;background:#e8ece4;padding:24px;border-radius:12px}footer{margin:32px 0;color:#526563;line-height:1.6}</style><main>"""
    page += f"<header><small>OUTFENCE / LOCAL PROXY ALPHA</small><h1>{title}</h1><p>{esc(mode.upper())} · {'Synthetic local demo' if demo else 'Proxy-aware workload'}</p></header>"
    page += '<div class="notice"><strong>Coverage: proxy only. This is not a network sandbox.</strong><br>Direct connections can bypass these rules. An allowed destination can still receive sensitive data. This report is not a data-residency or compliance certificate.</div>'
    page += (
        '<div class="stats">'
        + "".join(
            f'<div class="stat"><b>{n}</b>{esc(k.replace("_", " "))}</div>'
            for k, n in counts.items()
        )
        + "</div>"
    )
    page += f'<h2>Connections</h2><div class="table"><table><tr><th>Decision</th><th>Destination</th><th>Reason</th><th>Connection</th></tr>{rows}</table></div><h2>Policy used</h2><pre>{esc(json.dumps(policy, indent=2))}</pre>'
    page += f"<footer>{esc(started)}<br>CLI exit: {exit_code} · Workload exit: {esc(workload_exit)}<br>No request payloads or headers stored. Tool attribution unavailable.</footer></main></html>"
    save("report.html", page)
    return report

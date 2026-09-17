# Report format - schema 1

Each run prints a terminal report and saves `report.json`. No HTML is generated. Schema 1 remains unchanged; no long-term schema stability promise is made yet.

The terminal lists decisions and destinations with reasons and connection status, plus counts, mode, coverage, dropped events, and both exit codes. It does not evaluate task correctness. Empty reports explicitly mean no proxy requests were observed, not that the workload had no network activity. Non-printable metadata is escaped before terminal display.

| Field | Meaning |
|---|---|
| schema_version | String `1` |
| version | Outfence package version |
| mode | enforce or observe |
| started_at / finished_at | UTC timestamps |
| synthetic | True only for the built-in demo |
| policy | Validated policy snapshot |
| events | Chronological proxy decisions in collector order |
| workload_exit_code | Original command exit code, or null on interruption/setup failure |
| exit_code | Outfence outcome, including failures/violations |
| coverage.status | proxy_only or incomplete; never complete host coverage |
| coverage.dropped_events | Count rejected by the event-storage cap |
| coverage.boundary / limitations | Explicit scope and exclusions |

Events contain time, host, port, transport (`http`, `connect`, or `unknown`), action (`allowed`, `blocked`, `would_block`), reason, connection (`not_attempted`, `established`, `failed`), and `tool` (null in this alpha). Malformed requests have unknown host/port to avoid leaking raw request input. `established` means a socket connected; it does not attest to a valid application response or successful agent task. HTTP forwarding failures may update it to failed.

Reasons include allowlist_match, not_in_allowlist, non_public_address, dns_failed, connection_failed, tunnel_idle_timeout, invalid_destination, and invalid_or_unsupported_request. A policy-allowed destination may subsequently fail or be blocked by the address check.

JSON contains metadata, not request content. Reports are not signed or protected from changes by the workload's user account.

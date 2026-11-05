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
| coverage.provenance | `model_tap` when `--model-upstream` was used, otherwise `unavailable` |
| coverage.boundary / limitations | Explicit scope and exclusions |
| model_tap | Null without `--model-upstream`. Otherwise: chat request/response counts, rejected and failed requests, tool-environment changes (tools added/removed, MCP servers parsed from `mcp__server__tool` names), and tool calls (name and destination hosts found in arguments) |

Events contain:

- time and host/port
- transport: `http`, `connect` or `unknown`
- action: `allowed`, `blocked` or `would_block`
- reason
- connection: `not_attempted`, `established` or `failed`
- origin, tool and trigger

Malformed requests have unknown host/port to avoid leaking raw request input. `established` means a socket connected; it does not attest to a valid application response or successful agent task. HTTP forwarding failures may update it to failed.

The last three fields are null without the model tap:

- **origin** is `user`, `system`, `tool_definition`, `tool_output`, `model` or `unattributed`.
- **tool** names the model tool call whose arguments named the host. It is inferred, not authenticated.
- **trigger** is set only for model-originated destinations. It is the most recent tool-environment change: its servers, its tools, `seconds_before` the decision, and `at_start`.

Reasons include:

- allowlist_match and not_in_allowlist
- allow_from_user, allow_from_system, allow_from_tool_definition and allow_from_tool_output
- model_originated
- non_public_address and dns_failed
- connection_failed and tunnel_idle_timeout
- invalid_destination and invalid_or_unsupported_request

A policy-allowed destination may subsequently fail or be blocked by the address check.

JSON contains metadata, not request content. The model tap keeps host names, tool names and counts, never prompts, answers or tool results. The terminal shows the same metadata. Reports are not signed or protected from changes by the workload's user account.

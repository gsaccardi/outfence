# Outfence — Product requirements

> Update: a smaller [local proxy prototype](PROTOTYPE.md) is now runnable. This document describes the future container-enforced product; its full requirements are not implemented.

Version 0.1 · 12 September 2026 · **Draft for PM validation**

Product owner: Giuseppe Saccardi. Technical drafting and implementation support: Codex. Approval of this document is separate from implementation and publication.

## 1. Product decision in one page

**Working name:** Outfence. **Promise:** Know where your agents connect.

**Problem hypothesis:** Small companies shipping AI agents struggle to answer customer questions about outbound connections. Existing logs are fragmented and network controls are difficult to connect to a reproducible agent run. This can delay deployment approval. We have not yet validated the frequency, severity, or willingness to pay.

**First user:** An engineer at an agent startup running Python workflows in Linux containers. **Internal champion:** Its CTO or platform lead. **Evidence consumer:** The startup's enterprise customer security reviewer. **Potential buyer:** The startup; buyer and budget remain unvalidated.

**Job:** “When a customer asks which services my agent contacts, help me reproduce a representative run, explain its outbound destinations, and demonstrate what happens when an unapproved destination is attempted.”

**First release:** A local CLI for one supported Linux container environment, explicit HTTP(S) destination policy, runtime boundary checks, local JSON/HTML evidence, and a synthetic demo. Tool-level attribution is an experiment, not a release promise.

**Commercial hypothesis:** Free local inspection and enforcement drive adoption; teams may pay for centrally managed policies, run history, and review workflows. No hosted backend is required for the MVP.

**Go/no-go:** Validate a recurring customer problem and prove that existing firewall tooling cannot meet it with simple configuration or a small upstream contribution. See [research](RESEARCH.md).

## 2. Goals and non-goals

Goals:

- Reach a useful, understandable first report in under 10 minutes on a prepared supported host.
- Capture allow/deny decisions for supported outbound connections made during a run, including subprocess traffic inside its boundary.
- Make policy violations, monitoring gaps, and agent failures distinct.
- Generate local evidence with exact policy, workload identity, version, run interval, and coverage.
- Work with an existing containerized workflow without a mandatory agent SDK.

Outside the MVP: native macOS/Windows enforcement, Kubernetes, arbitrary TCP/UDP workloads, browser-agent compatibility guarantees, TLS interception, content classification/DLP, per-user authorization, model quality evaluation, autonomous policy approval, geographic residency certification, production fleet management, and a hosted dashboard. The runner cannot control a remote tool server's own downstream connections.

## 3. Core workflow

1. **Prepare:** User supplies a prebuilt image and command. Dependency installation and image pulls happen before the measured run and are disclosed as outside coverage. The user opts into any costs incurred by their own workload.
2. **Check:** CLI validates runtime support, isolation, destination policy, and evidence output. If enforcement cannot be established, it refuses to start the workload.
3. **Observe:** User explicitly chooses observation mode for a synthetic or approved workload. Supported public HTTP(S) destinations may be reached; out-of-policy events are labeled `would_block`, never `blocked`. This mode can disclose workload data to external services.
4. **Review:** User inspects destinations and edits an allowlist. The tool may suggest entries but never silently approves them.
5. **Enforce:** User reruns the workload. Destinations not allowed by policy are denied before their upstream connection is established.
6. **Explain:** Report shows decisions, reasons, timestamps, identity evidence, and coverage. Unknown process/tool identity remains unknown.
7. **Share:** User chooses whether to share a reviewed report. The product never uploads it automatically.

No requirement says observation must precede enforcement. Users may start with an explicit restrictive policy.

## 4. Functional requirements

| ID | Priority | Requirement | Acceptance condition |
|---|---|---|---|
| FR-01 | P0 | Validate policy and supported runtime before launch | Invalid policy, host networking, unsupported runtime, or missing isolation returns setup failure and does not launch workload |
| FR-02 | P0 | Bind evidence to one workload run | Report records run ID, start/end, image digest, policy snapshot/hash, CLI/backend version, and exit state |
| FR-03 | P0 | Observe supported outbound attempts | Seeded HTTP(S) connections from main process and subprocess appear with destination, action, timestamp, and evidence source |
| FR-04 | P0 | Enforce an exact-host and port allowlist | Allowed synthetic service succeeds; denied service receives zero connections; redirects to a denied host are denied |
| FR-05 | P0 | Close direct network bypass paths | Controlled direct-IP, alternative DNS, IPv6, and UDP probes cannot bypass the supported boundary; unsupported transports are denied, not silently allowed |
| FR-06 | P0 | Distinguish observation from enforcement | Observation event says `would_block`; enforcement event says `blocked`; report always displays mode prominently |
| FR-07 | P0 | Export JSON and offline HTML | Both share a versioned data model; HTML uses no external scripts, fonts, analytics, or network resources |
| FR-08 | P0 | Report coverage and interruptions | Backend failure terminates/fences the workload, marks run incomplete, and cannot produce a clean pass |
| FR-09 | P0 | Support CI outcomes | Exit 0 = completed, no policy violations; 2 = policy violation; 3 = setup/coverage/internal failure; 4 = workload failure without higher-priority issue |
| FR-10 | P0 | Keep evidence local and minimal | No telemetry or automatic upload; no prompts, headers, request bodies, response bodies, full URLs, or environment values stored by default |
| FR-11 | P0 | Provide useful failure reasons | Invalid policy, denied destination, unsupported transport, and backend failure have distinct codes and next steps |
| FR-12 | P1 | Correlate an instrumented Python tool span | Optional adapter attaches a span only with explicit correlation evidence; concurrent ambiguous activity is reported as unknown |
| FR-13 | P1 | Compare two runs | Show added/removed destinations and changed policy decisions; never infer that unseen destinations cannot occur |

Outcome precedence: setup/coverage/internal failure (3), policy violation (2), workload failure (4), clean completion (0). Preserve the original workload exit code separately. In observation mode an out-of-policy attempt also produces exit 2, even though it was allowed through.

## 5. Policy contract proposal

See [example policy](../examples/outfence.yaml). This schema is a design proposal, not a supported API.

- Version required; unknown fields and ambiguous patterns are errors.
- MVP allows exact normalized DNS hostnames and explicit ports for HTTP(S). No wildcards or CIDR allow rules.
- Explicit enforcement mode is the default if omitted; observation must be selected deliberately.
- Default deny. Domain allow rules do not authorize private, loopback, link-local, or cloud metadata upstream addresses. Those destination classes are denied in the MVP even when DNS resolves to them.
- Workload DNS and outbound sockets must not bypass the controlled path. Client-supplied hostnames are checked; resolved addresses and every new upstream connection are checked too.
- A domain identifies a destination, not who ultimately owns, stores, or receives its data. An allowed external proxy could relay data elsewhere; the policy author must understand allowed services.
- Internal connections required for the runner are separate from external policy rules and disclosed in the report.

## 6. Report contract

Required top-level fields: `schema_version`, `run_id`, `mode`, `started_at`, `finished_at`, `workload`, `policy`, `runtime`, `coverage`, `summary`, `events`, `outcome`, `workload_exit_code`.

Each event includes time, destination host when available, IP when available, port, transport, action (`allowed`, `blocked`, `would_block`), rule/reason, evidence source, and optional process/tool identity with provenance. Raw socket denials may expose only IP/port. Never invent a hostname or causal attribution.

Coverage names the container boundary, capture method, supported protocols, exclusions, dropped event counts, and interruption state. `complete` means the declared collector was healthy for this run; it does not mean universal application coverage or proof against all attacks.

Default output excludes stdout/stderr capture because it may contain secrets. Hostnames themselves may be sensitive; tell users to review evidence before sharing. The proposed `report.json` example is synthetic.

## 7. Quality and security requirements

- No network access is needed to render or inspect saved reports.
- A clean run must never be reported if decision events are dropped or backend health is lost.
- Escape all untrusted values in HTML; no raw insertion of destinations, commands, or error strings.
- Store reports with owner-only access on supported POSIX hosts. Retention is user-managed initially.
- Do not mount the Docker socket, host credentials, or host filesystem into the workload. No privileged workload, host network, or network-admin capabilities.
- Restart/timeout/signal handling cleans up only resources created for that run.
- Proposed performance gate: median added proxy latency below 20 ms per request on a documented local synthetic benchmark of 1,000 sequential requests; publish baseline and p95 rather than extrapolating to real agent performance. Revise after feasibility data.

## 8. Release acceptance scenarios

| Scenario | Expected result |
|---|---|
| Main process and child request allowed fixture | Both succeed and decisions are present |
| Child requests disallowed fixture | Fixture receives no upstream connection; run exits 2 |
| Allowed fixture redirects to disallowed host | Second destination denied; event explains default-deny |
| Direct IP, alternate DNS, IPv6, UDP/QUIC bypass attempts | No unauthorized egress; unsupported pathways visibly denied |
| Allowlisted hostname resolves to private or metadata address | Connection denied by address-class rule |
| Backend dies or event stream loses records | Workload is stopped/fenced, report incomplete, exit 3 |
| Agent crashes after a policy violation | Exit 2; original workload status preserved |
| Observation reaches disallowed public HTTP(S) destination | Request may succeed; `would_block`, mode visible, exit 2 |
| Two simultaneous tool calls cannot be disambiguated | Attribution unknown, no guessed association |
| Sensitive canaries in headers/body/env and hostile HTML in metadata | Canaries absent from evidence; HTML safely escaped |

Security acceptance must verify received connections at controlled destinations, not just assert on the runner's own logs. Freeze the support matrix after the feasibility spike; unsupported hosts fail explicitly.

## 9. Validation and success measures

All values below are targets, not achieved results.

- Interview 10 relevant teams; at least 3 provide concrete examples of a delayed review or recurring manual network-evidence work.
- Recruit 3 design partners with a repeatable container workflow and an identified evidence consumer.
- At least 2 of 3 partners generate a useful report within 10 minutes on a prepared host without live maintainer assistance.
- At least 2 of 3 rerun Outfence in a second week or add it to CI.
- At least 2 evidence consumers say the report answers a specific review question previously handled manually; collect what is still missing.
- Seek 1 paid pilot or budget-backed commitment for a clearly scoped recurring need before building a hosted product. Measure willingness to pay without setting a fictional market price.

Pivot/contribute upstream if users are satisfied by existing firewall logs plus a small script, if agent attribution has no value, or if the need is one-off with no recurring buyer. Security adoption does not justify a separate company by itself.

## 10. Delivery sequence and dependencies

1. **Discovery:** Interviews, example evidence, competitive hands-on comparison. Gate: problem and evidence consumer confirmed.
2. **Feasibility:** Compare reusing GitHub AWF with a thin runner over existing container/proxy primitives. Prove bypass resistance, health behavior, and event completeness for one Linux environment. Gate: defensible support matrix and backend decision.
3. **Alpha:** CLI, versioned policy, report, synthetic fixtures, documented limitations. Gate: P0 scenarios pass.
4. **Partner trial:** Reproduce three real workflows, record activation time, report usefulness, and repeat usage. Gate: decide public alpha and paid pilot scope.
5. **Expansion only with evidence:** Tool attribution, report diffs, managed collaboration. Production enforcement needs additional hardening and operational work.

No calendar or engineering estimate is committed before the feasibility gate. Host-level networking privileges and access to a Linux test environment are implementation dependencies.

## 11. PM validation checklist

Record each as Approve / Change / Reject, with a short reason.

- [ ] D1 — Outfence name and visual direction; handle/name clearance still pending.
- [ ] D2 — First customer: agent startups answering enterprise security reviews.
- [ ] D3 — Initial job: reproducible destination evidence with enforceable policy.
- [ ] D4 — Linux containers and HTTP(S) only for the first supported release.
- [ ] D5 — Tool attribution is experimental; no universal data-flow claim.
- [ ] D6 — Local inspection and enforcement remain open source; Apache-2.0 proposed.
- [ ] D7 — Discovery and backend feasibility gates precede implementation scope commitment.
- [ ] D8 — Success and stop criteria in section 9.

Approval record: Pending. No product decisions have been approved by the PM yet.

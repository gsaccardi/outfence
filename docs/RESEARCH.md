# Research notes

Checked 12 September 2026. Sources establish existing capabilities, not customer demand or our differentiation. Company descriptions are vendor claims. This is an initial scan, not an exhaustive market or name clearance.

| Source | Observed relevance | Implication to validate |
|---|---|---|
| [GitHub Agentic Workflow Firewall](https://github.github.com/gh-aw-firewall/) | Existing agent execution and egress-control infrastructure | Direct overlap; compare/reuse before building |
| [GitHub network permissions](https://github.github.com/gh-aw/reference/network/) | Declarative network controls for agent workflows | An allowlist alone is insufficient differentiation |
| [Docker packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/) | Engine-managed networking and firewall behavior | Boundary design requires a tested runtime matrix |
| [Langfuse telemetry](https://langfuse.com/self-hosting/security/telemetry) | Self-hosted deployment telemetry is documented | External dependencies are broader than model calls; this is not evidence of a data leak |
| [Agentic Fabriq / YC](https://www.ycombinator.com/companies/agentic-fabriq) | Agent identity, permissioning, and audit positioning | Adjacent competition; avoid generic governance positioning |
| [Multifactor / YC](https://www.ycombinator.com/companies/multifactor) | Agent authentication, authorization, and auditing | Funding precedent, not evidence we will be funded |
| [Superagent / YC](https://www.ycombinator.com/companies/superagent) | Agent security and execution-boundary positioning | Significant adjacent/direct overlap to investigate |
| [Promptfoo agent evaluation](https://www.promptfoo.dev/docs/guides/evaluate-openai-agents-python/) | Tool trajectory evaluation | Compatibility doctor alternative also has existing competitors |

## Name scan

Working proposal: **Outfence**. Exact-name web searches for Outfence with AI/security/GitHub did not surface an obvious agent-security product in the returned results. The term exists as a legacy HP command, so it is not an invented unused word. Tracegate was rejected because multiple relevant software projects already use it. Egresslane was considered but is longer and more infrastructure-specific.

GitHub organization availability, package registries, domains, and trademark availability have not been verified or reserved. These remain pre-publication checks. No commercial clearance conclusion is implied.

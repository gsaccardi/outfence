# Technical feasibility and threat model

> Update: a smaller [local proxy prototype](PROTOTYPE.md) is now runnable. This document describes the future container-enforced product; its full requirements are not implemented.

Draft engineering proposal; no implementation or verified protection exists yet.

## Backend decision

First evaluate [GitHub Agentic Workflow Firewall](https://github.github.com/gh-aw-firewall/). It already targets isolated agent execution and network control. Compare its policy semantics, event exports, failure behavior, license obligations, and embedding experience against the PRD using the same fixtures. Prefer reuse or an upstream contribution if it meets the need. A new packet-filtering engine is not a default requirement.

Alternative to evaluate: a thin CLI starts a prebuilt workload in an isolated Linux network namespace. Only a controlled HTTP(S) proxy is reachable; the trusted controller establishes the network boundary before workload launch. The proxy validates exact hosts/ports and resolved address classes, logs decisions, and connects upstream. HTTPS uses CONNECT without payload decryption. A supervisor collects logs and exports evidence outside the workload.

A proxy environment variable alone is not enforcement: subprocesses can ignore it. Direct outbound routes, DNS, IPv6, alternate protocols, private destinations, and host interfaces require explicit treatment. Docker creates its own networking rules; backend selection and rule ordering must be tested against the supported engine version. See [Docker packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/) and [Docker security](https://docs.docker.com/engine/security/).

## Trust boundary

Trusted: host kernel, container runtime, privileged controller, policy file supplied by operator, evidence collector and output directory. Untrusted: model-generated actions, workload application, tool subprocesses, remote responses, and event strings. This is not protection against a compromised host or container escape.

Workloads receive no host Docker socket, host network, privileged mode, host credentials mount, or network-admin/raw-socket capability. Evidence is stored outside workload write access. Setup may need host privileges; the future CLI must document this accurately and perform a read-only prerequisite check first.

An allowlisted service can receive or relay data. This product cannot prevent all exfiltration through allowed destinations. It does not inspect encrypted content, resolve legal jurisdiction, or observe remote tool server internals. DNS names can encode information: unauthorized names must not be forwarded to arbitrary external resolvers.

## Attribution

P0: identify the run and observed destination/decision reliably. Per-process attribution is optional and requires reliable OS evidence. A proxy connection alone may not identify the originating child process. Tool attribution requires a correlated adapter or equivalent trustworthy context; timing alone is not proof. Adapter-provided labels are explanatory metadata, not an authorization boundary.

## Spike deliverables

- Pin one Linux/Docker/backend combination and publish all assumptions.
- Run allowed/denied HTTP and HTTPS, redirects, IP literals, IPv6, UDP, DNS tunneling, private address resolution, backend crash, and concurrent process fixtures.
- Check destination-side receipt and collector loss, not only internal verdicts.
- Determine how denials outside the proxy are recorded; distinguish an IP observation from a known hostname.
- Demonstrate cleanup and fail-closed behavior under supervisor/backend failure.
- Compare report usefulness with existing AWF output using design-partner review questions.
- Produce an ADR choosing reuse, thin integration, upstream contribution, or stop.

Product support claims and delivery estimates follow this spike.

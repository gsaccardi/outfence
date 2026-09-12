# Changelog

## 0.1.0a1 — first alpha candidate

### Added

- Installable Python package with the `outfence` console command and no runtime dependencies.
- `init`, `check`, `demo`, and `run` commands; JSON policy with exact host/port matching.
- Local synthetic demo, enforce/observe modes, HTTP GET forwarding and CONNECT tunnels.
- Offline HTML/JSON reports with policy snapshots, coverage limits, and workload outcomes.
- Apache-2.0 license, contributor guidance, security scope, CI and package smoke checks.

### Corrected from the initial prototype

- Demo policy no longer depends on a source-checkout file after installation.
- Invalid and unsupported requests are represented in evidence.
- Upstream failures return an HTTP error and cannot produce a clean CLI outcome.
- Output directories are reserved before workload launch; reports cannot be overwritten.
- Active connections close at shutdown and incomplete evidence is disclosed.
- Policies reject ambiguous values, duplicate rules and boolean versions/ports.

### Limits

Proxy-only coverage; no OS/container network isolation or tool attribution. macOS/Linux only. Initial source publication: github.com/gsaccardi/outfence. No package-registry release yet.

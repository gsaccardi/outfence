# Changelog

## Unreleased

- Add `outfence demo --backdoor`. A scripted stand-in for a backdoored model calls a destination nobody named once an MCP server appears, and the report shows the block, the origin and the trigger candidate. It runs offline and no real model is involved. `outfence` with no arguments lists it in the menu.
- Pass model calls through the proxy to the model tap. Clients that honor proxy settings send their chat completions to the proxy, which used to refuse them with 501, so `--model-upstream` saw nothing. Requests for the tap's own address are now passed on to it, as plain HTTP or through a tunnel. Every other loopback address stays blocked.
- Read a bare name with a common file extension as a file, not a host. `readme.md` and `install.sh` are valid domain names, so mentioning a file could authorize a host through `allow_from`. Only a URL names such a host now. This covers `ac`, `am`, `cc`, `md`, `mk`, `ml`, `mov`, `py`, `rs`, `sh`, `so`, `tf` and `zip`.
- Fix plain HTTP forwarding.
  - A URL with a query and no path now requests `/?query`, not `?query`.
  - The response keeps its `Content-Length`, and a body that ends early is recorded as a failed connection.
- Print "under 0.1 s" when a trigger candidate appeared less than a tenth of a second before the request. It used to print "0 s".
- Document that `example.com` and `www.example.com` count as the same name, and that all conversations in a run share one provenance record.
- Make the console test pass when `NO_COLOR` is set in the developer's environment.

## 0.1.0a3 - third alpha

- Attribute each destination to the source that named it first, and let `allow_from` grant a host only through a source that named it before the model did. A later message that repeats the model's words, such as a sub-agent's task or a conversation summary, no longer authorizes the destination. Events add `named_by`, the sources that named the host in order.

## 0.1.0a2 - second alpha, first PyPI release

- Publish releases to PyPI from GitHub Actions with Trusted Publishing, so no API token is stored. The release workflow runs the tests, requires the tag to match the package version, and smoke-tests the wheel.
- Use absolute links and images in the README, so the PyPI project page renders it.
- Show a real terminal recording of `outfence demo` in the README. It is an animated SVG made by `scripts/terminal_svg.py`, which uses the standard library only and replaces local paths before rendering.
- Add an interactive terminal look, using the standard library only.
  - The brand banner opens each run, and decisions print as they happen.
  - The styled report ends with the goose pose for the outcome.
  - `outfence` with no arguments shows a menu.
  - Plain output for pipes, files and CI is unchanged. `NO_COLOR`, `OUTFENCE_COLOR`, `OUTFENCE_THEME` and `OUTFENCE_GOOSE` control the styling.
- Add a model tap for local OpenAI-compatible servers (`run --model-upstream`) and destination provenance.
  - Each proxy decision records which source first named the host: the user, the system prompt, a tool definition, a tool result, or only the model.
  - Each decision also records the inferred tool call and, when the offered tools changed, a trigger candidate.
  - A new optional `allow_from` policy key permits hosts named by trusted sources. Model output never authorizes a destination.
  - The tap fails closed on unreadable answers and keeps no prompt or answer text.
- Add a minimal stdio MCP fetch server and an MCP agent-loop example, with deterministic tests and a provenance walkthrough.

- Replace generated HTML with terminal reports showing decisions, counts, coverage, and separate workload outcomes. Keep JSON evidence and existing exit codes.
- Move planning drafts and obsolete schema examples into ignored local notes; retain practical user documentation.

- Add a live Ollama/Qwen repository-research agent, with explicit proxied HTTPS tools, blocked/allowed policies, deterministic tests, and a reproducible walkthrough.

- Replace the arrow-based identity with a minimal, monochrome split-ring symbol.
- Skip reverse DNS during loopback server startup, preventing cold-process demo timeouts on macOS CI.
- Add a regression check for DNS-free server startup and actionable smoke-test timeout output.

## 0.1.0a1 - first alpha candidate

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

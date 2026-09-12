# CLI reference — 0.1.0a1

`outfence` and `python -m outfence` are equivalent. Run `--help` or `SUBCOMMAND --help` for argument details.

| Command | Behavior |
|---|---|
| `outfence --version` | Print version |
| `outfence init [path]` | Write deny-all JSON policy; defaults to outfence.json; refuses overwrite |
| `outfence init demo.json --demo` | Write the two-host synthetic demo policy |
| `outfence check path.json` | Validate policy without network access |
| `outfence demo` | Start local fixture and proxy; attempt three synthetic destinations; save reports |
| `outfence demo --mode observe` | Reach all three demo fixtures and label the third would-block |
| `outfence demo --policy path.json` | Try edited rules against the synthetic fixtures |
| `outfence run --policy path.json -- COMMAND ...` | Run a proxy-aware program; policy is required |

Both `demo` and `run` accept `--mode enforce|observe` (enforce by default) and `--output NEW_DIRECTORY`. `run` also accepts `--timeout SECONDS` (positive integer; default 60). Put all Outfence options before `--`. Command arguments after it go to your program. No shell expansion is performed by Outfence itself.

The default demo uses reserved `.example` names mapped internally to localhost. Other allowed/observed destinations in your own `run` may make real network requests. `init` starts with an empty allowlist; do not copy the demo policy into production expecting it to authorize a real provider.

## Policy

`version` must be integer 1. `allow` is an array of objects with exactly `host` and `port`. Host normalization accepts canonical IP literals or lowercase ASCII DNS labels. Domain matching is exact, not suffix-based; `api.example.com` does not include `example.com` or `other.api.example.com`. Ports are explicit. No wildcard, CIDR, protocol, custom resolver, or private-address override field is supported.

The prototype's old YAML file is historical and is not parsed. CONNECT and HTTP GET both use the same host/port rules; a rule does not restrict payload protocol or API paths.

## Outcomes and resource limits

Exit 3 (setup, proxy failure, incomplete) takes precedence over 2 (policy violation), then 4 (workload failure), then 0. Argument parser usage errors also use exit 2, as shown with usage text and no run report. An HTTP application response such as 404 is passed through; it is not itself a proxy transport failure. The client/workload decides whether to fail on it.

The proxy permits at most 32 concurrent client connections and records at most 10,000 events. Capacity rejection marks coverage incomplete; reaching the event limit rejects further requests. Socket operations time out after 10 seconds. A CONNECT tunnel with no traffic for 15 seconds closes and is recorded as a failure. Workload runtime is bounded separately by `--timeout`.

Shutdown interrupts unfinished proxy requests and reports incomplete coverage. A report may be absent after a catastrophic process/disk failure. Do not treat absence of an artifact as success in CI.

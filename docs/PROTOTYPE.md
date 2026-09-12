> Historical prototype note. For the current alpha, see [release notes](RELEASE.md) and [CLI reference](CLI.md).

# Runnable prototype 0.1

This iteration was requested after the PRD draft to provide something immediately runnable. Docker's daemon was unavailable on the development machine, so the prototype uses the Python standard library and temporary loopback services.

## Implemented

- `python3 -m outfence demo`: three synthetic hosts, actual proxy requests and fixture-side receipt counts.
- `python3 -m outfence run ... -- COMMAND`: environment-based proxy configuration for a POSIX child process, with timeout and ordinary process-group cleanup.
- Exact host/port JSON allowlist, enforce and explicit observe mode.
- HTTP GET forwarding; destination-controlled CONNECT tunnels for HTTPS clients.
- Public-address check outside the internal demo fixtures; upstream connections use a checked IP.
- Local HTML/JSON reports with escaped metadata, captured policy, coverage statement, and distinct exit codes.

## Not implemented

Container isolation, direct-egress blocking, complete DNS monitoring, arbitrary HTTP forwarding, tool attribution, replay, persistent daemon, production hardening, full PRD policy/report schemas, and reliable collector-loss detection. An active or malicious workload can bypass proxy settings. Local applications can connect to the unauthenticated loopback proxy. The report is an experience prototype, not compliance evidence.

The original PRD remains a future proposal. This iteration does not satisfy its P0 isolation or fail-closed requirements, and does not decide whether to reuse GitHub AWF.

## Next decision after user testing

Validate whether the allow/block experience and report are useful. Then choose one Linux runtime and compare an AWF integration with existing container/proxy primitives. Establish and test the execution boundary before making stronger security claims.

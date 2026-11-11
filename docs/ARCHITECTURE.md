# Architecture - local proxy alpha

The package uses only the Python standard library. Its modules separate CLI lifecycle, policy validation, proxy traffic handling, synthetic fixtures, and report generation.

```text
outfence run
  ├─ validate policy + reserve report directory
  ├─ start loopback proxy (+ optional model tap with --model-upstream)
  ├─ start child process with proxy environment variables (+ OPENAI_BASE_URL)
  │    ├─ chat completions → model tap → provenance session → local model server
  │    │    (sent directly, or to the proxy, which passes them on to the tap)
  │    └─ proxy-aware requests → destination rule / allow_from origin → public IP check → upstream
  ├─ wait for exit / timeout / interruption
  ├─ stop ordinary process group + proxy sockets
  └─ snapshot decisions → terminal report + local JSON

Direct workload connections ───────────────────────────────→ outside coverage
```

Modules:

- **`policy.py`** strictly validates the small JSON contract, including the optional `allow_from` sources.
- **`proxy.py`** implements HTTP GET and CONNECT.
  - Denied enforce-mode names are not resolved.
  - Permitted or observed destinations are resolved, checked, and connected using a checked IP.
  - Requests for the run's own model tap are passed on to it as they are. They are not egress, so they are neither decided nor recorded.
- **`modeltap.py`** forwards non-streaming chat completions to a loopback model server. It fails closed on content it cannot read.
- **`provenance.py`** reduces what the model saw and said to destination metadata:
  - which sources named each host
  - tool calls and the hosts in their arguments
  - changes in the offered tools

  It never keeps prompt or answer text.
- **`cli.py`** owns the child process group and output lifecycle.
- **`report.py`** serializes a snapshot after shutdown and explains provenance in the terminal.
- **`demo.py`** contains only synthetic services used by the demos and tests: a local fixture, and a scripted stand-in for a backdoored model with the small agent loop that drives it.
- **`core.py`** retains compatibility imports for the original prototype.

The proxy caps active connections and event storage, closes sockets at shutdown, and marks incomplete evidence on detected loss/interruption. These mechanisms improve diagnostic honesty, not containment: the workload can bypass the proxy or modify files under the same user account.

A supported network boundary is a future investigation. Today's package makes no container or firewall claim.

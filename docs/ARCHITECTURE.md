# Architecture - local proxy alpha

The package uses only the Python standard library. Its modules separate CLI lifecycle, policy validation, proxy traffic handling, synthetic fixtures, and report generation.

```text
outfence run
  ├─ validate policy + reserve report directory
  ├─ start loopback proxy
  ├─ start child process with proxy environment variables
  │    └─ proxy-aware requests → destination rule → public IP check → upstream
  ├─ wait for exit / timeout / interruption
  ├─ stop ordinary process group + proxy sockets
  └─ snapshot decisions → terminal report + local JSON

Direct workload connections ───────────────────────────────→ outside coverage
```

`policy.py` strictly validates the small JSON contract. `proxy.py` implements HTTP GET and CONNECT; denied enforce-mode names are not resolved. Permitted/observed destinations are resolved, checked, and connected using a checked IP. `cli.py` owns the child process group and output lifecycle. `report.py` serializes a snapshot after shutdown. `demo.py` contains only synthetic services used by the demo/tests. `core.py` retains compatibility imports for the original prototype.

The proxy caps active connections and event storage, closes sockets at shutdown, and marks incomplete evidence on detected loss/interruption. These mechanisms improve diagnostic honesty, not containment: the workload can bypass the proxy or modify files under the same user account.

A supported network boundary is a future investigation. Today's package makes no container or firewall claim.

# Security and coverage

Outfence 0.1.0a1 is an experimental **local forward proxy** for trusted development machines. It has not undergone an independent security audit. It is not a sandbox, a DLP system, or a production security boundary.

## What the alpha does

For requests routed through its loopback proxy, it checks exact destination host/port rules. In enforce mode, a disallowed host is rejected before DNS resolution or an upstream connection. In observe mode, such public destinations can be contacted and are labeled `would_block`.

Before an upstream connection it checks resolved IP addresses and rejects non-public/multicast destinations. It pins one checked address for the connection. This reduces accidental access to loopback/private/metadata services through the proxy; it is not protection against a hostile host or a relaying allowed service. Demo/test fixtures have explicit internal localhost mappings which users cannot set through a policy.

## Trust and bypasses

- The workload can ignore the proxy, use a raw socket, use another proxy, or create a detached process. Those actions are outside Outfence's control and reports.
- The host, user account, kernel, runtime, policy file, and evidence storage are trusted. The workload runs as the same user and can modify their writable files, including reports. Reports are not tamper-proof.
- The proxy is unauthenticated and binds only to 127.0.0.1. Other local processes can use it while it is active. Do not expose it via port forwarding or on shared untrusted machines.
- An allowed destination can receive sensitive information or relay it elsewhere. CONNECT tunnels are opaque and can carry arbitrary TCP bytes; they are not confined to valid TLS or a particular API operation.
- Allowed/observed hostname lookups use the host resolver. DNS metadata, tunneling via allowed services, IPv6/direct traffic outside the proxy, and remote tool downstream calls are not comprehensively controlled.
- Labels identify a proxy run, not the tool or process responsible for a request.

## Failure behavior

The proxy caps concurrent connections at 32 and retained events at 10,000. Capacity rejection or event loss marks coverage incomplete. Once the event cap is reached, new destination requests are rejected. Shutdown closes active sockets; unfinished handlers mark the run incomplete. Resolver calls can remain blocked in daemon threads, but new upstream connections are refused after shutdown begins. These are development safeguards, not a complete fail-closed system: the workload can still bypass the proxy directly.

Socket operations have a 10-second timeout; CONNECT has a 15-second idle timeout. The runner handles its workload timeout, Ctrl-C, and SIGTERM by stopping its ordinary process group. SIGKILL, host crashes, abrupt interpreter exit, output-disk failures, and other catastrophic failures can leave no complete report. A missing report is never evidence of success.

## Data handling

No product telemetry, automatic uploads, TLS decryption, or payload logging. Reports retain hostnames, ports, timestamps, policy, decisions, connection status, and limits. Hostnames themselves can be confidential. Workload output goes to the terminal and is not captured in reports. Output files use owner-only permissions; the same user can still alter them. Keep production data out of public issues.

## Reporting a vulnerability

Private vulnerability reporting is enabled at [gsaccardi/outfence](https://github.com/gsaccardi/outfence/security). Use **Security → Report a vulnerability**. That is the preferred route for sensitive reproductions; do not file a public issue containing an exploit, credentials, or customer traces.

If the private option is unavailable, open a public issue only asking the maintainer to enable a private reporting channel, without technical exploit details. No monitored security email address has been established yet. Only the latest alpha is maintained; there is no response-time SLA.

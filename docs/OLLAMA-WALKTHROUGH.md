# A real agent: local Qwen + GitHub research tools

This example runs a real tool-calling model through Ollama. The model decides to invoke two read-only tools, consumes their results, and writes a short explanation of Outfence. Tool traffic uses Outfence's proxy; inference stays on localhost and is **outside the proxy report**.

No paid API key is required. The live tools read public GitHub endpoints and require internet access. This differs from the fully offline synthetic `outfence demo`.

## Prerequisites

- A source checkout of this repository and Python 3.10+ on macOS/Linux.
- A running [Ollama installation](https://docs.ollama.com/quickstart) with a local tool-capable model.
- This walkthrough was exercised with an already installed `qwen2.5:7b` model (digest prefix `845dbda0ea48`).

Check your installed models:

```sh
ollama list
```

If necessary, install a model yourself with `ollama pull qwen2.5:7b` (a multi-gigabyte download). Start `ollama serve` if the service is not already running. The example never downloads a model automatically. It connects to `127.0.0.1:11434`; cloud inference is not needed.

## 1. Allow metadata, block the README

From the repository root:

```sh
python3 -m outfence run \
  --policy examples/ollama-policy.json \
  --timeout 300 \
  -- python3 examples/ollama_agent.py --model qwen2.5:7b
```

The model receives two tool definitions. Both have one validated `repo_name` argument fixed to `gsaccardi/outfence`:

| Tool | Fixed destination | Initial policy |
|---|---|---|
| repository_info | api.github.com:443 | Allowed |
| read_readme | raw.githubusercontent.com:443 | Blocked |

Typical terminal sequence:

```text
Model turn 1 · local inference (outside proxy coverage)
Tool repository_info · received data
Tool read_readme · failed; see proxy report
Model turn 2 · local inference (outside proxy coverage)
Agent answer: ...
Exit 2: policy violation
```

The exact answer and tool-call order can vary by model. The agent treats a failed tool as a result to explain; it can finish with workload exit 0 while Outfence returns **2** for the denied connection. In the report, the README destination should show `blocked / not_in_allowlist / not_attempted`.

Open the printed `report.html` path in your browser, or inspect `report.json` for exact events. The example does not automatically publish reports or upload model prompts.

## 2. Allow both tools

```sh
python3 -m outfence run \
  --policy examples/ollama-policy-allow-readme.json \
  --timeout 300 \
  -- python3 examples/ollama_agent.py --model qwen2.5:7b
```

Both tools should return data, and Outfence should exit **0** if there are no transport or model failures. Each run gets a fresh directory so the two policy snapshots and outcomes remain available.

Optionally repeat the first policy with `--mode observe`: the README request can proceed, but its decision is `would_block`, producing exit 2. Observe mode does not prevent the request.

## What is observed, blocked, or missed?

| Activity | Coverage |
|---|---|
| HTTPS connection for repository metadata | Observed; checked against the host/port allowlist |
| HTTPS connection for README | Blocked in the first run, allowed in the second |
| Local HTTP POST to Ollama | Deliberately direct; absent from Outfence's report |
| TLS payload, model messages, tool results | Not inspected or stored in the report |
| Tool name responsible for each connection | Printed by the example; not authenticated/attributed by Outfence |
| Any other program's direct traffic | Outside coverage |

The inference client explicitly uses a direct localhost HTTP connection because the alpha does not support plain HTTP POST forwarding and rejects non-public proxy destinations. This is a disclosed coverage gap, not an exception added to the public network policy. The two HTTPS tools explicitly establish a tunnel through the loopback proxy and keep normal certificate/hostname validation enabled.

The model cannot choose arbitrary URLs, paths, headers, credentials, or executable code: the tool dispatcher maps known names to fixed repository endpoints. Unknown tools, wrong arguments, repeated tool requests, and premature answers fail the example. Model calls are capped at four, each with a 120-second socket timeout; Outfence's overall 300-second timeout may stop the workflow earlier. Tool requests use a 20-second client timeout. Results are size-limited, and remote README text is treated as untrusted data.

## Verified results

Manually tested on 12 September 2026, macOS / Python 3.13, local `qwen2.5:7b`:

| Run | Metadata | README | Model calls | Workload exit | Outfence exit |
|---|---|---|---|---|---|
| Initial policy | allowed / established | blocked / not_attempted | 2 | 0 | 2 |
| Expanded policy | allowed / established | allowed / established | 2 | 0 | 0 |

These are actual model/tool runs, not scripted model responses. No API keys or downloads were used on that test machine. CI uses deterministic model-response fixtures and local proxy checks; it does not run a real model or call public GitHub endpoints. It verifies tool-result round trips, rejected model instructions, explicit proxy routing, and TLS verification configuration.

## Troubleshooting

- **Missing model / Ollama unavailable:** run `ollama list`, check that the server is listening on port 11434, and pass an installed model name. A missing model is reported; no automatic pull occurs.
- **Model rejects tools or invents arguments:** try the validated local Qwen model. The example fails rather than executing an unexpected request. A model answering without calling both tools is not counted as a successful walkthrough.
- **Tool says proxy_or_network_error:** inspect the Outfence report. A policy block is distinct from DNS/TLS/transport failure. The example does not label every network error as a block.
- **GitHub responds 403/429:** unauthenticated API rate limits can apply; retry later. This read-only example intentionally uses no token.
- **Answer contains an inaccurate claim:** model output is not a factual or security guarantee. Check tool data and the report. Only the synthetic demo is offline; the live GitHub tools require the internet.

The tool-call message flow follows [Ollama's tool-calling documentation](https://docs.ollama.com/capabilities/tool-calling) and its [chat API](https://docs.ollama.com/api/chat). No Ollama Python SDK or other runtime dependency is required.

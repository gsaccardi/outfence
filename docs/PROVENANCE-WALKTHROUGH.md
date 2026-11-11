# Where did this destination come from? Local model + MCP walkthrough

This example runs a small MCP agent with a local OpenAI-compatible model, through Outfence's **model tap**. The agent offers one MCP tool, `request_url`, from a minimal stdio server (`examples/fetch_mcp_server.py`). For every connection the tool makes, Outfence records which source first named the destination host:

- the user
- the system prompt
- a tool definition
- a tool result
- **only the model**

Why it matters: in November 2026, CERT-AGID published "La backdoor attende il suo turno". They showed an open-weight model fine-tuned to make an unrequested HTTPS call as soon as an MCP server with a specific name was connected. The answer stayed correct, and the call was visible only in tool logs. A destination that only the model named, right after a new server appeared, is that signature.

No API key is needed. The default example uses Ollama's OpenAI-compatible endpoint. The allowed fetch needs internet access.

No model at hand? `outfence demo --backdoor` shows that signature offline in a few seconds. It runs a scripted stand-in for a backdoored model through the same model tap and prints the same report.

## Prerequisites

- A source checkout of this repository and Python 3.10+ on macOS/Linux.
- A running Ollama with a local tool-capable model. This walkthrough was exercised with `qwen2.5:7b` (digest prefix `845dbda0ea48`). Any local server with `/v1/chat/completions` and tool calls works, such as mlx-lm, llama.cpp or vLLM; pass its address to `--model-upstream`.

The policy has no fixed rules. It only allows hosts that the user named:

```json
{"version": 1, "allow": [], "allow_from": ["user"]}
```

## 1. A host the user named is allowed

```sh
python3 -m outfence run --policy examples/provenance-policy.json \
  --model-upstream http://127.0.0.1:11434 --timeout 300 \
  -- python3 examples/mcp_agent.py --model qwen2.5:7b --server fetch-mcp \
     --question "Fetch https://example.com/ and summarize it."
```

The model calls `mcp__fetch-mcp__request_url` with the user's URL. The report shows:

```text
ALLOWED      example.com:443
  allow_from_user | established
  origin: named by the user
  tool call: mcp__fetch-mcp__request_url
```

## 2. A host only the model named is blocked

```sh
python3 -m outfence run --policy examples/provenance-policy.json \
  --model-upstream http://127.0.0.1:11434 --timeout 300 \
  -- python3 examples/mcp_agent.py --model qwen2.5:7b --server fetch-mcp \
     --question "Open the official Python documentation website and tell me its title."
```

The user named no host, so the URL the model picks from its own knowledge is `model_originated`. It is blocked before DNS resolution:

```text
BLOCKED      docs.python.org:443
  model_originated | not_attempted
  origin: named only by the model; the user, system prompt, tools and tool results never did
  tool call: mcp__fetch-mcp__request_url
```

Outfence makes no judgment about intent here: a helpful guess and a call-home look the same. The point is that no trusted source named this host. To permit such destinations, add exact `allow` rules.

## 3. A server that appears mid-session

```sh
python3 -m outfence run --policy examples/provenance-policy.json \
  --model-upstream http://127.0.0.1:11434 --timeout 300 \
  -- python3 examples/mcp_agent.py --model qwen2.5:7b --server quickfetch-mcp --connect-late
```

`--connect-late` asks "Why is the sky blue?" without tools, connects the MCP server, and asks again. A well-behaved model answers twice and makes no connection. The report lists the tool-environment change:

```text
Model tap: 2 chat requests | 0 tool calls | 0 rejected | 0 errors
  17:46:50 UTC tools +mcp__quickfetch-mcp__request_url

No proxy requests observed. This does not prove there was no network activity.
```

If a model fetched an unrequested destination after the change, the blocked event would end with a line like `trigger?: MCP server quickfetch-mcp appeared 1.3 s before this request`. `outfence demo --backdoor` and the deterministic tests reproduce this with a scripted model; see `outfence/demo.py` and `tests/test_provenance.py`.

## What is observed, decided or missed

| Activity | Coverage |
|---|---|
| Chat completions between the agent and the local model | Observed through the model tap; only host names, tool names and counts are kept |
| Destinations in the user, system, tool-definition, tool-result or model text | Matched as text; the source that named the host first is its origin. A host the model named first is never allowed through `allow_from`, even when a later message repeats it |
| HTTPS connections made by the MCP tool | Decided by exact rules, then `allow_from`; blocked before DNS when denied |
| Prompt, answer and tool-result text | Not stored in the report |
| Streaming responses, hosted model APIs, direct sockets | Outside coverage |
| Which process made a connection | Inferred from tool-call arguments, not authenticated |

The agent calls the tap directly over loopback, and the MCP server inherits the proxy settings. An agent whose HTTP client honors proxy settings reaches the tap through the proxy instead, which passes those calls on. Tool results are treated as untrusted data. The example fails safely on unknown tools and invalid arguments, and stops after four model calls.

## Verified results

These runs were tested manually on 5 November 2026 (macOS, Python 3.13, Ollama 0.40.13, local `qwen2.5:7b`):

| Run | Model calls | Tool calls | Decision | Workload exit | Outfence exit |
|---|---|---|---|---|---|
| 1. User names `https://example.com/` | 2 | 1 | `example.com:443` allowed / `allow_from_user` / established | 0 | 0 |
| 2. Model picks the Python docs URL | 2 | 1 | `docs.python.org:443` blocked / `model_originated` / not attempted | 0 | 2 |
| 3. `quickfetch-mcp` connected late | 2 | 0 | No proxy requests | 0 | 0 |

These are real model runs, and the exact wording and tool choices can vary by model. CI does not run a model or reach public endpoints. Its deterministic tests use a scripted model that calls home only when `mcp__quickfetch-mcp__request_url` is offered. They check origins, `allow_from`, trigger attribution, fail-closed handling, the MCP server round trip and an end-to-end `outfence run`.

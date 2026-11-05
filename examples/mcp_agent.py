"""Small MCP agent loop: a local OpenAI-compatible model plus stdio MCP servers.

Run through 'outfence run --model-upstream ...'; see docs/PROVENANCE-WALKTHROUGH.md.
Model requests use the Outfence model tap (OPENAI_BASE_URL) over a direct loopback
connection. MCP servers inherit the Outfence proxy settings. Standard library only.
"""

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit

SYSTEM = "You are a helpful assistant. Use a tool only when the user's request needs it."
SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_mcp_server.py")
TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
NAME = re.compile(r"[A-Za-z0-9_-]{1,40}")


class AgentError(Exception):
    """A bounded, user-facing example failure."""


class MCPServer:
    """One stdio MCP server process. Its tools are offered as mcp__<server>__<tool>."""

    def __init__(self, command):
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        self.counter = 0
        info = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "outfence-example-agent", "version": "0.1"},
            },
        )
        server_info = info.get("serverInfo")
        self.name = server_info.get("name") if isinstance(server_info, dict) else None
        if not isinstance(self.name, str) or not NAME.fullmatch(self.name):
            raise AgentError("The MCP server reported an invalid name.")
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = self.request("tools/list", {}).get("tools")
        self.tools = [
            t for t in tools or [] if isinstance(t, dict) and isinstance(t.get("name"), str)
        ]

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params):
        self.counter += 1
        self.send({"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params})
        while line := self.proc.stdout.readline():
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == self.counter:
                if not isinstance(message.get("result"), dict):
                    raise AgentError(f"MCP request {method} failed.")
                return message["result"]
        raise AgentError("The MCP server exited.")

    def call(self, tool, arguments):
        result = self.request("tools/call", {"name": tool, "arguments": arguments})
        parts = result.get("content") if isinstance(result.get("content"), list) else []
        return "\n".join(p["text"] for p in parts if isinstance(p, dict) and "text" in p)

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def chat(messages, tools, model=None):
    base = urlsplit(os.environ.get("OPENAI_BASE_URL", ""))
    if base.scheme != "http" or base.hostname != "127.0.0.1" or not base.port:
        raise AgentError("Run through 'outfence run --model-upstream ...' to use the model tap.")
    payload = {"messages": messages, "temperature": 0, "max_tokens": 600, "stream": False}
    if tools:
        payload["tools"] = tools
    if model:
        payload["model"] = model
    # Direct loopback call to the model tap, which forwards to the local model server.
    conn = http.client.HTTPConnection(base.hostname, base.port, timeout=300)
    try:
        path = base.path.rstrip("/") + "/chat/completions"
        conn.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
        response = conn.getresponse()
        body = response.read(4 * 1024 * 1024)
        if response.status != 200:
            raise AgentError(f"The model tap returned HTTP {response.status}.")
        message = json.loads(body)["choices"][0]["message"]
        if not isinstance(message, dict):
            raise ValueError()
        return message
    except (OSError, http.client.HTTPException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AgentError("Cannot read a model response through the model tap.") from exc
    finally:
        conn.close()


def tool_calls(message):
    """Return (id, name, arguments) from OpenAI tool_calls or Qwen-style <tool_call> text."""
    found = []
    raw_calls = message.get("tool_calls")
    for index, call in enumerate(raw_calls if isinstance(raw_calls, list) else []):
        function = call.get("function") if isinstance(call, dict) else None
        if isinstance(function, dict):
            found.append((call.get("id") or f"call_{index}", function))
    content = message.get("content")
    if not found and isinstance(content, str):
        for index, raw in enumerate(TOOL_CALL.findall(content)):
            try:
                found.append((f"call_{index}", json.loads(raw)))
            except ValueError:
                continue
    calls = []
    for ident, function in found:
        arguments = function.get("arguments") if isinstance(function, dict) else None
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = None
        calls.append((str(ident), function.get("name"), arguments))
    return calls


def run_agent(question, servers, chat=chat, model=None, limit=4, show=print):
    routes, tools = {}, []
    for server in servers:
        for tool in server.tools:
            name = f"mcp__{server.name}__{tool['name']}"
            routes[name] = (server, tool["name"])
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(tool.get("description", "")),
                        "parameters": tool.get("inputSchema") or {"type": "object"},
                    },
                }
            )
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for _ in range(limit):
        message = chat(messages, tools, model)
        calls = tool_calls(message)
        content = THINK.sub("", TOOL_CALL.sub("", message.get("content") or "")).strip()
        if not calls:
            if not content:
                raise AgentError("The model returned no answer.")
            return content
        messages.append(
            {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": i,
                        "type": "function",
                        "function": {"name": n, "arguments": json.dumps(a)},
                    }
                    for i, n, a in calls
                ],
            }
        )
        for ident, name, arguments in calls:
            if name in routes and isinstance(arguments, dict):
                server, tool = routes[name]
                result = server.call(tool, arguments)
            else:
                result = "Error: unknown tool or invalid arguments."
            summary = result.splitlines()[0] if result else "no result"
            show(f"  tool {name} {json.dumps(arguments)} -> {summary}")
            messages.append({"role": "tool", "tool_call_id": ident, "content": result})
    raise AgentError("Stopped at the model-call limit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="Why is the sky blue?")
    parser.add_argument(
        "--server",
        action="append",
        default=[],
        help="Start examples/fetch_mcp_server.py with this server name (repeatable)",
    )
    parser.add_argument(
        "--connect-late",
        action="store_true",
        help="Ask once without MCP servers, then connect them and ask the same question again",
    )
    parser.add_argument("--model", help="Model name to send, if the server needs one")
    args = parser.parse_args()
    servers = []
    try:
        for connected in [False, True] if args.connect_late else [True]:
            if connected:
                for name in args.server:
                    if not NAME.fullmatch(name):
                        raise AgentError("Use letters, digits, '-' or '_' for server names.")
                    print(f"\nConnecting MCP server {name}", flush=True)
                    servers.append(MCPServer([sys.executable, SERVER, "--name", name]))
            print(f"\nUser: {args.question}", flush=True)
            answer = run_agent(args.question, servers, model=args.model)
            print(f"Assistant: {answer}", flush=True)
        return 0
    except AgentError as exc:
        print(f"Agent example: {exc}", file=sys.stderr)
        return 1
    finally:
        for server in servers:
            server.close()


if __name__ == "__main__":
    raise SystemExit(main())

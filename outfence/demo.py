"""Synthetic services used only by demo and offline tests."""

import http.client
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from .proxy import LoopbackHTTPServer

# The backdoor demo: one MCP-style fetch tool, and the address a scripted model calls unasked.
FETCH = "mcp__quickfetch-mcp__request_url"
BEACON = "https://beacon.outfence.test/"
TOOL = {
    "type": "function",
    "function": {
        "name": FETCH,
        "description": "Perform an HTTP GET request to the given URL.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
    },
}
# Hosts the user named are allowed; the model's own output never authorizes a destination.
BACKDOOR_POLICY = {"version": 1, "allow": [], "allow_from": ["user"]}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.received.append(self.headers.get("Host"))
        body = b'{"ok":true,"fixture":"local synthetic service"}\n'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def demo_requests(port):
    statuses = []
    for host in ("model.example", "retrieval.example", "telemetry.example"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"http://{host}/demo")
        response = conn.getresponse()
        statuses.append(response.status)
        response.read()
        conn.close()
        print(f"  {host:24} HTTP {response.status}")
    return statuses


def tool_call(url, as_text=False):
    """A chat completion that calls the fetch tool, as OpenAI tool_calls or Qwen-style text."""
    arguments = {"url": url}
    if as_text:
        payload = json.dumps({"name": FETCH, "arguments": arguments})
        message = {"role": "assistant", "content": f"<tool_call>\n{payload}\n</tool_call>"}
    else:
        function = {"name": FETCH, "arguments": json.dumps(arguments)}
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_0", "type": "function", "function": function}],
        }
    return {"choices": [{"index": 0, "message": message}]}


def answer(text="Rayleigh scattering: air scatters blue light more than red."):
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]}


class ScriptedModel(BaseHTTPRequestHandler):
    """A rule-based stand-in for a backdoored model: it calls home when the trigger tool exists."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.received.append(body)
        names = [t["function"]["name"] for t in body.get("tools", [])]
        last = body["messages"][-1]["role"] if body["messages"] else None
        reply = tool_call(BEACON) if FETCH in names and last == "user" else answer()
        data = self.server.override or json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def scripted_model(override=None):
    server = LoopbackHTTPServer(("127.0.0.1", 0), ScriptedModel)
    server.received, server.override = [], override
    return server


def chat(tap_port, messages, tools):
    conn = http.client.HTTPConnection("127.0.0.1", tap_port, timeout=5)
    try:
        body = json.dumps({"messages": messages, "tools": tools})
        conn.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
        return json.loads(conn.getresponse().read())["choices"][0]["message"]
    except (http.client.HTTPException, ValueError, LookupError) as exc:
        raise OSError("The demo model gave no usable answer.") from exc
    finally:
        conn.close()


def fetch(proxy_port, url):
    """The demo's fetch tool: one request through a proxy tunnel, as an HTTPS client opens it."""
    parts = urlsplit(url)
    conn = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=5)
    conn.set_tunnel(parts.hostname, parts.port or 443)
    try:
        # No TLS inside the tunnel: in observe mode the other end is the plain local fixture.
        conn.request("GET", parts.path or "/")
        return f"HTTP {conn.getresponse().status}"
    except (OSError, http.client.HTTPException):
        return "request failed, see the report"
    finally:
        conn.close()


def backdoor_requests(tap_port, proxy_port):
    """The backdoor demo's agent: ask once without tools, connect the trigger server, ask again."""
    question = {"role": "user", "content": "Why is the sky blue?"}
    for tools in ([], [TOOL]):
        if tools:
            print("\nConnecting MCP server quickfetch-mcp", flush=True)
        print(f"\nUser: {question['content']}", flush=True)
        messages = [question]
        message = chat(tap_port, messages, tools)
        for call in message.get("tool_calls") or []:
            url = json.loads(call["function"]["arguments"])["url"]
            result = fetch(proxy_port, url)
            print(f"  tool request_url({json.dumps(url)}) -> {result}", flush=True)
            messages += [message, {"role": "tool", "tool_call_id": call["id"], "content": result}]
            message = chat(tap_port, messages, tools)
        print(f"Assistant: {message['content']}", flush=True)

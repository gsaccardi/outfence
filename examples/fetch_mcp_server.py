"""Minimal stdio MCP server with one tool, request_url, for Outfence examples.

The server name is a command-line option, so the same tool can be offered under different
names. Requests use the proxy from the environment, which 'outfence run' sets.
Standard library only.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PROTOCOL = "2025-06-18"
TOOL = {
    "name": "request_url",
    "description": "Perform an HTTP GET request to the given URL and return the status and body.",
    "inputSchema": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "An http or https URL"}},
        "required": ["url"],
        "additionalProperties": False,
    },
}


def log(name, message):
    print(f"[{time.strftime('%H:%M:%S')}] {name} | {message}", file=sys.stderr, flush=True)


def request_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "Error: only http and https URLs are supported."
    # build_opener() honors HTTP(S)_PROXY, so every request goes through Outfence.
    request = urllib.request.Request(url, headers={"User-Agent": "outfence-example"})
    try:
        with urllib.request.build_opener().open(request, timeout=15) as response:
            body = response.read(4001).decode("utf-8", errors="replace")
            return f"HTTP {response.status}\n{body[:4000]}"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except (OSError, ValueError) as exc:
        return f"Error: request failed ({type(exc).__name__}); check the Outfence report."


def handle(name, message):
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    method = message.get("method")
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": name, "version": "0.1"},
        }
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "tools/call" and params.get("name") == "request_url":
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        url = arguments.get("url") if isinstance(arguments.get("url"), str) else ""
        text = request_url(url)
        log(name, f"request_url({json.dumps(url)}) -> {text.splitlines()[0]}")
        return {"content": [{"type": "text", "text": text}], "isError": not text.startswith("HTTP")}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="fetch-mcp", help="Server name reported to clients")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.name):
        parser.error("Use 1-40 letters, digits, '-' or '_' for --name.")
    log(args.name, "MCP ready")
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if not isinstance(message, dict) or "id" not in message:
            continue  # Notifications need no reply.
        result = handle(args.name, message)
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        if result is None:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        else:
            reply["result"] = result
        print(json.dumps(reply), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

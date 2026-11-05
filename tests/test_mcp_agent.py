"""Deterministic MCP example tests: no model download or external network required."""

import json
import os
import sys
import unittest
from unittest.mock import patch

from examples.mcp_agent import SERVER, AgentError, MCPServer, chat, run_agent, tool_calls
from outfence.demo import Fixture
from outfence.proxy import LoopbackHTTPServer, Proxy, Service


class FakeServer:
    name = "fake-mcp"
    tools = [{"name": "request_url", "description": "Fetch a URL.", "inputSchema": {}}]

    def __init__(self):
        self.calls = []

    def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        return "HTTP 200\nok"


class AgentTests(unittest.TestCase):
    def test_tool_calls_from_openai_fields_and_qwen_text(self):
        openai = {
            "tool_calls": [
                {"id": "a", "function": {"name": "t", "arguments": '{"url": "https://x.test/"}'}}
            ]
        }
        qwen = {"content": '<tool_call>\n{"name": "t", "arguments": {"url": "u"}}\n</tool_call>'}
        self.assertEqual(tool_calls(openai), [("a", "t", {"url": "https://x.test/"})])
        self.assertEqual(tool_calls(qwen), [("call_0", "t", {"url": "u"})])
        self.assertEqual(
            tool_calls({"tool_calls": [{"function": {"name": "t", "arguments": "{"}}]}),
            [("call_0", "t", None)],
        )

    def test_namespaced_tool_is_dispatched_and_result_returned_to_model(self):
        server, seen = FakeServer(), []

        def fake_chat(messages, tools, model):
            seen.append((json.loads(json.dumps(messages)), tools))
            if len(seen) == 1:
                call = {
                    "name": "mcp__fake-mcp__request_url",
                    "arguments": {"url": "https://x.test/"},
                }
                return {"content": f"<tool_call>{json.dumps(call)}</tool_call>"}
            return {"content": "<think>\n\n</think>\n\nDone."}

        answer = run_agent("Fetch https://x.test/", [server], chat=fake_chat, show=lambda _: None)
        self.assertEqual(answer, "Done.")
        self.assertEqual(server.calls, [("request_url", {"url": "https://x.test/"})])
        self.assertEqual(seen[0][1][0]["function"]["name"], "mcp__fake-mcp__request_url")
        self.assertEqual(
            seen[1][0][-1], {"role": "tool", "tool_call_id": "call_0", "content": "HTTP 200\nok"}
        )

    def test_unknown_tool_is_not_dispatched(self):
        server = FakeServer()
        replies = iter(
            [
                {"tool_calls": [{"function": {"name": "run_shell", "arguments": "{}"}}]},
                {"content": "ok"},
            ]
        )
        run_agent("hi", [server], chat=lambda *_: next(replies), show=lambda _: None)
        self.assertEqual(server.calls, [])

    def test_model_calls_require_the_model_tap(self):
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://api.example.com/v1"}):
            with self.assertRaises(AgentError):
                chat([], [])


class MCPServerTests(unittest.TestCase):
    def test_server_round_trip_uses_the_outfence_proxy(self):
        fixture = LoopbackHTTPServer(("127.0.0.1", 0), Fixture)
        fixture.received = []
        policy = {"version": 1, "allow": [{"host": "news.example", "port": 80}]}
        routes = {("news.example", 80): fixture.server_address}
        with Service(fixture), Service(Proxy(policy, "enforce", routes)) as proxy:
            url = f"http://127.0.0.1:{proxy.server_port}"
            env = {k: url for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
            with patch.dict(os.environ, dict(env, NO_PROXY="", no_proxy="")):
                server = MCPServer([sys.executable, SERVER, "--name", "quickfetch-mcp"])
            try:
                self.assertEqual(server.name, "quickfetch-mcp")
                self.assertEqual([t["name"] for t in server.tools], ["request_url"])
                self.assertTrue(
                    server.call("request_url", {"url": "http://news.example/"}).startswith(
                        "HTTP 200"
                    )
                )
                blocked = server.call("request_url", {"url": "https://beacon.outfence.test/"})
                self.assertTrue(blocked.startswith("Error: request failed"))
            finally:
                server.close()
        self.assertEqual([e["action"] for e in proxy.events], ["allowed", "blocked"])
        self.assertEqual(len(fixture.received), 1)


if __name__ == "__main__":
    unittest.main()

"""Deterministic agent-loop tests: no model download or external network required."""

import copy
import json
import os
import unittest
from unittest.mock import patch

from examples.ollama_agent import AgentError, fetch_public, proxy_address, run_agent
from outfence.proxy import Proxy, Service


def tool_call(name, arguments=None):
    return {
        "function": {
            "name": name,
            "arguments": arguments
            if arguments is not None
            else {"repo_name": "gsaccardi/outfence"},
        }
    }


class AgentTests(unittest.TestCase):
    def test_model_tool_results_are_returned_before_final_answer(self):
        seen = []

        def chat(model, messages):
            seen.append(copy.deepcopy(messages))
            if len(seen) == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call("repository_info"), tool_call("read_readme")],
                }
            return {"role": "assistant", "content": "Metadata received; README unavailable."}

        fetches = []

        def fetch(name):
            fetches.append(name)
            return {"ok": name == "repository_info", "data": "synthetic"}

        result = run_agent(chat=chat, fetch=fetch)
        self.assertEqual(fetches, ["repository_info", "read_readme"])
        self.assertEqual(result["model_calls"], 2)
        tool_results = [m for m in seen[1] if m["role"] == "tool"]
        self.assertEqual([m["tool_name"] for m in tool_results], fetches)
        self.assertEqual([json.loads(m["content"])["ok"] for m in tool_results], [True, False])

    def test_unknown_or_malicious_tool_request_never_dispatches(self):
        calls = [
            tool_call("run_shell"),
            tool_call("read_readme", {"repo_name": "another/private-repo"}),
            tool_call(
                "read_readme",
                {"repo_name": "gsaccardi/outfence", "url": "https://attacker.example"},
            ),
            {"function": []},
            {"function": {"name": []}},
        ]
        for call in calls:
            with self.subTest(call=call), patch("examples.ollama_agent.fetch_public") as fetch:
                with self.assertRaises(AgentError):
                    run_agent(chat=lambda *_: {"tool_calls": [call]}, fetch=fetch)
                fetch.assert_not_called()

    def test_repeated_tool_is_not_executed_twice(self):
        with patch("examples.ollama_agent.fetch_public", return_value={"ok": True}) as fetch:
            with self.assertRaises(AgentError):
                run_agent(chat=lambda *_: {"tool_calls": [tool_call("read_readme")]}, fetch=fetch)
            self.assertEqual(fetch.call_count, 1)

    def test_premature_answer_is_not_reported_as_a_successful_agent_run(self):
        with self.assertRaises(AgentError):
            run_agent(chat=lambda *_: {"content": "I did not inspect anything."})

    def test_explicit_proxy_required(self):
        for url in ["", "http://example.com:8080", "http://user:pass@127.0.0.1:8080"]:
            with (
                self.subTest(url=url),
                patch.dict(os.environ, {"https_proxy": url, "HTTPS_PROXY": url}),
            ):
                with self.assertRaises(AgentError):
                    proxy_address()

    def test_real_tool_connect_is_denied_by_real_proxy(self):
        with Service(Proxy({"version": 1, "allow": []}, "enforce")) as proxy:
            with patch.dict(os.environ, {"https_proxy": f"http://127.0.0.1:{proxy.server_port}"}):
                result = fetch_public("read_readme")
        self.assertFalse(result["ok"])
        self.assertEqual(proxy.events[0]["host"], "raw.githubusercontent.com")
        self.assertEqual(proxy.events[0]["action"], "blocked")
        self.assertEqual(proxy.events[0]["connection"], "not_attempted")

    def test_tool_uses_fixed_target_and_keeps_tls_validation_enabled(self):
        with patch.dict(os.environ, {"https_proxy": "http://127.0.0.1:12345"}):
            with patch("examples.ollama_agent.http.client.HTTPSConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = 200
                response.read.return_value = b'{"full_name":"gsaccardi/outfence"}'
                result = fetch_public("repository_info")
                connection.return_value.set_tunnel.assert_called_once_with("api.github.com", 443)
                self.assertEqual(
                    connection.return_value.request.call_args.args[1], "/repos/gsaccardi/outfence"
                )
                context = connection.call_args.kwargs["context"]
                self.assertTrue(context.check_hostname)
                self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()

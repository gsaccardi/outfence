"""Model tap and destination provenance: deterministic, local, no model required."""

import http.client
import json
import socket
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from outfence.cli import main, model_upstream
from outfence.demo import Fixture
from outfence.modeltap import ModelTap
from outfence.policy import validate_policy
from outfence.provenance import Session, destinations
from outfence.proxy import LoopbackHTTPServer, Proxy, Service
from outfence.report import explain, format_report

FETCH = "mcp__quickfetch-mcp__request_url"
TOOL = {
    "type": "function",
    "function": {
        "name": FETCH,
        "description": "Perform an HTTP GET request to the given URL.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
    },
}


def tool_call(url, as_text=False):
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


def answer(text="Rayleigh scattering."):
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
        reply = (
            tool_call("https://beacon.outfence.test/")
            if FETCH in names and last == "user"
            else answer()
        )
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


class SessionTests(unittest.TestCase):
    def test_destinations_in_text(self):
        found = destinations(
            "See https://Example.com:8443/a, docs.python.org, 8.8.8.8 but not a_b.example"
        )
        self.assertIn(("example.com", 8443), found)
        self.assertIn(("docs.python.org", None), found)
        self.assertIn(("8.8.8.8", None), found)
        self.assertNotIn(("example.com", None), found)
        self.assertFalse([host for host, _ in found if host.endswith("b.example")])

    def test_origin_is_the_source_that_named_the_host_first(self):
        session = Session()
        session.observe_request(
            {
                "messages": [
                    {"role": "system", "content": "Docs live at docs.example.org"},
                    {"role": "user", "content": "Summarize https://news.example.com/today"},
                    {
                        "role": "tool",
                        "content": "Links: https://cdn.example.net/x news.example.com",
                    },
                    {"role": "narrator", "content": "unknown roles are data: odd.example"},
                    {"role": "user", "content": "Also open https://cdn.example.net/x"},
                ],
                "tools": [TOOL],
            }
        )
        session.observe_response(tool_call("https://beacon.outfence.test/"))
        expected = {
            "news.example.com": "user",
            "docs.example.org": "system",
            "cdn.example.net": "tool_output",
            "odd.example": "tool_output",
            "beacon.outfence.test": "model",
            "api.github.com": "unattributed",
        }
        for host, origin in expected.items():
            with self.subTest(host=host):
                self.assertEqual(session.check(host, 443, [])[0], origin)
        # Only the model's earlier mention cancels a grant; the user's own later one counts.
        self.assertEqual(session.check("cdn.example.net", 443, ["user"])[1], "user")

    def test_a_later_message_repeating_the_model_grants_nothing(self):
        # An orchestrator's answer becomes a sub-agent's task: the same words, now from the user.
        task = "Subtask: fetch https://beacon.outfence.test/ first."
        session = Session()
        session.observe_request({"messages": [{"role": "user", "content": "Read news.example"}]})
        session.observe_response(answer(f"{task} Then news.example."))
        session.observe_request({"messages": [{"role": "user", "content": task}]})
        origin, granted, details = session.check("beacon.outfence.test", 443, ["user"])
        self.assertEqual((origin, granted), ("model", None))
        self.assertEqual(details["named_by"], ["model", "user"])
        # The model repeating the user changes nothing.
        self.assertEqual(session.check("news.example", 443, ["user"])[:2], ("user", "user"))

    def test_allow_from_needs_a_matching_source_and_port(self):
        session = Session()
        session.observe_request(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Check http://example.com:8080/ and www.example.org",
                    }
                ]
            }
        )
        self.assertEqual(session.check("example.com", 8080, ["user"])[1], "user")
        self.assertIsNone(session.check("example.com", 443, ["user"])[1])
        self.assertEqual(session.check("example.org", 443, ["user"])[1], "user")
        self.assertIsNone(session.check("example.org", 22, ["user"])[1])
        self.assertIsNone(session.check("example.org", 443, ["tool_output"])[1])

    def test_new_mcp_server_is_the_trigger_candidate_and_content_is_not_kept(self):
        session = Session()
        question = {"messages": [{"role": "user", "content": "Why is the sky blue?"}]}
        session.observe_request(question)
        session.observe_response(answer())
        session.observe_request(dict(question, tools=[TOOL]))
        session.observe_response(tool_call("https://beacon.outfence.test/", as_text=True))
        origin, granted, details = session.check("beacon.outfence.test", 443, ["user"])
        self.assertEqual((origin, granted), ("model", None))
        self.assertEqual(details["tool"], FETCH)
        self.assertEqual(details["trigger"]["servers"], ["quickfetch-mcp"])
        self.assertFalse(details["trigger"]["at_start"])
        summary = session.summary()
        self.assertEqual((summary["requests"], summary["responses"]), (2, 2))
        self.assertEqual(summary["tool_calls"][0]["hosts"], ["beacon.outfence.test"])
        self.assertNotIn("sky", json.dumps(summary))
        self.assertNotIn("Rayleigh", json.dumps(summary))

    def test_policy_allow_from_is_strict(self):
        validate_policy({"version": 1, "allow": [], "allow_from": ["user", "tool_output"]})
        for value in [["model"], ["user", "user"], "user", [{"x": 1}], ["users"], None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_policy({"version": 1, "allow": [], "allow_from": value})

    def test_model_upstream_must_be_local(self):
        self.assertEqual(model_upstream("http://localhost:8080"), ("127.0.0.1", 8080))
        for value in [
            "https://127.0.0.1:8080",
            "http://example.com:8080",
            "http://127.0.0.1",
            "http://127.0.0.1:8080/v1",
            "http://user@127.0.0.1:8080",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                model_upstream(value)


class ProxyProvenanceTests(unittest.TestCase):
    def test_user_named_host_allowed_and_model_originated_host_blocked(self):
        fixture = LoopbackHTTPServer(("127.0.0.1", 0), Fixture)
        fixture.received = []
        session = Session()
        session.observe_request(
            {
                "messages": [{"role": "user", "content": "Read http://news.example/"}],
                "tools": [TOOL],
            }
        )
        session.observe_response(tool_call("https://beacon.outfence.test/"))
        policy = {"version": 1, "allow": [], "allow_from": ["user"]}
        routes = {("news.example", 80): fixture.server_address}
        with Service(fixture), Service(Proxy(policy, "enforce", routes, session=session)) as proxy:
            conn = http.client.HTTPConnection(*proxy.server_address, timeout=3)
            conn.request("GET", "http://news.example/")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            conn.close()
            with socket.create_connection(proxy.server_address) as raw:
                raw.sendall(b"CONNECT beacon.outfence.test:443 HTTP/1.0\r\n\r\n")
                self.assertIn(b"403", raw.recv(4096))
        allowed, blocked = proxy.events
        self.assertEqual(
            (allowed["action"], allowed["reason"], allowed["origin"]),
            ("allowed", "allow_from_user", "user"),
        )
        self.assertEqual(
            (blocked["action"], blocked["reason"], blocked["origin"]),
            ("blocked", "model_originated", "model"),
        )
        self.assertEqual((allowed["named_by"], blocked["named_by"]), (["user"], ["model"]))
        self.assertEqual(blocked["tool"], FETCH)
        self.assertEqual(blocked["connection"], "not_attempted")
        self.assertEqual(blocked["trigger"]["servers"], ["quickfetch-mcp"])
        self.assertTrue(blocked["trigger"]["at_start"])
        self.assertIsNone(allowed["trigger"])
        self.assertEqual(len(fixture.received), 1)

    def test_a_destination_the_model_named_first_stays_model_originated(self):
        task = "Subtask: fetch https://beacon.outfence.test/ first."
        session = Session()
        session.observe_response(answer(task))
        session.observe_request({"messages": [{"role": "user", "content": task}]})
        policy = {"version": 1, "allow": [], "allow_from": ["user"]}
        with Service(Proxy(policy, "enforce", session=session)) as proxy:
            proxy.destination("beacon.outfence.test", 443, "connect")
        (event,) = proxy.events
        self.assertEqual((event["action"], event["reason"]), ("blocked", "model_originated"))
        self.assertEqual(event["named_by"], ["model", "user"])
        text = "\n".join(explain(event))
        self.assertIn("origin: named first by the model, then repeated by the user", text)

    def test_without_a_session_decisions_and_events_are_unchanged(self):
        with Service(
            Proxy({"version": 1, "allow": [], "allow_from": ["user"]}, "enforce")
        ) as proxy:
            proxy.destination("example.invalid", 443, "connect")
        self.assertEqual(proxy.events[0]["reason"], "not_in_allowlist")
        self.assertIsNone(proxy.events[0]["origin"])
        self.assertIsNone(proxy.events[0]["named_by"])
        self.assertIsNone(proxy.events[0]["trigger"])


class ModelTapTests(unittest.TestCase):
    def post(self, tap, body):
        conn = http.client.HTTPConnection(*tap.server_address, timeout=3)
        conn.request("POST", "/v1/chat/completions", json.dumps(body))
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_tap_forwards_and_records_tool_calls(self):
        model, session = scripted_model(), Session()
        with Service(model), Service(ModelTap(model.server_address, session)) as tap:
            body = {"messages": [{"role": "user", "content": "Why?"}], "tools": [TOOL]}
            status, reply = self.post(tap, body)
        self.assertEqual(status, 200)
        self.assertEqual(reply, tool_call("https://beacon.outfence.test/"))
        self.assertEqual(model.received, [body])
        self.assertEqual(session.summary()["tool_calls"][0]["name"], FETCH)

    def test_streaming_and_unreadable_answers_are_refused(self):
        model, session = scripted_model(override=b"not json"), Session()
        with Service(model), Service(ModelTap(model.server_address, session)) as tap:
            stream = {"messages": [], "stream": True}
            self.assertEqual(self.post(tap, stream)[0], 400)
            self.assertEqual(model.received, [])
            self.assertEqual(self.post(tap, {"messages": []})[0], 502)
        summary = session.summary()
        self.assertEqual((summary["rejected"], summary["errors"]), (1, 1))


WORKLOAD = """
import http.client, json, os, socket, sys
from urllib.parse import urlsplit
base = urlsplit(os.environ["OPENAI_BASE_URL"])
def chat(tools):
    conn = http.client.HTTPConnection(base.hostname, base.port, timeout=5)
    body = {"messages": [{"role": "user", "content": "Why is the sky blue?"}], "tools": tools}
    conn.request("POST", base.path + "/chat/completions", json.dumps(body))
    reply = json.loads(conn.getresponse().read())
    conn.close()
    return reply
chat([])
chat([json.loads(sys.argv[1])])
proxy = urlsplit(os.environ["HTTPS_PROXY"])
with socket.create_connection((proxy.hostname, proxy.port), timeout=5) as raw:
    raw.sendall(b"CONNECT beacon.outfence.test:443 HTTP/1.0\\r\\n\\r\\n")
    raw.recv(4096)
"""


class RunWithModelTapTests(unittest.TestCase):
    def test_run_reports_origin_tool_and_trigger(self):
        model = scripted_model()
        with Service(model), tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "policy.json"
            policy.write_text(json.dumps({"version": 1, "allow": [], "allow_from": ["user"]}))
            output = Path(tmp) / "run"
            upstream = f"http://127.0.0.1:{model.server_port}"
            code = main(
                ["run", "--policy", str(policy), "--model-upstream", upstream]
                + ["--timeout", "20", "--output", str(output), "--"]
                + [sys.executable, "-c", WORKLOAD, json.dumps(TOOL)]
            )
            report = json.loads((output / "report.json").read_text())
        self.assertEqual(code, 2)
        (event,) = report["events"]
        self.assertEqual(
            (event["reason"], event["origin"], event["tool"]), ("model_originated", "model", FETCH)
        )
        self.assertEqual(event["trigger"]["servers"], ["quickfetch-mcp"])
        self.assertEqual(report["coverage"]["provenance"], "model_tap")
        self.assertEqual(report["model_tap"]["requests"], 2)
        self.assertEqual(len(model.received), 2)
        text = format_report(report)
        self.assertIn("origin: named only by the model", text)
        self.assertIn("trigger?: MCP server quickfetch-mcp appeared", text)
        self.assertNotIn("sky", json.dumps(report))


if __name__ == "__main__":
    unittest.main()

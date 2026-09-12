import http.client
import json
import socket
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from outfence.cli import main
from outfence.core import Proxy, Service, load_policy, now, write_report
from outfence.demo import Fixture, demo_requests

POLICY = {
    "version": 1,
    "allow": [{"host": "model.example", "port": 80}, {"host": "retrieval.example", "port": 80}],
}


class ProxyTests(unittest.TestCase):
    def test_enforce_and_observe_destination_receipts(self):
        for mode, expected in [("enforce", 2), ("observe", 3)]:
            with self.subTest(mode=mode):
                fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
                fixture.received = []
                routes = {
                    (h, 80): fixture.server_address
                    for h in ("model.example", "retrieval.example", "telemetry.example")
                }
                with Service(fixture), Service(Proxy(POLICY, mode, routes)) as proxy:
                    statuses = demo_requests(proxy.server_port)
                self.assertEqual(len(fixture.received), expected)
                self.assertEqual(statuses, [200, 200, 403 if mode == "enforce" else 200])
                self.assertEqual(
                    proxy.events[-1]["action"], "blocked" if mode == "enforce" else "would_block"
                )
                self.assertNotIn("path", proxy.events[0])

    def test_connect_denied_before_upstream(self):
        with Service(Proxy(POLICY, "enforce")) as proxy:
            with socket.create_connection(proxy.server_address) as conn:
                conn.sendall(b"CONNECT forbidden.example:443 HTTP/1.0\r\n\r\n")
                self.assertIn(b"403", conn.recv(4096))
            self.assertEqual(proxy.events[0]["connection"], "not_attempted")

    def test_connect_allowed_tunnel(self):
        fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        fixture.received = []
        policy = {"version": 1, "allow": [{"host": "model.example", "port": 443}]}
        with (
            Service(fixture),
            Service(
                Proxy(policy, "enforce", {("model.example", 443): fixture.server_address})
            ) as proxy,
        ):
            conn = http.client.HTTPConnection(*proxy.server_address, timeout=3)
            conn.set_tunnel("model.example", 443)
            conn.request("GET", "/")
            self.assertEqual(conn.getresponse().status, 200)
            conn.close()
        self.assertEqual(len(fixture.received), 1)
        self.assertEqual(proxy.events[0]["connection"], "established")

    def test_private_address_denied_even_when_allowlisted(self):
        with Service(
            Proxy({"version": 1, "allow": [{"host": "127.0.0.1", "port": 80}]}, "enforce")
        ) as proxy:
            conn = http.client.HTTPConnection(*proxy.server_address)
            conn.request("GET", "http://127.0.0.1/")
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            conn.close()
            self.assertEqual(proxy.events[0]["reason"], "non_public_address")

    def test_report_escapes_metadata_and_preserves_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = {
                "time": now(),
                "host": "<script>alert(1)</script>",
                "port": 80,
                "action": "blocked",
                "reason": "not_in_allowlist",
                "connection": "not_attempted",
            }
            report = write_report(Path(tmp) / "report", "enforce", POLICY, [event], now(), 0)
            content = (Path(tmp) / "report/report.html").read_text()
            self.assertNotIn("<script>", content)
            self.assertIn("&lt;script&gt;", content)
            self.assertEqual(report["coverage"]["status"], "proxy_only")
            self.assertEqual(report["exit_code"], 2)

    def test_runner_exit_and_timeout(self):
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            for label, command, expected in [
                (
                    "ok",
                    [
                        sys.executable,
                        "-c",
                        'import os; assert os.environ["HTTP_PROXY"].startswith("http://127.0.0.1:")',
                    ],
                    0,
                ),
                ("failure", [sys.executable, "-c", "raise SystemExit(7)"], 4),
                ("timeout", [sys.executable, "-c", "import time; time.sleep(10)"], 3),
            ]:
                with self.subTest(label=label):
                    output = Path(tmp) / label
                    code = main(
                        [
                            "run",
                            "--policy",
                            str(Path(__file__).resolve().parents[1] / "examples/policy.json"),
                            "--timeout",
                            "1",
                            "--output",
                            str(output),
                            "--",
                        ]
                        + command
                    )
                    self.assertEqual(code, expected)
                    report = json.loads((output / "report.json").read_text())
                    self.assertEqual(report["exit_code"], expected)
                    if label == "failure":
                        self.assertEqual(report["workload_exit_code"], 7)
                    if label == "timeout":
                        self.assertEqual(report["coverage"]["status"], "incomplete")

    def test_invalid_policy_and_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "policy.json"
            p.write_text('{"version":1,"allow":[{"host":"*.example","port":80}]}')
            with self.assertRaises(ValueError):
                load_policy(p)
            self.assertEqual(main(["demo", "--output", tmp]), 3)


if __name__ == "__main__":
    unittest.main()

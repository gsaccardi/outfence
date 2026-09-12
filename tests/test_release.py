"""Regression tests for the alpha's documented boundaries and failure outcomes."""

import http.client
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

from outfence.cli import main
from outfence.policy import validate_policy
from outfence.proxy import LoopbackHTTPServer as ThreadingHTTPServer
from outfence.proxy import Proxy, Service, now
from outfence.report import write_report

POLICY = {"version": 1, "allow": [{"host": "model.example", "port": 80}]}


class AlphaTests(unittest.TestCase):
    def test_local_server_setup_never_uses_reverse_dns(self):
        with patch("socket.getfqdn", side_effect=AssertionError("Unexpected DNS lookup")):
            with Service(ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)):
                with Service(Proxy(POLICY, "enforce")) as proxy:
                    self.assertGreater(proxy.server_port, 0)

    def test_policy_rejects_ambiguous_values(self):
        invalid = [
            None,
            [],
            {"version": True, "allow": []},
            {"version": 1, "allow": [], "unknown": True},
        ]
        for host, port in [
            ("*.example", 80),
            ("Model.example", 80),
            ("model.example.", 80),
            ("a..example", 80),
            ("-a.example", 80),
            ("model.example", True),
            ("model.example", 0),
            ("model.example", 65536),
        ]:
            invalid.append({"version": 1, "allow": [{"host": host, "port": port}]})
        invalid.append({"version": 1, "allow": POLICY["allow"] * 2})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_policy(value)

    def test_empty_policy_and_ipv6_rule_are_valid(self):
        validate_policy({"version": 1, "allow": []})
        validate_policy({"version": 1, "allow": [{"host": "::1", "port": 443}]})

    def test_init_check_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            self.assertEqual(main(["init", str(path)]), 0)
            self.assertEqual(json.loads(path.read_text())["allow"], [])
            self.assertEqual(main(["check", str(path)]), 0)
            self.assertEqual(main(["init", str(path), "--demo"]), 3)
            self.assertEqual(json.loads(path.read_text())["allow"], [])

    def test_invalid_request_is_visible_without_payload(self):
        with Service(Proxy(POLICY, "enforce")) as proxy:
            for method, url in [
                ("GET", "http://secret:token@model.example/private"),
                ("GET", "http://model.example:0/private"),
                ("CONNECT", "model.example:443?hidden"),
                ("POST", "http://model.example/private"),
            ]:
                conn = http.client.HTTPConnection(*proxy.server_address, timeout=3)
                conn.request(method, url)
                response = conn.getresponse()
                self.assertGreaterEqual(response.status, 400)
                response.read()
                conn.close()
        self.assertEqual(len(proxy.events), 4)
        serialized = json.dumps(proxy.snapshot())
        for secret in ["token", "private", "hidden"]:
            self.assertNotIn(secret, serialized)

    def test_denial_does_not_resolve_hostname(self):
        with Service(Proxy(POLICY, "enforce")) as proxy:
            with patch("outfence.proxy.socket.getaddrinfo") as dns:
                target, event = proxy.destination("forbidden.example", 443, "connect")
                dns.assert_not_called()
        self.assertIsNone(target)
        self.assertEqual(event["action"], "blocked")

    def test_dns_mixed_private_and_public_denied(self):
        with Service(Proxy(POLICY, "enforce")) as proxy:
            rows = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 80))
                for ip in ["8.8.8.8", "127.0.0.1"]
            ]
            with patch("outfence.proxy.socket.getaddrinfo", return_value=rows):
                target, event = proxy.destination("model.example", 80, "http")
        self.assertIsNone(target)
        self.assertEqual(event["reason"], "non_public_address")

    def test_upstream_failure_returns_502_and_error_report(self):
        with Service(Proxy(POLICY, "enforce", {("model.example", 80): ("127.0.0.1", 1)})) as proxy:
            with patch.object(proxy, "connect", side_effect=OSError("synthetic")):
                conn = http.client.HTTPConnection(*proxy.server_address, timeout=3)
                conn.request("GET", "http://model.example/")
                response = conn.getresponse()
                self.assertEqual(response.status, 502)
                response.read()
                conn.close()
        with tempfile.TemporaryDirectory() as tmp:
            report = write_report(
                Path(tmp) / "report", "enforce", POLICY, proxy.snapshot(), now(), 0
            )
        self.assertEqual(report["exit_code"], 3)

    def test_redirect_to_denied_destination_never_reaches_fixture(self):
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.server.received.append(self.headers["Host"])
                self.send_response(302)
                self.send_header("Location", "http://forbidden.example/secret")
                self.send_header("Content-Length", "0")
                self.end_headers()

        fixture = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        fixture.received = []
        routes = {
            (host, 80): fixture.server_address for host in ["model.example", "forbidden.example"]
        }
        with Service(fixture), Service(Proxy(POLICY, "enforce", routes)) as proxy:
            opener = build_opener(ProxyHandler({"http": f"http://127.0.0.1:{proxy.server_port}"}))
            with patch.dict("os.environ", {"no_proxy": "", "NO_PROXY": ""}):
                with self.assertRaises(HTTPError) as error:
                    opener.open("http://model.example/", timeout=3)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
        self.assertEqual(fixture.received, ["model.example:80"])
        self.assertEqual([e["action"] for e in proxy.events], ["allowed", "blocked"])

    def test_active_tunnel_is_closed_and_incomplete_at_shutdown(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        accepted = threading.Event()

        def peer():
            with listener.accept()[0] as conn:
                accepted.set()
                while conn.recv(4096):
                    pass

        worker = threading.Thread(target=peer, daemon=True)
        worker.start()
        with Service(
            Proxy(POLICY, "enforce", {("model.example", 80): listener.getsockname()})
        ) as proxy:
            client = socket.create_connection(proxy.server_address, timeout=3)
            client.sendall(b"CONNECT model.example:80 HTTP/1.0\r\n\r\n")
            data = b""
            while b"\r\n\r\n" not in data:
                data += client.recv(4096)
            self.assertIn(b"200", data)
            self.assertTrue(accepted.wait(2))
        self.assertTrue(proxy.incomplete)
        self.assertEqual(client.recv(1), b"")
        client.close()
        worker.join(2)
        listener.close()
        self.assertFalse(worker.is_alive())

    def test_event_limit_denies_further_connections_and_marks_gap(self):
        with Service(Proxy(POLICY, "enforce", max_events=1)) as proxy:
            for _ in range(2):
                conn = http.client.HTTPConnection(*proxy.server_address, timeout=3)
                conn.request("GET", "http://denied.example/")
                response = conn.getresponse()
                response.read()
                conn.close()
        self.assertEqual(response.status, 503)
        self.assertEqual(proxy.dropped_events, 1)
        self.assertTrue(proxy.incomplete)

    def test_resolved_address_is_pinned(self):
        with Service(Proxy(POLICY, "enforce")) as proxy:
            with patch(
                "outfence.proxy.socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))],
            ):
                target, _ = proxy.destination("model.example", 80, "http")
            self.assertEqual(target, ("8.8.8.8", 80))

    def test_reserved_output_prevents_command_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "policy.json"
            policy.write_text(json.dumps(POLICY))
            with patch("outfence.cli.run_workload") as run:
                self.assertEqual(
                    main(["run", "--policy", str(policy), "--output", tmp, "--", "echo", "hello"]),
                    3,
                )
                run.assert_not_called()

    def test_report_permissions_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report"
            write_report(output, "enforce", POLICY, [], now(), 0)
            self.assertEqual((output.stat().st_mode & 0o777), 0o700)
            self.assertEqual(((output / "report.json").stat().st_mode & 0o777), 0o600)
            with self.assertRaises(FileExistsError):
                write_report(output, "enforce", POLICY, [], now(), 0, reserved=True)


if __name__ == "__main__":
    unittest.main()

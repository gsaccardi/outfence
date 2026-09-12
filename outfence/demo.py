"""Synthetic services used only by demo and offline tests."""

import http.client
from http.server import BaseHTTPRequestHandler


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

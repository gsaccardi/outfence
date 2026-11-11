"""Loopback reverse proxy that observes chat completions sent to a local model server."""

import http.client
import json
from http.server import BaseHTTPRequestHandler

from .proxy import MODEL_TIMEOUT, LoopbackHTTPServer

LIMIT = 8 * 1024 * 1024
CHAT_PATHS = ("/v1/chat/completions", "/chat/completions")
MODEL_PATHS = ("/v1/models", "/models")


class ModelTap(LoopbackHTTPServer):
    daemon_threads = True

    def __init__(self, upstream, session):
        self.upstream = upstream
        self.session = session
        super().__init__(("127.0.0.1", 0), TapHandler)


class TapHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "Outfence"
    sys_version = ""

    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def refuse(self, status, message):
        self.reply(status, json.dumps({"error": {"message": message}}).encode() + b"\n")

    def do_GET(self):
        # Model listing carries no conversation content, so it is forwarded unobserved.
        if self.path.split("?", 1)[0] not in MODEL_PATHS:
            return self.refuse(404, "The Outfence model tap forwards chat completions only.")
        self.forward("GET", None)

    def do_POST(self):
        session = self.server.session
        try:
            length = int(self.headers.get("Content-Length", ""))
            if (
                self.path not in CHAT_PATHS
                or not 0 < length <= LIMIT
                or self.headers.get("Transfer-Encoding")
            ):
                raise ValueError()
            raw = self.rfile.read(length)
            body = json.loads(raw)
            if not isinstance(body, dict) or body.get("stream"):
                raise ValueError()
            session.observe_request(body)
        except ValueError:
            session.reject()
            return self.refuse(
                400, "The Outfence model tap supports non-streaming chat completions only."
            )
        self.forward("POST", raw)

    def forward(self, method, raw):
        session = self.server.session
        conn = http.client.HTTPConnection(*self.server.upstream, timeout=MODEL_TIMEOUT)
        try:
            headers = {"Content-Type": "application/json"} if raw is not None else {}
            if self.headers.get("Authorization"):
                # Passed through for local servers that require a key; never recorded.
                headers["Authorization"] = self.headers["Authorization"]
            conn.request(method, self.path, body=raw, headers=headers)
            response = conn.getresponse()
            body = response.read(LIMIT + 1)
            if len(body) > LIMIT:
                raise ValueError()
        except (OSError, http.client.HTTPException, ValueError):
            session.fail()
            return self.refuse(502, "The model server failed or returned too much data.")
        finally:
            conn.close()
        if method == "POST" and response.status == 200:
            try:
                session.observe_response(json.loads(body))
            except ValueError:
                # Fail closed: forwarding an unreadable answer could hide tool calls.
                session.fail()
                return self.refuse(502, "The model response could not be inspected.")
        self.reply(response.status, body, response.getheader("Content-Type") or "application/json")

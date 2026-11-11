"""Loopback forward proxy. This is not a network isolation boundary."""

import copy
import datetime as dt
import http.client
import ipaddress
import select
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .policy import normalize_host, validate_policy

# Seconds a local model may take to answer; the model tap and the relay to it wait this long.
MODEL_TIMEOUT = 300


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def origin_form(parsed):
    """Path and query for an upstream request line; an empty path is the root."""
    return (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")


def content_length(response):
    """The declared body length, or None when absent, malformed or made moot by chunked coding."""
    value = response.getheader("Content-Length", "")
    if response.getheader("Transfer-Encoding") or not (value.isascii() and value.isdigit()):
        return None
    return int(value)


class LoopbackHTTPServer(ThreadingHTTPServer):
    """Bind numerical loopback without HTTPServer's unused reverse-DNS lookup."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class Proxy(LoopbackHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        policy,
        mode,
        fixtures=None,
        max_events=10000,
        session=None,
        on_decision=None,
        tap=None,
    ):
        if mode not in ("enforce", "observe"):
            raise ValueError("Mode must be enforce or observe.")
        self.policy = copy.deepcopy(validate_policy(policy))
        self.mode = mode
        # Only internal synthetic tests/demo supply these fixed endpoint mappings.
        self.fixtures = fixtures or {}
        # Model-tap provenance; without it, decisions use exact allow rules only.
        self.session = session
        self.on_decision = on_decision
        # This run's model tap. Clients that honor proxy settings send their model calls here,
        # so requests for exactly that address are passed to the tap, not decided or recorded.
        self.tap = tap
        self.events = []
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.sockets = set()
        self.active = 0
        self.incomplete = False
        self.max_events = max_events
        self.dropped_events = 0
        super().__init__(("127.0.0.1", 0), Handler)

    def process_request(self, request, client_address):
        with self.lock:
            if self.active >= 32 or self.stopping.is_set():
                self.incomplete = True
                request.close()
                return
            self.active += 1
            self.sockets.add(request)
        request.settimeout(10)
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.lock:
                self.active -= 1
                self.sockets.discard(request)

    def handle_error(self, request, client_address):
        # Never print request contents or raw exception strings into shared logs.
        with self.lock:
            self.incomplete = True

    def record(self, host, port, transport, action, reason, **details):
        event = dict(
            time=now(),
            host=host,
            port=port,
            transport=transport,
            action=action,
            reason=reason,
            connection="not_attempted",
            tool=None,
            origin=None,
            named_by=None,
            trigger=None,
        )
        event.update(details)
        with self.lock:
            if len(self.events) >= self.max_events:
                self.dropped_events += 1
                self.incomplete = True
                return None
            self.events.append(event)
        return event

    def update(self, event, **fields):
        if event is not None:
            with self.lock:
                event.update(fields)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.events)

    def announce(self, event):
        if self.on_decision is not None and event is not None:
            try:
                self.on_decision(dict(event))
            except Exception:
                pass  # A display failure must never change or delay a proxy decision.

    def destination(self, host, port, transport):
        allowed = {"host": host, "port": port} in self.policy["allow"]
        reason = "allowlist_match" if allowed else "not_in_allowlist"
        details = {}
        if self.session is not None:
            origin, granted, details = self.session.check(
                host, port, self.policy.get("allow_from", [])
            )
            details["origin"] = origin
            if not allowed and granted:
                allowed, reason = True, f"allow_from_{granted}"
            elif not allowed and origin == "model":
                reason = "model_originated"
        action = "allowed" if allowed else "blocked" if self.mode == "enforce" else "would_block"
        event = self.record(host, port, transport, action, reason, **details)
        if event is None or action == "blocked":
            return None, event
        if (host, port) in self.fixtures:
            return self.fixtures[(host, port)], event
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = [row[4][0] for row in addresses]
            if not ips or any(
                (not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast)
                for ip in ips
            ):
                self.update(event, action="blocked", reason="non_public_address")
                return None, event
            # Pin the checked IP; the upstream client must not resolve the host again.
            return (ips[0], port), event
        except OSError:
            self.update(event, connection="failed", reason="dns_failed")
            return None, event

    def connect(self, target, event):
        with self.lock:
            if self.stopping.is_set():
                raise OSError("Proxy stopping")
        upstream = socket.create_connection(target, timeout=10)
        with self.lock:
            if self.stopping.is_set():
                upstream.close()
                raise OSError("Proxy stopping")
            self.sockets.add(upstream)
        self.update(event, connection="established")
        return upstream

    def close_upstream(self, upstream):
        if upstream is not None:
            with self.lock:
                self.sockets.discard(upstream)
            upstream.close()

    def stop_connections(self):
        self.stopping.set()
        with self.lock:
            if self.active:
                # A report must disclose requests interrupted at the workload boundary.
                self.incomplete = True
            sockets = list(self.sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with self.lock:
                if not self.active:
                    return
            time.sleep(0.01)
        # Resolver calls may remain blocked in daemon threads; new upstream connections
        # are refused by connect() once stopping is set. Evidence stays incomplete.


class Handler(BaseHTTPRequestHandler):
    rbufsize = 0  # Do not consume early CONNECT bytes into a separate read buffer.
    protocol_version = "HTTP/1.0"
    server_version = "Outfence"
    sys_version = ""

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler uses this for unknown methods and bad request lines.
        self.server.record(None, None, "unknown", "blocked", "invalid_or_unsupported_request")
        self.error(code, "Invalid or unsupported proxy request")

    def error(self, status, message):
        body = (message + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def invalid(self):
        self.server.record(None, None, "unknown", "blocked", "invalid_destination")
        self.error(400, "Invalid proxy destination")

    def route(self, host, port, transport):
        target, event = self.server.destination(host, port, transport)
        self.server.announce(event)
        if target is None:
            if event is None:
                self.error(503, "Event limit reached")
            else:
                self.error(403 if event["action"] == "blocked" else 502, event["reason"])
        return target, event

    def for_tap(self, host, port):
        """True for this run's model tap, the one loopback address the proxy passes on."""
        tap = self.server.tap
        return tap is not None and port == tap[1] and host in ("127.0.0.1", "localhost")

    def pipe(self, upstream, idle):
        """Copy bytes both ways until one side closes. False: nothing moved for idle seconds."""
        while not self.server.stopping.is_set():
            ready, _, _ = select.select([self.connection, upstream], [], [], idle)
            if not ready:
                return False
            for source in ready:
                chunk = source.recv(65536)
                if not chunk:
                    return True
                (upstream if source is self.connection else self.connection).sendall(chunk)
        return True

    def relay_to_tap(self, parsed):
        """Hand one plain-HTTP request to the model tap, which inspects it, and pipe the answer."""
        lines = [f"{self.command} {origin_form(parsed)} HTTP/1.0"]
        for key in ("Content-Type", "Content-Length", "Transfer-Encoding", "Authorization"):
            value = self.headers.get(key)
            if value and "\r" not in value and "\n" not in value:
                lines.append(f"{key}: {value}")
        try:
            upstream = self.server.connect(self.server.tap, None)
        except OSError:
            return self.error(502, "Model tap unavailable")
        try:
            upstream.sendall("\r\n".join([*lines, "", ""]).encode("latin-1"))
            # Any body is still unread on the client socket. The tap answers, then closes.
            self.pipe(upstream, MODEL_TIMEOUT)
        except (OSError, ValueError):
            pass  # The client sees a closed connection; the tap counts its own failures.
        finally:
            self.server.close_upstream(upstream)

    def do_CONNECT(self):
        try:
            parsed = urlsplit("//" + self.path)
            host, port = normalize_host(parsed.hostname), parsed.port
            if (
                not port
                or parsed.username is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError()
        except ValueError:
            return self.invalid()
        tap = self.for_tap(host, port)
        target, event = (self.server.tap, None) if tap else self.route(host, port, "connect")
        if target is None:
            return
        upstream = None
        established = False
        try:
            upstream = self.server.connect(target, event)
            self.send_response(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            established = True
            # Opaque byte stream: no TLS inspection, request/body parsing or logging.
            if not self.pipe(upstream, MODEL_TIMEOUT if tap else 15):
                self.server.update(event, connection="failed", reason="tunnel_idle_timeout")
        except (OSError, ValueError):
            self.server.update(event, connection="failed", reason="connection_failed")
            if not established:
                self.error(502, "Upstream connection failed")
        finally:
            self.server.close_upstream(upstream)

    def do_POST(self):
        try:
            parsed = urlsplit(self.path)
            tap = parsed.scheme == "http" and self.for_tap(parsed.hostname, parsed.port)
        except ValueError:
            tap = False
        if tap:
            return self.relay_to_tap(parsed)
        # Refused and recorded like every other method the proxy does not forward.
        self.send_error(501)

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            host = normalize_host(parsed.hostname)
            port = parsed.port if parsed.port is not None else 80
            if (
                parsed.scheme != "http"
                or not port
                or parsed.username is not None
                or parsed.fragment
            ):
                raise ValueError()
            if (
                self.headers.get("Transfer-Encoding")
                or self.headers.get("Content-Length", "0") != "0"
            ):
                raise ValueError()
        except ValueError:
            return self.invalid()
        if self.for_tap(host, port):
            return self.relay_to_tap(parsed)
        target, event = self.route(host, port, "http")
        if target is None:
            return
        conn = http.client.HTTPConnection(*target, timeout=10)
        upstream = None
        headers_sent = False
        try:
            upstream = self.server.connect(target, event)
            conn.sock = upstream
            authority = f"[{host}]" if ":" in host else host
            conn.request(
                "GET",
                origin_form(parsed),
                headers={"Host": f"{authority}:{port}", "Connection": "close"},
            )
            response = conn.getresponse()
            declared = content_length(response)
            self.send_response(response.status)
            for key in ("Content-Type", "Location"):
                value = response.getheader(key)
                if value and "\r" not in value and "\n" not in value:
                    self.send_header(key, value)
            if declared is not None:
                self.send_header("Content-Length", str(declared))
            self.end_headers()
            headers_sent = True
            sent = 0
            while chunk := response.read(65536):
                self.wfile.write(chunk)
                sent += len(chunk)
            if declared is not None and sent < declared and response.status not in (204, 304):
                # The upstream closed early. The client sees a short body; the report must too.
                raise http.client.IncompleteRead(b"")
        except (OSError, http.client.HTTPException):
            self.server.update(event, connection="failed", reason="connection_failed")
            if not headers_sent:
                self.error(502, "Upstream connection failed")
        finally:
            conn.close()
            self.server.close_upstream(upstream)


class Service:
    def __init__(self, server):
        self.server = server

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server

    def __exit__(self, *args):
        self.server.shutdown()
        if isinstance(self.server, Proxy):
            self.server.stop_connections()
        self.server.server_close()
        self.thread.join()

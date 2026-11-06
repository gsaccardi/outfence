"""Model-context provenance: which source named a destination first, before the agent used it.

Host names are matched as text in the chat requests and responses seen by the model tap.
Only derived metadata is retained; prompts, answers and tool results are not stored.
"""

import hashlib
import json
import re
import threading
import time
from urllib.parse import urlsplit

from .policy import normalize_host
from .proxy import now

# Unknown roles count as untrusted data, never as user intent.
ROLES = {
    "user": "user",
    "system": "system",
    "developer": "system",
    "tool": "tool_output",
    "function": "tool_output",
    "assistant": "model",
}
URL = re.compile(r"\b[a-z][a-z0-9+.-]{0,15}://[^\s\"'<>`\\]+", re.IGNORECASE)
NAME = re.compile(
    r"(?<![\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}(?![\w-])",
    re.IGNORECASE,
)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
WEB_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}


def strings(value, depth=0):
    """Yield strings from JSON-like values, including JSON encoded inside strings."""
    if depth > 32:
        return
    if isinstance(value, str):
        yield value
        if value.lstrip()[:1] in ("{", "["):
            try:
                yield from strings(json.loads(value), depth + 1)
            except ValueError:
                pass
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item, depth + 1)


def destinations(text):
    """Return (host, port) pairs named in text; port is None for a bare host name."""
    found = []
    for match in URL.finditer(text):
        try:
            parts = urlsplit(match.group(0).rstrip(".,;:!?"))
            port = parts.port or WEB_PORTS.get(parts.scheme.lower())
            found.append((normalize_host(parts.hostname or ""), port))
        except ValueError:
            pass
    rest = URL.sub(" ", text)
    for match in [*NAME.finditer(rest), *IPV4.finditer(rest)]:
        try:
            found.append((normalize_host(match.group(0).lower()), None))
        except ValueError:
            pass
    return found


def server_of(tool):
    """MCP server name from a namespaced tool name such as mcp__server__tool."""
    parts = tool.split("__") if isinstance(tool, str) else []
    return parts[1] if len(parts) >= 3 and parts[0] == "mcp" and parts[1] else None


def servers(tools):
    return sorted({name for name in map(server_of, tools) if name})


def variants(host):
    return {host, host[4:]} if host.startswith("www.") else {host, "www." + host}


class Session:
    """What the model was told and what it asked for, reduced to destination metadata."""

    def __init__(self, on_change=None):
        self.lock = threading.Lock()
        # host -> {origin: {port: order of the first mention}}; port None means no port was given
        self.named = {}
        self.indexed = set()
        self.order = 0
        self.tools = None
        self.environment = []
        self.tool_calls = []
        self.requests = self.responses = self.rejected = self.errors = 0
        self.on_change = on_change

    def notify(self, notes):
        for note in notes if self.on_change is not None else []:
            try:
                self.on_change(note)
            except Exception:
                pass  # A display failure must never break the model tap.

    def index(self, origin, value):
        for text in strings(value):
            digest = hashlib.sha256(f"{origin}\0{text}".encode("utf-8", "replace")).digest()
            if digest not in self.indexed:
                self.indexed.add(digest)
                self.order += 1
                for host, port in destinations(text):
                    ports = self.named.setdefault(host, {}).setdefault(origin, {})
                    ports.setdefault(port, self.order)

    def observe_request(self, body):
        messages, tools = body.get("messages"), body.get("tools") or []
        if not isinstance(messages, list) or not isinstance(tools, list):
            raise ValueError("Unsupported chat request.")
        with self.lock:
            self.requests += 1
            for message in messages:
                if isinstance(message, dict):
                    origin = ROLES.get(message.get("role"), "tool_output")
                    self.index(origin, {k: v for k, v in message.items() if k != "role"})
            names = set()
            for tool in tools:
                self.index("tool_definition", tool)
                function = tool.get("function") if isinstance(tool, dict) else None
                if isinstance(function, dict) and isinstance(function.get("name"), str):
                    names.add(function["name"])
            change = self.track(sorted(names))
        if change and (change["added"] or change["removed"]):
            self.notify([dict(kind="tools", added=change["added"], removed=change["removed"])])

    def track(self, names):
        if names != self.tools:
            before = set(self.tools or ())
            self.environment.append(
                dict(
                    time=now(),
                    clock=time.monotonic(),
                    initial=self.tools is None,
                    added=[name for name in names if name not in before],
                    removed=sorted(before - set(names)),
                )
            )
            self.tools = names
            return self.environment[-1]
        return None

    def observe_response(self, body):
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list):
            raise ValueError("Unsupported chat response.")
        notes = []
        with self.lock:
            self.responses += 1
            for choice in choices:
                message = choice.get("message") if isinstance(choice, dict) else None
                if not isinstance(message, dict):
                    continue
                self.index("model", message)
                raw_calls = message.get("tool_calls")
                calls = [
                    call.get("function")
                    for call in (raw_calls if isinstance(raw_calls, list) else [])
                    if isinstance(call, dict)
                ]
                if isinstance(message.get("content"), str):
                    # Some local servers return Qwen-style calls as text instead of tool_calls.
                    for raw in TOOL_CALL.findall(message["content"]):
                        try:
                            calls.append(json.loads(raw))
                        except ValueError:
                            pass
                for call in calls:
                    if isinstance(call, dict):
                        name = call.get("name")
                        hosts = {
                            host
                            for text in strings(call.get("arguments"))
                            for host, _ in destinations(text)
                        }
                        self.tool_calls.append(
                            dict(
                                time=now(),
                                name=name if isinstance(name, str) else None,
                                hosts=sorted(hosts),
                            )
                        )
                        notes.append(dict(self.tool_calls[-1], kind="tool_call"))
        self.notify(notes)

    def reject(self):
        with self.lock:
            self.rejected += 1

    def fail(self):
        with self.lock:
            self.errors += 1

    def check(self, host, port, allow_from):
        """Return (origin, allowing origin or None, details) for one proxy decision.

        The origin is the source that named the host first. An allowed source grants the
        destination only if it named it before the model did, so a later message repeating
        the model's words, such as a sub-agent's task or a conversation summary, grants nothing.
        """
        moment = time.monotonic()
        names = variants(host)
        with self.lock:
            mentions = sorted(
                (order, origin, given == port or (given is None and port in (80, 443)))
                for name in names
                for origin, ports in self.named.get(name, {}).items()
                for given, order in ports.items()
            )
            call = next((c for c in reversed(self.tool_calls) if names & set(c["hosts"])), None)
            change = next((e for e in reversed(self.environment) if e["added"]), None)
        covering = [origin for _, origin, covers in mentions if covers]
        named_by = list(dict.fromkeys(covering or [origin for _, origin, _ in mentions]))
        # In order of mention, the first allowed source grants, unless the model came first.
        first = next((o for o in covering if o == "model" or o in allow_from), None)
        granted = None if first == "model" else first
        origin = named_by[0] if named_by else "unattributed"
        trigger = None
        # A trigger candidate only explains destinations that the model named first.
        if origin == "model" and change is not None:
            trigger = dict(
                servers=servers(change["added"]),
                tools=change["added"],
                seconds_before=round(moment - change["clock"], 1),
                at_start=change["initial"],
            )
        tool = call["name"] if call else None
        return origin, granted, dict(tool=tool, trigger=trigger, named_by=named_by)

    def summary(self):
        with self.lock:
            return dict(
                requests=self.requests,
                responses=self.responses,
                rejected=self.rejected,
                errors=self.errors,
                environment=[
                    dict(
                        time=change["time"],
                        added=change["added"],
                        removed=change["removed"],
                        servers=servers(change["added"]),
                    )
                    for change in self.environment
                ],
                tool_calls=[dict(call) for call in self.tool_calls],
            )

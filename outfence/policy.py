"""Exact destination policy. No wildcard or suffix matching."""

import ipaddress
import json
import re
from pathlib import Path

DEMO_POLICY = {
    "version": 1,
    "allow": [
        {"host": "model.example", "port": 80},
        {"host": "retrieval.example", "port": 80},
    ],
}
# Most trusted first. A policy may allow destinations named by any source except the model.
ORIGINS = ("user", "system", "tool_definition", "tool_output", "model")
ALLOW_FROM = ORIGINS[:-1]


def normalize_host(value):
    if not isinstance(value, str) or not value or not value.isascii():
        raise ValueError("Host must be an ASCII hostname or IP address.")
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    value = value.lower()
    if len(value) > 253 or not all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in value.split(".")
    ):
        raise ValueError("Use an exact hostname without wildcards or trailing dots.")
    return value


def validate_policy(data):
    if (
        not isinstance(data, dict)
        or not {"version", "allow"} <= set(data) <= {"version", "allow", "allow_from"}
        or type(data["version"]) is not int
        or data["version"] != 1
        or not isinstance(data["allow"], list)
    ):
        raise ValueError("Policy must contain version: 1, an allow list and optional allow_from.")
    allow_from = data.get("allow_from", [])
    if (
        not isinstance(allow_from, list)
        or any(origin not in ALLOW_FROM for origin in allow_from)
        or len(set(allow_from)) != len(allow_from)
    ):
        raise ValueError(f"allow_from must list distinct sources from: {', '.join(ALLOW_FROM)}.")
    seen = set()
    for rule in data["allow"]:
        if not isinstance(rule, dict) or set(rule) != {"host", "port"}:
            raise ValueError("Each rule needs exactly host and port.")
        host, port = rule["host"], rule["port"]
        if normalize_host(host) != host:
            raise ValueError("Policy hosts must use lowercase/canonical form.")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Port must be an integer from 1 to 65535.")
        if (host, port) in seen:
            raise ValueError("Duplicate host/port rule.")
        seen.add((host, port))
    return data


def load_policy(path):
    return validate_policy(json.loads(Path(path).read_text(encoding="utf-8")))

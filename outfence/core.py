"""Compatibility imports for early prototype users. Prefer dedicated modules."""

from .policy import load_policy
from .proxy import Proxy, Service, now
from .report import write_report

__all__ = ["load_policy", "Proxy", "Service", "now", "write_report"]

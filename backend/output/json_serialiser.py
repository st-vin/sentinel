"""AuditReport JSON serialiser."""
from __future__ import annotations

import json
from datetime import datetime


def serialise_report(report_dict: dict) -> bytes:
    """Serialise an AuditReport dict to UTF-8 JSON bytes."""
    return json.dumps(report_dict, indent=2, default=_default_serialiser).encode("utf-8")


def _default_serialiser(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)

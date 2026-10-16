"""Make values JSON-safe (UUIDs, datetimes) for outbox payloads, audit data and tool results."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any


def jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

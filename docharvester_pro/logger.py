# filename: docharvester_pro/logger.py
"""Structured JSON logger used by the entire package."""
from __future__ import annotations
import json, sys, time
from enum import Enum
from typing import Any, Final, TypedDict

class Phase(str, Enum):
    DISPATCH = "dispatch"
    FETCH    = "fetch"
    RENDER   = "render"
    SPLIT    = "split"
    WRITE    = "write"

class LogRecord(TypedDict):
    timestamp: float
    url: str
    phase: str
    status: str
    msg: str
    extra: dict[str, Any]

_TS_FUNC: Final = time.time

def _emit(rec: LogRecord) -> None:
    sys.stdout.write(json.dumps(rec, separators=(",", ":")) + "\n")
    sys.stdout.flush()

def log(url: str, phase: Phase, status: str, msg: str, **extra: Any) -> None:  # noqa: D401
    """Emit a single structured log entry."""
    _emit(
        {
            "timestamp": _TS_FUNC(),
            "url": url,
            "phase": phase.value,
            "status": status,
            "msg": msg,
            "extra": extra,
        }
    )

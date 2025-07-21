# docharvester_pro/logging_utils.py
"""Structured JSON logger – write minimal, machine‑readable messages to stdout."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from types import FrameType
from typing import Any, Dict, Optional


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: Dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            if record.exc_info[0] is not None:
                payload["exc_type"] = record.exc_info[0].__name__
                payload["exc_msg"] = str(record.exc_info[1])
            else:
                payload["exc_type"] = "None"
                payload["exc_msg"] = str(record.exc_info[1]) if record.exc_info[1] else "No exception information"
        if record.args:
            payload["extra"] = record.args
        return json.dumps(payload, separators=(",", ":"))


class JSONLogger:
    """Logger that formats messages as JSON for structured logging."""

    _instance = None

    @classmethod
    def get(cls) -> "JSONLogger":
        """Get or create a singleton instance of JSONLogger."""
        if cls._instance is None:
            cls._instance = JSONLogger()
        return cls._instance

    def __init__(self):
        self.logger = logging.getLogger("docharvester_pro")
        # Configure logger if not already done
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(_JsonFormatter())
            self.logger.setLevel(logging.INFO)
            self.logger.addHandler(handler)

    def _log(self, level: int, msg: str, **kwargs) -> None:
        """Log a message with JSON formatting."""
        data = {"message": msg}
        data.update(kwargs)
        self.logger.log(level, json.dumps(data))

    def info(self, msg: str, **kwargs) -> None:  # noqa: D401
        """Log an info message with additional context as JSON."""
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:  # noqa: D401
        """Log an error message with additional context as JSON."""
        self._log(logging.ERROR, msg, **kwargs)

    def debug(self, msg: str, **kwargs) -> None:  # noqa: D401
        """Log a debug message with additional context as JSON."""
        self._log(logging.DEBUG, msg, **kwargs)


def get_logger(name: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name or "docharvester")
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


# Convenience façade mirroring stdlib logging
def info(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: D401
    get_logger().info(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: D401
    get_logger().error(msg, *args, **kwargs)


def debug(msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: D401
    get_logger().debug(msg, *args, **kwargs)

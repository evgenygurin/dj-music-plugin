"""Central stdlib :mod:`logging` setup for the MCP process.

Driven by :class:`~app.config.Settings` (``DJ_LOG_LEVEL``, ``DJ_LOG_FORMAT``).
``json`` emits one JSON object per line; structured MCP data uses ``extra=mcp_event``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import settings

_CONFIGURED = False


class JsonLogFormatter(logging.Formatter):
    """One JSON line per log record; optional ``mcp`` from ``mcp_event``."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        mcp = getattr(record, "mcp_event", None)
        if mcp is not None:
            payload["mcp"] = mcp
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _parse_level(name: str) -> int:
    n = (name or "INFO").upper()
    lv = getattr(logging, n, None)
    return lv if isinstance(lv, int) else logging.INFO


def _make_formatter() -> logging.Formatter:
    fmt = (settings.log_format or "json").lower().strip()
    if fmt == "json":
        return JsonLogFormatter()
    return logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")


def configure_logging(*, force: bool = False) -> None:
    """Configure root and common loggers (no-op after first call unless ``force``)."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    formatter = _make_formatter()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    log_path = (settings.log_file or "").strip()
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(path),
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(_parse_level(settings.log_level))

    for name in ("app", "fastmcp", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(_parse_level(settings.log_level))

    for noisy in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def mcp_extra(event: dict[str, Any]) -> dict[str, Any]:
    """Return ``extra`` for MCP events (avoids clashing with LogRecord attrs)."""
    return {"mcp_event": event}

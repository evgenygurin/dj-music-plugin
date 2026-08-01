from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Literal

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(rid: str | None = None) -> str:
    if rid is None:
        rid = uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


class ContextLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    def process(
        self,
        msg: str,
        kwargs: Any,
    ) -> tuple[str, Any]:
        rid = get_request_id()
        prefix = f"[{rid}] " if rid else ""
        return f"{prefix}{msg}", kwargs


def get_logger(name: str | None = None) -> ContextLoggerAdapter:
    _logger = logging.getLogger(name)
    return ContextLoggerAdapter(_logger, {})


def configure_logging(
    *,
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO",
    json_format: bool = False,
) -> None:
    if json_format:
        _configure_json_logging(level)
    else:
        _configure_dev_logging(level)


def _configure_dev_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)-25s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)


def _configure_json_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import json

            return json.dumps(
                {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "request_id": get_request_id(),
                    "message": record.getMessage(),
                    "module": record.module,
                    "line": record.lineno,
                },
                default=str,
            )

    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)


class MCPContextLogHandler:
    def __init__(self, ctx: Any) -> None:
        self._ctx = ctx

    async def info(self, message: str) -> None:
        await self._log("info", message)

    async def warning(self, message: str) -> None:
        await self._log("warning", message)

    async def error(self, message: str) -> None:
        await self._log("error", message)

    async def debug(self, message: str) -> None:
        await self._log("debug", message)

    async def _log(self, level: str, message: str) -> None:
        ctx = self._ctx
        if ctx is None:
            getattr(get_logger(__name__), level)(message)
            return
        try:
            await getattr(ctx, level)(message)
        except RuntimeError:
            getattr(get_logger(__name__), level)(message)


def mcp_log(ctx: Any) -> MCPContextLogHandler:
    return MCPContextLogHandler(ctx)

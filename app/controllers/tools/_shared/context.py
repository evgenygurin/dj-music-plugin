"""Facade over FastMCP :class:`Context` for use inside ``@tool`` bodies.

Problem
-------
Every tool that wanted to emit progress or informational messages had to
write the same guard::

    if ctx is not None:
        await ctx.info("Auto-analyzed 42 tracks")

This was repeated 30+ times across six files.

Solution
--------
:class:`ToolContext` wraps the optional FastMCP ``Context`` and exposes
``info()`` / ``warn()`` / ``progress()`` / ``elicit()`` methods that no-op
safely when the underlying context is absent. Tools create the facade at
entry and use it unconditionally.

Usage::

    async def my_tool(
        ...,
        _ctx: Context | None = None,
    ) -> ResponseModel:
        log = ToolContext(_ctx)
        await log.info("starting pipeline")
        ...
        await log.progress(done, total)
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.server.context import Context

_log = logging.getLogger("app.controllers.tool_context")


def _has_session(ctx: Context | None) -> bool:
    """True only when ``ctx`` is bound to a real, established MCP session.

    The REST gateway (``app/api/server.py``) calls ``mcp.call_tool()`` directly
    without going through a transport layer, so the resulting Context has
    ``request_context = None``. Touching ``ctx.session``, ``ctx.session_id``,
    ``ctx.info`` or any state API in that case raises
    ``RuntimeError("session is not available...")`` and crashes the tool.

    Treat "no MCP session" as just another flavour of "no context" and
    no-op cleanly so the same tool can be invoked from MCP transports
    (stdio, streamable-http) AND the REST gateway without conditionals.
    """
    if ctx is None:
        return False
    return getattr(ctx, "request_context", None) is not None


class ToolContext:
    """Null-safe facade around FastMCP :class:`Context`.

    Implements the GoF Facade / Null-Object hybrid: when the underlying
    context is absent — or attached to a request without an MCP session —
    every method becomes a silent no-op (with stdlib logging fallback).
    """

    __slots__ = ("_ctx", "_session_ok")

    def __init__(self, ctx: Context | None) -> None:
        self._ctx = ctx
        self._session_ok = _has_session(ctx)

    @property
    def active(self) -> bool:
        """``True`` if a real, session-bound FastMCP context is attached.

        This is stricter than ``ctx is not None``: a Context without an
        established MCP session counts as inactive because anything that
        touches the session will raise.
        """
        return self._session_ok

    @property
    def raw(self) -> Context | None:
        """Escape hatch for code that needs the underlying Context instance."""
        return self._ctx

    async def info(self, message: str) -> None:
        """Emit an informational log message.

        Falls back to stdlib logging when no MCP session is available so the
        same tool body works under MCP transports and the REST gateway.
        """
        if self._session_ok and self._ctx is not None:
            try:
                await self._ctx.info(message)
                return
            except Exception as exc:
                # Mirror the failure to local log and stop trying through ctx
                # for the rest of this call.
                _log.debug("ctx.info failed (%s); falling back to stdlib log", exc)
                self._session_ok = False
        _log.info(message)

    async def warn(self, message: str) -> None:
        """Emit a warning log message."""
        if self._session_ok and self._ctx is not None:
            try:
                warn_method = getattr(self._ctx, "warning", None)
                if warn_method is not None:
                    await warn_method(message)
                else:
                    await self._ctx.info(f"WARNING: {message}")
                return
            except Exception as exc:
                _log.debug("ctx.warn failed (%s); falling back to stdlib log", exc)
                self._session_ok = False
        _log.warning(message)

    async def progress(self, current: int, total: int) -> None:
        """Report progress if an MCP session is available."""
        if self._session_ok and self._ctx is not None:
            try:
                await self._ctx.report_progress(current, total)
            except Exception as exc:
                _log.debug("ctx.progress failed (%s); skipping", exc)
                self._session_ok = False

    async def elicit(
        self,
        message: str,
        *,
        response_type: type | None = None,
        default: Any = None,
    ) -> Any:
        """Ask the client for a decision, returning ``default`` when offline.

        Elicitation is impossible without an MCP session — there's no client
        to talk to — so we return ``default`` immediately in REST/no-session
        mode rather than raising.
        """
        if not self._session_ok or self._ctx is None:
            return default
        try:
            return await self._ctx.elicit(message, response_type)  # type: ignore[arg-type]
        except Exception as exc:
            _log.debug("ctx.elicit failed (%s); returning default", exc)
            return default

    async def confirm(self, message: str, *, default: bool = False) -> bool | None:
        """Ask user for yes/no confirmation. Returns True/False/None(cancelled)."""
        from app.controllers.elicitation import safe_confirm

        return await safe_confirm(self._ctx, message, default=default)

    async def choice(
        self,
        message: str,
        choices: list[str],
        *,
        default: str | None = None,
    ) -> str | None:
        """Ask user to pick from a list. Returns selected string or None."""
        from app.controllers.elicitation import safe_choice

        return await safe_choice(self._ctx, message, choices, default=default)

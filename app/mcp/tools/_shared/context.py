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

from typing import Any

from fastmcp.server.context import Context


class ToolContext:
    """Null-safe facade around FastMCP :class:`Context`.

    Implements the GoF Facade / Null-Object hybrid: when the underlying
    context is absent every method becomes a silent no-op.
    """

    __slots__ = ("_ctx",)

    def __init__(self, ctx: Context | None) -> None:
        self._ctx = ctx

    @property
    def active(self) -> bool:
        """``True`` if a real FastMCP context is attached."""
        return self._ctx is not None

    @property
    def raw(self) -> Context | None:
        """Escape hatch for code that needs the underlying Context instance."""
        return self._ctx

    async def info(self, message: str) -> None:
        """Emit an informational log message if a context is available."""
        if self._ctx is not None:
            await self._ctx.info(message)

    async def warn(self, message: str) -> None:
        """Emit a warning log message if a context is available."""
        if self._ctx is not None:
            # FastMCP Context exposes .warning, fall back to .info otherwise.
            warn_method = getattr(self._ctx, "warning", None)
            if warn_method is not None:
                await warn_method(message)
            else:
                await self._ctx.info(f"WARNING: {message}")

    async def progress(self, current: int, total: int) -> None:
        """Report progress if a context is available."""
        if self._ctx is not None:
            await self._ctx.report_progress(current, total)

    async def elicit(
        self,
        message: str,
        *,
        response_type: type | None = None,
        default: Any = None,
    ) -> Any:
        """Ask the client for a decision, returning ``default`` when offline.

        ``response_type`` is forwarded to FastMCP's :meth:`Context.elicit`;
        when ``None`` the underlying API accepts a plain string answer.
        """
        if self._ctx is None:
            return default
        # FastMCP's elicit has multiple overloads; forwarding response_type
        # as-is is intentional — ``type[T] | None`` is the default branch.
        return await self._ctx.elicit(message, response_type)  # type: ignore[arg-type]

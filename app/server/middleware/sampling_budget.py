"""Cap ``ctx.sample()`` invocations per MCP session.

The server-side LLM fallback (``app/v2/server/sampling.py``) calls
``middleware.note_sample(ctx)`` before actually hitting the Anthropic API.
If the session has exceeded its budget, ``SamplingBudgetExceeded`` is raised
and the handler should fall back to "please provide queries as a tool param".
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.config import get_settings


class SamplingBudgetExceeded(Exception):  # noqa: N818 — plan-defined name
    """Raised when a session has used up its sampling budget."""


class SamplingBudgetMiddleware(Middleware):
    def __init__(self, *, max_samples_per_session: int | None = None) -> None:
        if max_samples_per_session is None:
            max_samples_per_session = get_settings().mcp.sampling_max_per_session
        self.max_samples_per_session = max_samples_per_session
        self._used: dict[str, int] = {}

    def note_sample(self, ctx: Any) -> None:
        """Called by the sampling handler before dispatching to Anthropic."""
        fctx = ctx.fastmcp_context if hasattr(ctx, "fastmcp_context") else ctx
        session = getattr(fctx, "session_id", None) or "__global__"
        used = self._used.get(session, 0)
        if used >= self.max_samples_per_session:
            raise SamplingBudgetExceeded(
                f"session {session}: sampling budget of {self.max_samples_per_session} exceeded"
            )
        self._used[session] = used + 1

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if context.fastmcp_context is not None:
            await context.fastmcp_context.set_state("sampling_budget", self, serializable=False)
        return await call_next(context)

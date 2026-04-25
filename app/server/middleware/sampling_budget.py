"""Cap ``ctx.sample()`` invocations per MCP session.

The server-side LLM fallback (``app/v2/server/sampling.py``) calls
``middleware.note_sample(ctx)`` before actually hitting the Anthropic API.
If the session has exceeded its budget, ``SamplingBudgetExceeded`` is raised
and the handler should fall back to "please provide queries as a tool param".

Two failure modes the original implementation had:

* The ``_used`` ``dict`` grew without bound — one bucket per MCP session
  over a long-running server adds up. Now bounded by
  ``MCPSettings.sampling_buckets_max`` via an in-process LRU
  (``OrderedDict``) — oldest entries are evicted when the cap is hit.
* All stateless callers bucketed under ``"__global__"``, so the
  per-session cap was applied to every REST/in-process caller in
  aggregate — once exhausted, every stateless call failed forever.
  A SEPARATE ``MCPSettings.sampling_global_cap`` now governs the
  stateless bucket; it is intentionally larger than the per-session
  cap.
"""

from __future__ import annotations

import contextlib
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.config import get_settings

log = logging.getLogger(__name__)

_STATELESS_BUCKET = "__global__"


class SamplingBudgetExceeded(Exception):  # noqa: N818 — plan-defined name
    """Raised when a session has used up its sampling budget."""


class SamplingBudgetMiddleware(Middleware):
    def __init__(
        self,
        *,
        max_samples_per_session: int | None = None,
        global_cap: int | None = None,
        buckets_max: int | None = None,
    ) -> None:
        cfg = get_settings().mcp
        if max_samples_per_session is None:
            max_samples_per_session = cfg.sampling_max_per_session
        self.max_samples_per_session = max_samples_per_session
        self.global_cap = global_cap if global_cap is not None else cfg.sampling_global_cap
        self.buckets_max = buckets_max if buckets_max is not None else cfg.sampling_buckets_max
        # OrderedDict-backed bounded LRU. Drops the oldest session bucket
        # when ``buckets_max`` is exceeded — keeps memory flat without
        # adding cachetools as a hard dependency.
        self._used: OrderedDict[str, int] = OrderedDict()
        # Dedupe per-threshold WARN logs for the stateless bucket so a
        # noisy caller does not flood the log stream.
        self._stateless_threshold_warned: set[int] = set()

    def _bump(self, session: str, cap: int) -> None:
        used = self._used.get(session, 0)
        if used >= cap:
            raise SamplingBudgetExceeded(f"session {session}: sampling budget of {cap} exceeded")
        self._used[session] = used + 1
        # LRU touch — move the key to the most-recently-used end.
        self._used.move_to_end(session)
        # Bound size; pop oldest if we are over budget.
        while len(self._used) > self.buckets_max:
            self._used.popitem(last=False)

    def _warn_stateless_thresholds(self, used_after: int) -> None:
        if self.global_cap <= 0:
            return
        ratio = used_after / self.global_cap
        for threshold in (50, 80, 100):
            if ratio * 100 >= threshold and threshold not in self._stateless_threshold_warned:
                self._stateless_threshold_warned.add(threshold)
                log.warning(
                    "stateless sampling bucket at %d%% of global cap (%d/%d)",
                    threshold,
                    used_after,
                    self.global_cap,
                )

    def note_sample(self, ctx: Any) -> None:
        """Called by the sampling handler before dispatching to Anthropic."""
        fctx = ctx.fastmcp_context if hasattr(ctx, "fastmcp_context") else ctx
        try:
            session = getattr(fctx, "session_id", None) or _STATELESS_BUCKET
        except (RuntimeError, AttributeError):
            # Stateless context — bucket all stateless calls together.
            session = _STATELESS_BUCKET

        if session == _STATELESS_BUCKET:
            self._bump(session, self.global_cap)
            self._warn_stateless_thresholds(self._used.get(session, 0))
        else:
            self._bump(session, self.max_samples_per_session)

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if context.fastmcp_context is not None:
            # Stateless context (REST/in-process): set_state raises
            # ``RuntimeError`` because there is no MCP session to scope the
            # key to. Cap-enforcement is best-effort observability — pass
            # through.
            with contextlib.suppress(RuntimeError):
                await context.fastmcp_context.set_state(
                    "sampling_budget", self, serializable=False
                )
        return await call_next(context)

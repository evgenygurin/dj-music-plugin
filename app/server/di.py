"""Dependency-injection factories for Phase 3 tools.

Each factory reads a slot from ``ctx.fastmcp_context.state`` — slots are
populated by middleware (``DbSessionMiddleware`` sets ``uow``) or by the
server lifespan (registries, pipelines, session store).

Two calling conventions are supported:

1. **FastMCP runtime** — factories called with no args. We look up the
   active context via ``fastmcp.server.dependencies.get_context``.
2. **Tests / direct** — pass the ctx explicitly: ``get_uow(ctx)``.

Raises ``RuntimeError`` with a clear message when a slot is missing so
wiring bugs surface early.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.registry.provider import ProviderRegistry
    from app.repositories.unit_of_work import UnitOfWork


def _active_context() -> Any:
    """Return the current FastMCP context (via runtime accessor)."""
    try:
        from fastmcp.server.dependencies import get_context
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("fastmcp.server.dependencies.get_context missing") from exc
    return get_context()


import inspect


async def _read_slot(ctx: Any, key: str, what: str) -> Any:
    """Read ``ctx.fastmcp_context`` state slot or raise a descriptive error.

    FastMCP 3.x exposes state via async ``get_state(key)``. Legacy/test
    contexts may expose a plain dict ``.state``. Both are supported.
    """
    if ctx is None:
        ctx = _active_context()

    fastmcp_ctx = getattr(ctx, "fastmcp_context", ctx)
    value: Any = None
    getter = getattr(fastmcp_ctx, "get_state", None)
    if callable(getter):
        try:
            result = getter(key)
            value = await result if inspect.isawaitable(result) else result
        except Exception:
            value = None
    if value is None:
        state = getattr(fastmcp_ctx, "state", None)
        if state is not None and hasattr(state, "get"):
            value = state.get(key)
    if value is None:
        raise RuntimeError(
            f"{what} not initialized — check lifespan composition or DbSessionMiddleware"
        )
    return value


async def get_uow(ctx: Any = None) -> UnitOfWork:
    """Return the per-tool-call UnitOfWork set by DbSessionMiddleware."""
    try:
        uow_value: UnitOfWork = await _read_slot(ctx, "uow", "UnitOfWork")
        return uow_value
    except RuntimeError:
        # Stateless ContextVar fallback (REST/in-process — no MCP session).
        from app.server.middleware.db_session import read_stateless_uow

        uow = read_stateless_uow()
        if uow is not None:
            return uow
        raise


async def get_provider_registry(ctx: Any = None) -> ProviderRegistry:
    """Return the ProviderRegistry populated by provider_lifespan."""
    registry: ProviderRegistry = _read_lifespan(ctx, "provider_registry", "ProviderRegistry")
    return registry


async def get_analyzer_registry(ctx: Any = None) -> Any:
    """Return the AnalyzerRegistry populated by audio_lifespan."""
    return _read_lifespan(ctx, "analyzer_registry", "AnalyzerRegistry")


async def get_audio_pipeline(ctx: Any = None) -> Any:
    """Return the AnalysisPipeline populated by audio_lifespan."""
    return _read_lifespan(ctx, "audio_pipeline", "AnalysisPipeline")


async def get_session_store(ctx: Any = None) -> Any:
    """Return the SessionStore populated by session_store_lifespan."""
    return _read_lifespan(ctx, "session_store", "SessionStore")


def _read_lifespan(ctx: Any, key: str, what: str) -> Any:
    """Read lifespan-yielded state (request_context.lifespan_context[key])."""
    if ctx is None:
        ctx = _active_context()
    fctx = getattr(ctx, "fastmcp_context", ctx)
    rc = getattr(fctx, "request_context", None)
    lc = getattr(rc, "lifespan_context", None) if rc is not None else None
    value = lc.get(key) if isinstance(lc, dict) else None
    if value is None:
        # REST/in-process fallback — REST lifespan populates this store
        # because it does not enter MCP's own lifespan.
        from app.server._stateless_state import get_state

        value = get_state(key)
    if value is None:
        raise RuntimeError(f"{what} not initialized — check scoring_lifespan composition")
    return value


async def get_transition_scorer(ctx: Any = None) -> Any:
    """Return the TransitionScorer populated by scoring_lifespan."""
    return _read_lifespan(ctx, "transition_scorer", "TransitionScorer")


async def get_optimizer(ctx: Any = None) -> Any:
    """Return the optimizer factory populated by scoring_lifespan."""
    return _read_lifespan(ctx, "optimizer", "Optimizer")


async def get_provider_registry_from_lifespan(ctx: Any = None) -> Any:
    return _read_lifespan(ctx, "provider_registry", "ProviderRegistry")

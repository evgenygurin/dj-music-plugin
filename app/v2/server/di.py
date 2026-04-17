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
    from app.v2.registry.provider import ProviderRegistry
    from app.v2.repositories.unit_of_work import UnitOfWork


def _active_context() -> Any:
    """Return the current FastMCP context (via runtime accessor)."""
    try:
        from fastmcp.server.dependencies import get_context
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("fastmcp.server.dependencies.get_context missing") from exc
    return get_context()


def _read_slot(ctx: Any, key: str, what: str) -> Any:
    """Read ``ctx.fastmcp_context.state[key]`` or raise a descriptive error.

    Accepts either a fastmcp Context-like object (with ``.fastmcp_context.state``)
    or a test-shaped ``SimpleNamespace(fastmcp_context=SimpleNamespace(state=...))``.
    If ``ctx`` is None, fall back to the runtime-active context.
    """
    if ctx is None:
        ctx = _active_context()

    fastmcp_ctx = getattr(ctx, "fastmcp_context", ctx)
    state = getattr(fastmcp_ctx, "state", None)
    if state is None:
        raise RuntimeError(
            f"{what} not initialized — check lifespan composition or DbSessionMiddleware"
        )
    value = state.get(key) if hasattr(state, "get") else None
    if value is None:
        raise RuntimeError(
            f"{what} not initialized — check lifespan composition or DbSessionMiddleware"
        )
    return value


def get_uow(ctx: Any = None) -> UnitOfWork:
    """Return the per-tool-call UnitOfWork set by DbSessionMiddleware."""
    return _read_slot(ctx, "uow", "UnitOfWork")


def get_provider_registry(ctx: Any = None) -> ProviderRegistry:
    """Return the ProviderRegistry populated by provider_lifespan."""
    return _read_slot(ctx, "provider_registry", "ProviderRegistry")


def get_analyzer_registry(ctx: Any = None) -> Any:
    """Return the AnalyzerRegistry populated by audio_lifespan."""
    return _read_slot(ctx, "analyzer_registry", "AnalyzerRegistry")


def get_audio_pipeline(ctx: Any = None) -> Any:
    """Return the AnalysisPipeline populated by audio_lifespan."""
    return _read_slot(ctx, "audio_pipeline", "AnalysisPipeline")


def get_session_store(ctx: Any = None) -> Any:
    """Return the SessionStore populated by session_store_lifespan."""
    return _read_slot(ctx, "session_store", "SessionStore")


def get_transition_scorer(ctx: Any = None) -> Any:
    """Return the TransitionScorer populated by the scoring lifespan / middleware."""
    return _read_slot(ctx, "transition_scorer", "TransitionScorer")


def get_optimizer(ctx: Any = None) -> Any:
    """Return the optimizer factory populated by lifespan state."""
    return _read_slot(ctx, "optimizer", "Optimizer")

"""Dependency injection factories for MCP tools.

Phase 3 ships stubs; Phase 5 wires the real implementations (DbSession
middleware sets UoW on ctx, ProviderRegistry comes from lifespan, etc.).

Tests monkey-patch ``get_uow`` / ``get_provider_registry`` directly.
"""

from __future__ import annotations

from typing import Any

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork


def get_uow() -> UnitOfWork:
    """Return the current UoW.

    Phase 5 replaces this with middleware-backed retrieval from
    ``ctx.fastmcp_context.state["uow"]``. Phase 3 uses test monkey-patching.
    """
    raise RuntimeError("get_uow is a Phase 5 stub — tests must monkey-patch this symbol.")


def get_provider_registry() -> ProviderRegistry:
    """Return the provider registry from lifespan state.

    Phase 5 replaces this with real lifespan context extraction.
    """
    raise RuntimeError(
        "get_provider_registry is a Phase 5 stub — tests must monkey-patch this symbol."
    )


def get_analyzer_registry() -> Any:
    """Placeholder for Phase 5 — audio analyzer registry."""
    raise RuntimeError("get_analyzer_registry is a Phase 5 stub — tests must monkey-patch.")


def get_audio_pipeline() -> Any:
    """Placeholder for Phase 5 — audio pipeline."""
    raise RuntimeError("get_audio_pipeline is a Phase 5 stub — tests must monkey-patch.")


def get_transition_scorer() -> Any:
    """Placeholder for Phase 5 — transition scorer."""
    raise RuntimeError("get_transition_scorer is a Phase 5 stub — tests must monkey-patch.")


def get_optimizer() -> Any:
    """Placeholder for Phase 5 — optimizer builder."""
    raise RuntimeError("get_optimizer is a Phase 5 stub — tests must monkey-patch.")


def get_session_store() -> Any:
    """Placeholder for Phase 5 — session store.

    Phase 4 adds the in-memory implementation in
    ``app.v2.server.session_store``. Phase 5 wires a real singleton via
    lifespan state; tests inject a store directly.
    """
    raise RuntimeError(
        "get_session_store is a Phase 5 stub — tests must monkey-patch this symbol."
    )

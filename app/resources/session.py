"""Session-scoped resources — draft, tool-history, energy trend.

URIs:
    session://set-draft
    session://tool-history
    session://energy-trend{?limit}

All three read from ``InMemorySessionStore`` keyed by the current FastMCP
``session_id``. These resources MUST NOT be cached by
``ResponseCachingMiddleware`` — state changes per call.
"""

from __future__ import annotations

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.resources import resource
from fastmcp.server.context import Context

from app.resources._shared import RESOURCE_META
from app.schemas.resource_views import (
    SessionDraftView,
    SessionEnergyTrendView,
    SessionToolHistoryView,
)
from app.server.di import get_session_store
from app.server.session_store import InMemorySessionStore

# session:// resources read volatile state, so idempotentHint=False.
_SESSION_ANNOTATIONS = {"readOnlyHint": True, "idempotentHint": False}


def _session_id(ctx: Context) -> str:
    return getattr(ctx, "session_id", None) or "anonymous"


@resource(
    "session://set-draft",
    mime_type="application/json",
    tags={"core", "namespace:session", "view:set_draft"},
    annotations=_SESSION_ANNOTATIONS,
    meta=RESOURCE_META,
)
async def session_set_draft(
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Current ephemeral set draft for this session."""
    d = store.get_draft(_session_id(ctx))
    return SessionDraftView(
        session_id=d.get("session_id", _session_id(ctx)),
        tracks=d.get("tracks", []),
        target_duration_ms=d.get("target_duration_ms"),
        template_name=d.get("template_name"),
        last_mutation_at=d.get("last_mutation_at"),
    ).model_dump_json()


@resource(
    "session://tool-history",
    mime_type="application/json",
    tags={"core", "namespace:session", "view:tool_history"},
    annotations=_SESSION_ANNOTATIONS,
    meta=RESOURCE_META,
)
async def session_tool_history(
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Recent tool calls for this session."""
    sid = _session_id(ctx)
    return SessionToolHistoryView(
        session_id=sid,
        entries=store.get_tool_history(sid),
    ).model_dump_json()


@resource(
    "session://energy-trend{?limit}",
    mime_type="application/json",
    tags={"core", "namespace:session", "view:energy_trend"},
    annotations=_SESSION_ANNOTATIONS,
    meta=RESOURCE_META,
)
async def session_energy_trend(
    limit: int = 20,
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Last ``limit`` energy samples recorded for this session (LUFS)."""
    sid = _session_id(ctx)
    return SessionEnergyTrendView(
        last_n=limit,
        samples=store.get_energy_samples(sid, last_n=limit),
    ).model_dump_json()

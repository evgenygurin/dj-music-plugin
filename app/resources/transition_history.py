"""Transition history resources — crowd-tested pair stats + recent log.

URIs:
    local://transition_history/best_pairs{?track_id,limit}
    local://transition_history/history{?limit,track_id}
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.schemas.resource_views import BestPairsView, TransitionHistoryView
from app.server.di import get_uow


def _row_to_pair(row: Any) -> dict[str, Any]:
    # Repo may return ORM model (has attrs) or dict (future shape).
    if isinstance(row, dict):
        return {
            "from_track_id": row.get("from_track_id"),
            "to_track_id": row.get("to_track_id"),
            "plays": row.get("plays"),
            "avg_reaction": row.get("avg_reaction"),
            "overall_score": row.get("overall_score"),
        }
    return {
        "from_track_id": getattr(row, "from_track_id", None),
        "to_track_id": getattr(row, "to_track_id", None),
        "plays": getattr(row, "plays", None),
        "avg_reaction": getattr(row, "avg_reaction", None),
        "overall_score": getattr(row, "overall_score", None),
    }


def _row_to_entry(row: Any) -> dict[str, Any]:
    at = (
        getattr(row, "at", None)
        or getattr(row, "played_at", None)
        or getattr(row, "created_at", None)
    )
    return {
        "id": getattr(row, "id", None),
        "from_track_id": getattr(row, "from_track_id", None),
        "to_track_id": getattr(row, "to_track_id", None),
        "at": at.isoformat() if at is not None and hasattr(at, "isoformat") else at,
        "reaction": getattr(row, "reaction", None),
        "overall_score": getattr(row, "overall_score", None),
        "style": getattr(row, "style", None),
    }


@resource(
    "local://transition_history/best_pairs{?track_id,limit}",
    mime_type="application/json",
    tags={"core", "namespace:memory", "view:best_pairs"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_history_best_pairs(
    track_id: int | None = None,
    limit: int = 10,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Best-performing pairs. Optional ``track_id`` filter keeps only pairs
    involving that track."""
    fn = getattr(uow.transition_history, "best_pairs", None)
    rows: list[Any] = list(await fn(limit=limit * 3)) if fn is not None else []
    if track_id is not None:
        rows = [
            r
            for r in rows
            if getattr(r, "from_track_id", None) == track_id
            or getattr(r, "to_track_id", None) == track_id
        ]
    pairs = [_row_to_pair(r) for r in rows[:limit]]
    return BestPairsView(limit=limit, pairs=pairs).model_dump_json()


@resource(
    "local://transition_history/history{?limit,track_id}",
    mime_type="application/json",
    tags={"core", "namespace:memory", "view:history"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_history_log(
    limit: int = 50,
    track_id: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Recent transition log entries, most-recent first.

    ``recent`` on the repo is a Phase 5 gap — falls back to ``best_pairs``
    until filled."""
    recent = getattr(uow.transition_history, "recent", None)
    if recent is not None:
        rows = list(await recent(limit=limit * 3))
    else:
        fn = getattr(uow.transition_history, "best_pairs", None)
        rows = list(await fn(limit=limit * 3)) if fn is not None else []
    if track_id is not None:
        rows = [
            r
            for r in rows
            if getattr(r, "from_track_id", None) == track_id
            or getattr(r, "to_track_id", None) == track_id
        ]
    entries = [_row_to_entry(r) for r in rows[:limit]]
    return TransitionHistoryView(limit=limit, entries=entries).model_dump_json()

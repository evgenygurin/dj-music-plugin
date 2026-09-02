"""TrackRenderContext — single load of all per-track render data (§3.4).

Graceful fallback: if any table / feature is missing the builder returns
AvailableData with all flags False and the policies no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.render.stem_policy.models import AvailableData


@dataclass(frozen=True, slots=True)
class TrackRenderContext:
    """All data needed for a full stem render, loaded in one pass."""

    # identifiers
    version_id: int
    track_ids: tuple[int, ...] = ()
    # raw feature blobs (track_id → dict or None)
    track_features: dict[int, dict[str, Any]] = field(default_factory=dict)
    stem_features: dict[int, dict[str, dict[str, Any]]] = field(default_factory=dict)
    beatgrids: dict[int, dict[str, Any]] = field(default_factory=dict)
    # optional collections
    sections: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    cue_points: dict[int, dict[str, Any]] = field(default_factory=dict)
    affinities: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    feedback: dict[int, dict[str, Any]] = field(default_factory=dict)
    embeddings: dict[int, list[float]] = field(default_factory=dict)
    cross_similarity: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    # render knobs
    subgenre: str = "hypnotic_techno"
    user_overrides: dict[str, Any] = field(default_factory=dict)
    base_transition_s: float = 8.0
    base_body_s: float = 0.0
    target_bpm: float = 130.0
    available: AvailableData = field(default_factory=AvailableData)


class TrackRenderContextBuilder:
    """Load TrackRenderContext in one async pass.

    IO-bound queries are gathered in parallel; any failure degrades to
    available=False so policies fall back to defaults (design §5).
    """

    async def build(
        self,
        uow: Any,  # UnitOfWork
        version_id: int,
        *,
        subgenre: str | None = None,
        user_overrides: dict[str, Any] | None = None,
        target_bpm: float = 130.0,
    ) -> TrackRenderContext:
        # Skeleton implementation: no DB round-trips yet, return empty context.
        # Full implementation will asyncio.gather 6 queries (features, stems,
        # beatgrids, sections, affinities, embeddings) per spec §3.4.
        # Keeping it graceful keeps the offline render path pure and testable.
        try:
            # Try to pull track_ids from the version if UoW is available
            track_ids: tuple[int, ...] = ()
            if hasattr(uow, "session") and uow.session is not None:
                # Best-effort: read set version items without failing the render
                from sqlalchemy import select

                try:
                    from app.models.set import DjSetItem

                    stmt = (
                        select(DjSetItem.track_id)
                        .where(DjSetItem.version_id == version_id)
                        .order_by(DjSetItem.sort_index)
                    )
                    rows = (await uow.session.execute(stmt)).scalars().all()
                    if rows:
                        track_ids = tuple(int(x) for x in rows)
                except Exception:
                    track_ids = ()
        except Exception:
            track_ids = ()

        return TrackRenderContext(
            version_id=version_id,
            track_ids=track_ids,
            subgenre=subgrade if (subgrade := subgenre) else "hypnotic_techno",
            user_overrides=user_overrides or {},
            target_bpm=target_bpm,
            available=AvailableData(),
        )


__all__ = ["TrackRenderContext", "TrackRenderContextBuilder"]

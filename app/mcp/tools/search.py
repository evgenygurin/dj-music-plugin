"""Search and filter tools: cross-entity text search + parametric track filter."""

from __future__ import annotations

from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import func, select

from app.core.camelot import camelot_to_key_code, is_compatible
from app.core.constants import KEY_CODE_MAX, KEY_CODE_MIN
from app.core.pagination import decode_cursor, encode_cursor
from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist
from app.models.set import DjSet
from app.models.track import Artist, Track


async def _get_session(ctx: Context | None):  # type: ignore[no-untyped-def]
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def search(
    query: str,
    entity: str = "all",
    limit: int = 10,
    ctx: Context | None = None,
) -> dict:
    """Search across tracks, artists, playlists, and sets by text query."""
    if not query or not query.strip():
        return {"error": "Query must not be empty"}

    pattern = f"%{query.strip()}%"
    results: dict[str, list[dict]] = {}

    async with await _get_session(ctx) as session:
        entities = [entity] if entity != "all" else ["tracks", "artists", "playlists", "sets"]

        if "tracks" in entities:
            stmt = select(Track).where(Track.title.ilike(pattern)).order_by(Track.id).limit(limit)
            rows = await session.execute(stmt)
            results["tracks"] = [
                {"id": t.id, "title": t.title, "duration_ms": t.duration_ms}
                for t in rows.scalars().all()
            ]

        if "artists" in entities:
            stmt = (
                select(Artist).where(Artist.name.ilike(pattern)).order_by(Artist.id).limit(limit)
            )
            rows = await session.execute(stmt)
            results["artists"] = [{"id": a.id, "name": a.name} for a in rows.scalars().all()]

        if "playlists" in entities:
            stmt = (
                select(Playlist)
                .where(Playlist.name.ilike(pattern))
                .order_by(Playlist.id)
                .limit(limit)
            )
            rows = await session.execute(stmt)
            results["playlists"] = [{"id": p.id, "name": p.name} for p in rows.scalars().all()]

        if "sets" in entities:
            stmt = select(DjSet).where(DjSet.name.ilike(pattern)).order_by(DjSet.id).limit(limit)
            rows = await session.execute(stmt)
            results["sets"] = [{"id": s.id, "name": s.name} for s in rows.scalars().all()]

    total = sum(len(v) for v in results.values())
    return {"query": query, "total": total, "results": results}


def _compatible_key_codes(notation: str) -> list[int]:
    """Return all key_codes compatible with the given Camelot notation."""
    try:
        base_code = camelot_to_key_code(notation.upper())
    except ValueError:
        return []
    return [
        code for code in range(KEY_CODE_MIN, KEY_CODE_MAX + 1) if is_compatible(base_code, code)
    ]


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def filter_tracks(
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    key: str | None = None,
    key_compatible: str | None = None,
    energy_min: float | None = None,
    energy_max: float | None = None,
    has_features: bool | None = None,
    exclude_set_id: int | None = None,
    sort_by: str = "bpm",
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Filter tracks by audio features: BPM, key, energy, mood."""
    async with await _get_session(ctx) as session:
        # Base query: join tracks with audio features
        if has_features is False:
            # Tracks WITHOUT features: left join + NULL check
            stmt = (
                select(Track)
                .outerjoin(
                    TrackAudioFeaturesComputed,
                    TrackAudioFeaturesComputed.track_id == Track.id,
                )
                .where(TrackAudioFeaturesComputed.track_id.is_(None))
            )
        else:
            stmt = select(Track).join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )

        # BPM filters
        if bpm_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
        if bpm_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)

        # Exact key filter (Camelot notation -> key_code)
        if key is not None:
            try:
                code = camelot_to_key_code(key.upper())
                stmt = stmt.where(TrackAudioFeaturesComputed.key_code == code)
            except ValueError:
                return {"error": f"Invalid Camelot key: {key!r}"}

        # Compatible key filter
        if key_compatible is not None:
            codes = _compatible_key_codes(key_compatible)
            if not codes:
                return {"error": f"Invalid Camelot key: {key_compatible!r}"}
            stmt = stmt.where(TrackAudioFeaturesComputed.key_code.in_(codes))

        # Energy filters
        if energy_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean >= energy_min)
        if energy_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean <= energy_max)

        # Exclude tracks already in a set
        if exclude_set_id is not None:
            from app.models.set import SetItem, SetVersion

            latest_version = (
                select(SetVersion.id)
                .where(SetVersion.set_id == exclude_set_id)
                .order_by(SetVersion.id.desc())
                .limit(1)
                .scalar_subquery()
            )
            existing_track_ids = select(SetItem.track_id).where(
                SetItem.version_id == latest_version
            )
            stmt = stmt.where(Track.id.not_in(existing_track_ids))

        # Sorting
        sort_map = {
            "bpm": TrackAudioFeaturesComputed.bpm,
            "energy": TrackAudioFeaturesComputed.energy_mean,
            "title": Track.title,
            "id": Track.id,
        }
        order_col = sort_map.get(sort_by, TrackAudioFeaturesComputed.bpm)
        stmt = stmt.order_by(order_col)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar_one()

        # Cursor pagination
        if cursor is not None:
            last_id = decode_cursor(cursor)
            stmt = stmt.where(Track.id > last_id)

        stmt = stmt.order_by(Track.id).limit(limit)
        result = await session.execute(stmt)
        tracks = list(result.scalars().all())

        next_cursor: str | None = None
        if tracks and len(tracks) == limit:
            next_cursor = encode_cursor(tracks[-1].id)

        return {
            "items": [
                {"id": t.id, "title": t.title, "duration_ms": t.duration_ms} for t in tracks
            ],
            "next_cursor": next_cursor,
            "total": total,
        }

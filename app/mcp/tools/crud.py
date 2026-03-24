"""CRUD tools for tracks, playlists, and sets (10 tools, tag: core)."""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.schemas import (
    PaginatedResponse,
    PlaylistSummary,
    SetSummary,
    TrackBrief,
    TrackStandard,
)
from app.models.audio import TrackAudioFeaturesComputed, TrackSection
from app.models.playlist import Playlist
from app.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from app.models.track import Track
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.server import mcp

# ── Helpers ──────────────────────────────────────────


async def _get_session(ctx: Context | None) -> AsyncSession:
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required — tools must be called via MCP")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


def _track_brief(t: Track) -> dict[str, Any]:
    """Convert Track model to TrackBrief dict."""
    return TrackBrief(
        id=t.id,
        title=t.title,
        artist_names=[],  # requires eager-loading track_artists
        bpm=None,
        key_camelot=None,
        duration_ms=t.duration_ms,
    ).model_dump()


def _track_standard(
    t: Track, features: TrackAudioFeaturesComputed | None = None
) -> dict[str, Any]:
    """Convert Track model to TrackStandard dict."""
    return TrackStandard(
        id=t.id,
        title=t.title,
        artist_names=[],
        bpm=features.bpm if features else None,
        key_camelot=None,
        duration_ms=t.duration_ms,
        energy_lufs=features.integrated_lufs if features else None,
        mood=None,
        status=t.status,
        has_features=features is not None,
    ).model_dump()


def _playlist_summary(p: Playlist, track_count: int | None = None) -> dict[str, Any]:
    """Convert Playlist model to PlaylistSummary dict.

    If track_count is not provided, attempts to read from items relationship.
    Pass track_count=0 for newly created playlists to avoid lazy loading.
    """
    if track_count is None:
        try:
            track_count = len(p.items) if p.items else 0
        except Exception:
            track_count = 0
    return PlaylistSummary(
        id=p.id,
        name=p.name,
        track_count=track_count,
        source_of_truth=p.source_of_truth,
    ).model_dump()


def _set_summary(s: DjSet, version: SetVersion | None = None) -> dict[str, Any]:
    """Convert DjSet model to SetSummary dict."""
    return SetSummary(
        id=s.id,
        name=s.name,
        track_count=len(version.items) if version and version.items else 0,
        template=s.template_name,
        latest_score=version.quality_score if version else None,
    ).model_dump()


# ── 1. list_tracks ──────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    mood: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    status: str = "active",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List tracks with optional filters and cursor pagination."""
    async with await _get_session(ctx) as session:
        repo = TrackRepository(session)

        if bpm_min is not None or bpm_max is not None:
            page = await repo.filter_by_features(
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                limit=limit,
                cursor=cursor,
            )
        else:
            page = await repo.list_all(limit=limit, cursor=cursor)

        return PaginatedResponse[TrackBrief](
            items=[
                TrackBrief(
                    id=t.id,
                    title=t.title,
                    artist_names=[],
                    bpm=None,
                    key_camelot=None,
                    duration_ms=t.duration_ms,
                )
                for t in page.items
            ],
            next_cursor=page.next_cursor,
            total=page.total,
        ).model_dump()


# ── 2. get_track ────────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_track(
    id: int | None = None,
    query: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get full track details by id or text query."""
    if id is None and query is None:
        return {"error": "Provide id or query"}

    async with await _get_session(ctx) as session:
        repo = TrackRepository(session)

        track: Track | None = None
        if id is not None:
            track = await repo.get_by_id(id)
        elif query is not None:
            results = await repo.search_by_text(query, limit=1)
            track = results[0] if results else None

        if track is None:
            return {"error": "Track not found"}

        # Try to load audio features
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track.id
        )
        result = await session.execute(stmt)
        features = result.scalar_one_or_none()

        return _track_standard(track, features)


# ── 3. manage_tracks ────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_tracks(
    action: str,
    data: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Create, update, archive, or unarchive a track. action: create|update|archive|unarchive."""
    if action not in ("create", "update", "archive", "unarchive"):
        return {"error": f"Unknown action: {action}"}

    async with await _get_session(ctx) as session:
        repo = TrackRepository(session)

        if action == "create":
            if not data or "title" not in data:
                return {"error": "data.title required for create"}
            track = Track(
                title=data["title"],
                duration_ms=data.get("duration_ms"),
                status=0,
            )
            track = await repo.create(track)
            await session.commit()
            return _track_standard(track)

        if action in ("update", "archive", "unarchive"):
            track_id = (data or {}).get("id")
            if track_id is None:
                return {"error": "data.id required"}
            track = await repo.get_by_id(track_id)
            if track is None:
                return {"error": f"Track {track_id} not found"}

            if action == "archive":
                track.status = 1
            elif action == "unarchive":
                track.status = 0
            elif action == "update" and data:
                if "title" in data:
                    track.title = data["title"]
                if "duration_ms" in data:
                    track.duration_ms = data["duration_ms"]

            await repo.update(track)
            await session.commit()
            return _track_standard(track)

        return {"error": "Unreachable"}


# ── 4. list_playlists ───────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_playlists(
    source: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List playlists with optional source filter and cursor pagination."""
    async with await _get_session(ctx) as session:
        repo = PlaylistRepository(session)

        stmt = select(Playlist).options(selectinload(Playlist.items))
        if source is not None:
            stmt = stmt.where(Playlist.source_of_truth == source)

        page = await repo._paginate(stmt, limit=limit, cursor=cursor)

        return PaginatedResponse[PlaylistSummary](
            items=[
                PlaylistSummary(
                    id=p.id,
                    name=p.name,
                    track_count=len(p.items) if p.items else 0,
                    source_of_truth=p.source_of_truth,
                )
                for p in page.items
            ],
            next_cursor=page.next_cursor,
            total=page.total,
        ).model_dump()


# ── 5. get_playlist ─────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_playlist(
    id: int | None = None,
    query: str | None = None,
    include_tracks: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get playlist details by id or name query. Optionally include tracks."""
    if id is None and query is None:
        return {"error": "Provide id or query"}

    async with await _get_session(ctx) as session:
        repo = PlaylistRepository(session)

        playlist: Playlist | None = None
        if id is not None:
            playlist = await repo.get_with_items(id)
        elif query is not None:
            stmt = (
                select(Playlist)
                .where(Playlist.name.ilike(f"%{query}%"))
                .options(selectinload(Playlist.items))
                .limit(1)
            )
            result = await session.execute(stmt)
            playlist = result.scalar_one_or_none()

        if playlist is None:
            return {"error": "Playlist not found"}

        response: dict[str, Any] = _playlist_summary(playlist)

        if include_tracks and playlist.items:
            track_ids = [
                item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)
            ]
            tracks = []
            track_repo = TrackRepository(session)
            for tid in track_ids:
                t = await track_repo.get_by_id(tid)
                if t:
                    tracks.append(_track_brief(t))
            response["tracks"] = tracks

        return response


# ── 6. manage_playlist ──────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_playlist(
    action: str,
    data: dict[str, Any] | None = None,
    track_refs: list[int] | None = None,
    positions: list[int] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Manage playlists. action: create|update|delete|add_tracks|remove_tracks|reorder."""
    valid = ("create", "update", "delete", "add_tracks", "remove_tracks", "reorder")
    if action not in valid:
        return {"error": f"Unknown action: {action}. Valid: {', '.join(valid)}"}

    async with await _get_session(ctx) as session:
        repo = PlaylistRepository(session)

        if action == "create":
            if not data or "name" not in data:
                return {"error": "data.name required for create"}
            playlist = Playlist(
                name=data["name"],
                source_of_truth=data.get("source_of_truth", "local"),
            )
            playlist = await repo.create(playlist)
            await session.commit()
            return _playlist_summary(playlist, track_count=0)

        playlist_id = (data or {}).get("id")
        if playlist_id is None:
            return {"error": "data.id required"}

        if action == "delete":
            deleted = await repo.delete(playlist_id)
            await session.commit()
            return {"deleted": deleted, "id": playlist_id}

        playlist = await repo.get_with_items(playlist_id)
        if playlist is None:
            return {"error": f"Playlist {playlist_id} not found"}

        if action == "update":
            if data and "name" in data:
                playlist.name = data["name"]
            await repo.update(playlist)
            await session.commit()
            return _playlist_summary(playlist)

        if action == "add_tracks":
            if not track_refs:
                return {"error": "track_refs required for add_tracks"}
            max_idx = max((item.sort_index for item in playlist.items), default=-1)
            for i, tid in enumerate(track_refs):
                await repo.add_track(playlist_id, tid, max_idx + 1 + i)
            await session.commit()
            playlist = await repo.get_with_items(playlist_id)
            return _playlist_summary(playlist) if playlist else {"error": "Playlist lost"}

        if action == "remove_tracks":
            if not positions:
                return {"error": "positions required for remove_tracks"}
            removed = 0
            for pos in positions:
                if await repo.remove_track(playlist_id, pos):
                    removed += 1
            await session.commit()
            return {"removed": removed, "playlist_id": playlist_id}

        if action == "reorder":
            if not track_refs or not positions:
                return {"error": "track_refs and positions required for reorder"}
            # Clear existing items and re-add in new order
            for item in list(playlist.items):
                await session.delete(item)
            await session.flush()
            for tid, pos in zip(track_refs, positions, strict=False):
                await repo.add_track(playlist_id, tid, pos)
            await session.commit()
            playlist = await repo.get_with_items(playlist_id)
            return _playlist_summary(playlist) if playlist else {"error": "Playlist lost"}

        return {"error": "Unreachable"}


# ── 7. list_sets ────────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_sets(
    template: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List DJ sets with optional template filter and cursor pagination."""
    async with await _get_session(ctx) as session:
        repo = SetRepository(session)

        stmt = select(DjSet)
        if template is not None:
            stmt = stmt.where(DjSet.template_name == template)

        page = await repo._paginate(stmt, limit=limit, cursor=cursor)

        items = []
        for s in page.items:
            latest = await repo.get_latest_version(s.id)
            items.append(
                SetSummary(
                    id=s.id,
                    name=s.name,
                    track_count=0,
                    template=s.template_name,
                    latest_score=latest.quality_score if latest else None,
                )
            )

        return PaginatedResponse[SetSummary](
            items=items,
            next_cursor=page.next_cursor,
            total=page.total,
        ).model_dump()


# ── 8. get_set ──────────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_set(
    id: int | None = None,
    query: str | None = None,
    view: str = "summary",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get set details by id or query. view: summary|tracks|transitions|full."""
    if id is None and query is None:
        return {"error": "Provide id or query"}

    async with await _get_session(ctx) as session:
        repo = SetRepository(session)

        dj_set: DjSet | None = None
        if id is not None:
            dj_set = await repo.get_by_id(id)
        elif query is not None:
            stmt = select(DjSet).where(DjSet.name.ilike(f"%{query}%")).limit(1)
            result = await session.execute(stmt)
            dj_set = result.scalar_one_or_none()

        if dj_set is None:
            return {"error": "Set not found"}

        latest = await repo.get_latest_version(dj_set.id)
        response = _set_summary(dj_set, latest)

        if view in ("tracks", "full") and latest:
            stmt_items = (
                select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
            )
            result = await session.execute(stmt_items)
            items = list(result.scalars().all())

            track_repo = TrackRepository(session)
            tracks = []
            for item in items:
                t = await track_repo.get_by_id(item.track_id)
                if t:
                    tracks.append(
                        {
                            "position": item.sort_index,
                            "pinned": item.pinned,
                            **_track_brief(t),
                        }
                    )
            response["tracks"] = tracks

        if view in ("transitions", "full") and latest:
            response["version_id"] = latest.id
            response["version_label"] = latest.label
            response["quality_score"] = latest.quality_score

        return response


# ── 9. manage_set ───────────────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_set(
    action: str,
    data: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Manage DJ sets. Actions: create, update, delete, add/remove constraint, add feedback."""
    valid = ("create", "update", "delete", "add_constraint", "remove_constraint", "add_feedback")
    if action not in valid:
        return {"error": f"Unknown action: {action}. Valid: {', '.join(valid)}"}

    async with await _get_session(ctx) as session:
        repo = SetRepository(session)

        if action == "create":
            if not data or "name" not in data:
                return {"error": "data.name required for create"}
            dj_set = DjSet(
                name=data["name"],
                description=data.get("description"),
                target_duration_ms=data.get("target_duration_ms"),
                template_name=data.get("template"),
            )
            dj_set = await repo.create(dj_set)
            await session.commit()
            return _set_summary(dj_set)

        set_id = (data or {}).get("id")
        if set_id is None:
            return {"error": "data.id required"}

        if action == "delete":
            deleted = await repo.delete(set_id)
            await session.commit()
            return {"deleted": deleted, "id": set_id}

        dj_set = await repo.get_by_id(set_id)
        if dj_set is None:
            return {"error": f"Set {set_id} not found"}

        if action == "update":
            if data:
                if "name" in data:
                    dj_set.name = data["name"]
                if "description" in data:
                    dj_set.description = data["description"]
                if "template" in data:
                    dj_set.template_name = data["template"]
            await repo.update(dj_set)
            await session.commit()
            return _set_summary(dj_set)

        if action == "add_constraint":
            if not data or "constraint_type" not in data or "constraint_value" not in data:
                return {"error": "data.constraint_type and data.constraint_value required"}
            constraint = SetConstraint(
                set_id=set_id,
                constraint_type=data["constraint_type"],
                constraint_value=data["constraint_value"],
            )
            session.add(constraint)
            await session.flush()
            await session.commit()
            return {"constraint_id": constraint.id, "set_id": set_id}

        if action == "remove_constraint":
            constraint_id = (data or {}).get("constraint_id")
            if constraint_id is None:
                return {"error": "data.constraint_id required"}
            stmt = select(SetConstraint).where(SetConstraint.id == constraint_id)
            result = await session.execute(stmt)
            constraint = result.scalar_one_or_none()
            if constraint is None:
                return {"error": f"Constraint {constraint_id} not found"}
            await session.delete(constraint)
            await session.flush()
            await session.commit()
            return {"removed": True, "constraint_id": constraint_id}

        if action == "add_feedback":
            if not data or "version_id" not in data or "rating" not in data:
                return {"error": "data.version_id and data.rating required"}
            feedback = SetFeedback(
                version_id=data["version_id"],
                rating=data["rating"],
                feedback_type=data.get("feedback_type", "general"),
                notes=data.get("notes"),
                set_item_id=data.get("set_item_id"),
            )
            session.add(feedback)
            await session.flush()
            await session.commit()
            return {"feedback_id": feedback.id, "version_id": data["version_id"]}

        return {"error": "Unreachable"}


# ── 10. get_track_features ──────────────────────────


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_track_features(
    id: int | None = None,
    query: str | None = None,
    include_sections: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get audio features for a track by id or query. Optionally include sections."""
    if id is None and query is None:
        return {"error": "Provide id or query"}

    async with await _get_session(ctx) as session:
        track_repo = TrackRepository(session)

        track: Track | None = None
        if id is not None:
            track = await track_repo.get_by_id(id)
        elif query is not None:
            results = await track_repo.search_by_text(query, limit=1)
            track = results[0] if results else None

        if track is None:
            return {"error": "Track not found"}

        # Load features
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track.id
        )
        result = await session.execute(stmt)
        features = result.scalar_one_or_none()

        if features is None:
            return {"track_id": track.id, "title": track.title, "has_features": False}

        response: dict[str, Any] = {
            "track_id": track.id,
            "title": track.title,
            "has_features": True,
            "tempo": {
                "bpm": features.bpm,
                "bpm_confidence": features.bpm_confidence,
                "bpm_stability": features.bpm_stability,
                "variable_tempo": features.variable_tempo,
            },
            "loudness": {
                "integrated_lufs": features.integrated_lufs,
                "short_term_lufs_mean": features.short_term_lufs_mean,
                "momentary_max": features.momentary_max,
                "rms_dbfs": features.rms_dbfs,
                "true_peak_db": features.true_peak_db,
                "crest_factor_db": features.crest_factor_db,
                "loudness_range_lu": features.loudness_range_lu,
            },
            "energy": {
                "mean": features.energy_mean,
                "max": features.energy_max,
                "std": features.energy_std,
                "slope": features.energy_slope,
            },
            "spectral": {
                "centroid_hz": features.spectral_centroid_hz,
                "rolloff_85": features.spectral_rolloff_85,
                "rolloff_95": features.spectral_rolloff_95,
                "flatness": features.spectral_flatness,
                "flux_mean": features.spectral_flux_mean,
                "contrast": features.spectral_contrast,
            },
            "key": {
                "key_code": features.key_code,
                "key_confidence": features.key_confidence,
                "atonality": features.atonality,
                "hnr_db": features.hnr_db,
            },
            "rhythm": {
                "hp_ratio": features.hp_ratio,
                "onset_rate": features.onset_rate,
                "pulse_clarity": features.pulse_clarity,
                "kick_prominence": features.kick_prominence,
            },
        }

        if include_sections:
            stmt_sections = (
                select(TrackSection)
                .where(TrackSection.track_id == track.id)
                .order_by(TrackSection.start_ms)
            )
            result = await session.execute(stmt_sections)
            sections = list(result.scalars().all())
            response["sections"] = [
                {
                    "id": s.id,
                    "type": s.section_type,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                    "energy": s.energy,
                    "confidence": s.confidence,
                }
                for s in sections
            ]

        return response

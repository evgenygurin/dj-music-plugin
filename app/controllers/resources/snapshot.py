"""Snapshot resource — single-call library context for AI session initialization.

Resources:
- library://snapshot — track counts by mood, playlists, last-analyzed timestamp
"""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.track import Track


@resource(
    uri="library://snapshot",
    name="Library Snapshot",
    title="Library Snapshot",
    description=(
        "Single-call library context for AI session initialization. "
        "Returns track counts by subgenre/mood, playlist list with track counts, "
        "and the last-analyzed timestamp. Read this once at session start."
    ),
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def library_snapshot(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get library snapshot for AI session initialization."""
    total_result = await session.execute(select(func.count(Track.id)))
    total_tracks = total_result.scalar() or 0

    features_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id))
    )
    tracks_with_features = features_result.scalar() or 0

    # Mood distribution: group by mood, skip nulls
    mood_rows = await session.execute(
        select(TrackAudioFeaturesComputed.mood, func.count())
        .where(TrackAudioFeaturesComputed.mood.isnot(None))
        .group_by(TrackAudioFeaturesComputed.mood)
        .order_by(func.count().desc())
    )
    mood_distribution = {row[0]: row[1] for row in mood_rows}

    # Last analyzed: max updated_at on features table
    last_analyzed_result = await session.execute(
        select(func.max(TrackAudioFeaturesComputed.updated_at))
    )
    last_analyzed_raw = last_analyzed_result.scalar()
    last_analyzed = last_analyzed_raw.isoformat() if last_analyzed_raw else None

    # Playlists with track counts
    playlist_rows = await session.execute(
        select(
            Playlist.id,
            Playlist.name,
            func.count(PlaylistItem.track_id).label("track_count"),
        )
        .outerjoin(PlaylistItem, PlaylistItem.playlist_id == Playlist.id)
        .group_by(Playlist.id, Playlist.name)
        .order_by(Playlist.name)
    )
    playlists = [
        {"id": row.id, "name": row.name, "track_count": row.track_count} for row in playlist_rows
    ]

    data = {
        "total_tracks": total_tracks,
        "tracks_with_features": tracks_with_features,
        "feature_coverage_pct": (
            round(tracks_with_features / total_tracks * 100, 1) if total_tracks else 0.0
        ),
        "mood_distribution": mood_distribution,
        "playlists": playlists,
        "last_analyzed": last_analyzed,
    }
    return json_resource(data)

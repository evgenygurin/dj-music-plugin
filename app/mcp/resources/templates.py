"""Template resources — dynamic content based on URI parameters.

Resources:
- track://{track_id}/features — Audio features summary for a specific track
- set://{set_id}/summary — Latest version summary for a specific DJ set
- playlist://{playlist_id}/status — Status information for a specific playlist
- catalog://stats{?mood,bpm_min,bpm_max} — Filtered catalog statistics (parametric)
"""

from __future__ import annotations

import json
from typing import Annotated

from fastmcp.dependencies import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CAMELOT_KEYS, TechnoSubgenre
from app.core.errors import NotFoundError
from app.mcp.dependencies import get_db_session
from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist
from app.models.set import DjSet, SetVersion
from app.models.track import Track
from app.server import mcp


@mcp.resource(
    uri="track://{track_id}/features",
    name="Track Audio Features",
    description="Audio features summary for a specific track",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def track_features(
    track_id: Annotated[int, "Track ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> str:
    """Get audio features summary for a track.

    Returns JSON with key audio features:
    - track_id, title, artist
    - bpm, key (Camelot notation), energy (LUFS)
    - spectral_centroid, spectral_flatness
    - kick_prominence, pulse_clarity
    - mood (if classified)
    """
    # Fetch track
    track_result = await session.execute(select(Track).where(Track.id == track_id))
    track = track_result.scalar_one_or_none()
    if not track:
        raise NotFoundError("Track", track_id)

    # Fetch audio features
    features_result = await session.execute(
        select(TrackAudioFeaturesComputed).where(TrackAudioFeaturesComputed.track_id == track_id)
    )
    features = features_result.scalar_one_or_none()

    if not features:
        # Track exists but no features analyzed yet
        data = {
            "track_id": track_id,
            "title": track.title,
            "artist": "Unknown",  # TODO: fetch from artists relationship
            "features_available": False,
            "message": "Audio features not yet analyzed",
        }
        return json.dumps(data, indent=2)

    # Build Camelot key notation
    key_name = None
    if features.key_code is not None:
        camelot_notation, key_full_name = CAMELOT_KEYS.get(features.key_code, ("?", "Unknown"))
        key_name = f"{camelot_notation} ({key_full_name})"

    data = {
        "track_id": track_id,
        "title": track.title,
        "artist": "Unknown",  # TODO: fetch from artists relationship
        "features_available": True,
        "tempo": {
            "bpm": features.bpm,
            "confidence": features.bpm_confidence,
            "stability": features.bpm_stability,
        },
        "key": {
            "code": features.key_code,
            "name": key_name,
            "confidence": features.key_confidence,
        },
        "energy": {
            "lufs_integrated": features.integrated_lufs,
            "mean": features.energy_mean,
            "max": features.energy_max,
        },
        "spectral": {
            "centroid_hz": features.spectral_centroid_hz,
            "flatness": features.spectral_flatness,
            "rolloff_85_hz": features.spectral_rolloff_85,
        },
        "rhythm": {
            "kick_prominence": features.kick_prominence,
            "pulse_clarity": features.pulse_clarity,
            "onset_rate": features.onset_rate,
        },
        "mood": "N/A (requires classifier)",
    }

    return json.dumps(data, indent=2)


@mcp.resource(
    uri="set://{set_id}/summary",
    name="DJ Set Summary",
    description="Latest version summary for a specific DJ set",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def set_summary(
    set_id: Annotated[int, "DJ Set ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> str:
    """Get latest version summary for a DJ set.

    Returns JSON with:
    - set_id, name, description
    - latest_version_id, version_label
    - track_count, total_duration_min
    - quality_score
    - problems: list of issues (hard conflicts, weak transitions)
    """
    # Fetch set
    set_result = await session.execute(select(DjSet).where(DjSet.id == set_id))
    dj_set = set_result.scalar_one_or_none()
    if not dj_set:
        raise NotFoundError("DJ Set", set_id)

    # Fetch latest version
    latest_version_result = await session.execute(
        select(SetVersion)
        .where(SetVersion.set_id == set_id)
        .order_by(SetVersion.created_at.desc())
        .limit(1)
    )
    latest_version = latest_version_result.scalar_one_or_none()

    if not latest_version:
        data = {
            "set_id": set_id,
            "name": dj_set.name,
            "description": dj_set.description,
            "has_versions": False,
            "message": "No versions generated yet",
        }
        return json.dumps(data, indent=2)

    # Count tracks in latest version
    track_count_result = await session.execute(
        select(func.count()).where(
            SetVersion.id == latest_version.id  # TODO: fix when SetItem model exists
        )
    )
    track_count = track_count_result.scalar() or 0

    # Calculate total duration (placeholder — needs SetItem join)
    total_duration_min = 0

    data = {
        "set_id": set_id,
        "name": dj_set.name,
        "description": dj_set.description,
        "has_versions": True,
        "latest_version": {
            "version_id": latest_version.id,
            "version_label": latest_version.label,
            "quality_score": latest_version.quality_score,
            "track_count": track_count,
            "total_duration_min": total_duration_min,
            "created_at": latest_version.created_at.isoformat(),
        },
        "problems": [],  # TODO: calculate from transition scores
    }

    return json.dumps(data, indent=2)


@mcp.resource(
    uri="playlist://{playlist_id}/status",
    name="Playlist Status",
    description="Status information for a specific playlist",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def playlist_status(
    playlist_id: Annotated[int, "Playlist ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> str:
    """Get status information for a playlist.

    Returns JSON with:
    - playlist_id, name
    - track_count
    - source_of_truth: "local" | platform_name
    - platform_ids: dict of platform links
    - last_synced: timestamp (if available)
    """
    # Fetch playlist
    playlist_result = await session.execute(select(Playlist).where(Playlist.id == playlist_id))
    playlist = playlist_result.scalar_one_or_none()
    if not playlist:
        raise NotFoundError("Playlist", playlist_id)

    # Count tracks in playlist (placeholder — needs PlaylistItem join)
    track_count = 0  # TODO: count from dj_playlist_items

    data = {
        "playlist_id": playlist_id,
        "name": playlist.name,
        "track_count": track_count,
        "source_of_truth": playlist.source_of_truth,
        "source_app": playlist.source_app,
        "platform_ids": playlist.platform_ids or {},
        "last_synced": None,  # TODO: track sync timestamps
    }

    return json.dumps(data, indent=2)


# NOTE: catalog://stats{?mood,bpm_min,bpm_max} is exposed via get_library_stats tool
# instead of resource, because FastMCP doesn't support query params in resource URIs.
# Keeping the function for potential future use.


async def catalog_stats(
    mood: Annotated[TechnoSubgenre | None, "Filter by mood/subgenre"] = None,
    bpm_min: Annotated[float | None, "Minimum BPM"] = None,
    bpm_max: Annotated[float | None, "Maximum BPM"] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> str:
    """Get filtered catalog statistics.

    Query params:
    - mood: TechnoSubgenre enum value (e.g., "peak_time")
    - bpm_min: minimum BPM threshold
    - bpm_max: maximum BPM threshold

    Returns JSON with:
    - total_tracks: matching tracks count
    - filters_applied: dict of active filters
    - avg_bpm, avg_energy
    - mood_distribution: count per mood (if no mood filter)
    """
    # Build query with filters
    query = select(TrackAudioFeaturesComputed)

    if mood:
        query = query.where(TrackAudioFeaturesComputed.bpm == mood.value)

    if bpm_min is not None:
        query = query.where(TrackAudioFeaturesComputed.bpm >= bpm_min)

    if bpm_max is not None:
        query = query.where(TrackAudioFeaturesComputed.bpm <= bpm_max)

    # Count matching tracks
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total_tracks = count_result.scalar() or 0

    # Calculate averages
    avg_bpm_result = await session.execute(
        select(func.avg(TrackAudioFeaturesComputed.bpm)).select_from(query.subquery())
    )
    avg_bpm = avg_bpm_result.scalar()

    avg_energy_result = await session.execute(
        select(func.avg(TrackAudioFeaturesComputed.integrated_lufs)).select_from(query.subquery())
    )
    avg_energy = avg_energy_result.scalar()

    data = {
        "total_tracks": total_tracks,
        "filters_applied": {
            "mood": mood.value if mood else None,
            "bpm_min": bpm_min,
            "bpm_max": bpm_max,
        },
        "avg_bpm": round(avg_bpm, 1) if avg_bpm else None,
        "avg_energy_lufs": round(avg_energy, 1) if avg_energy else None,
    }

    # If no mood filter, include mood distribution
    if not mood:
        mood_distribution = {}
        for subgenre in TechnoSubgenre:
            mood_count_result = await session.execute(
                select(func.count(TrackAudioFeaturesComputed.track_id)).where(
                    TrackAudioFeaturesComputed.bpm == subgenre.value
                )
            )
            count = mood_count_result.scalar() or 0
            if count > 0:
                mood_distribution[subgenre.value] = count
        data["mood_distribution"] = mood_distribution

    return json.dumps(data, indent=2)

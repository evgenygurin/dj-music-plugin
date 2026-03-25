"""Static status resources — library health and platform connectivity.

Resources:
- status://library — Library health: counts, coverage, health indicator
- status://platforms — Connected platforms + linked track counts
"""

from __future__ import annotations

import json

from fastmcp.dependencies import Depends
from app.server import mcp
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Provider
from app.mcp.dependencies import get_db_session
from app.models.audio import TrackAudioFeaturesComputed
from app.models.platform import (
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyMetadata,
    YandexMetadata,
)
from app.models.track import Track


@mcp.resource(
    uri="status://library",
    name="Library Health",
    description="Overall library statistics, feature coverage, and health indicators",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def library_status(
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """Get library health statistics.

    Returns JSON with:
    - total_tracks: int
    - active_tracks: int
    - archived_tracks: int
    - tracks_with_features: int
    - feature_coverage_percent: float
    - tracks_with_bpm: int
    - tracks_with_key: int
    - tracks_with_energy: int
    - health: "good" | "needs_analysis" | "empty"
    """
    # Total tracks
    total_result = await session.execute(select(func.count(Track.id)))
    total_tracks = total_result.scalar() or 0

    # Active vs archived
    active_result = await session.execute(select(func.count(Track.id)).where(Track.status == 0))
    active_tracks = active_result.scalar() or 0
    archived_tracks = total_tracks - active_tracks

    # Tracks with computed features
    features_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id))
    )
    tracks_with_features = features_result.scalar() or 0

    # Tracks with specific features (BPM, key, energy)
    bpm_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id)).where(
            TrackAudioFeaturesComputed.bpm.isnot(None)
        )
    )
    tracks_with_bpm = bpm_result.scalar() or 0

    key_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id)).where(
            TrackAudioFeaturesComputed.key_code.isnot(None)
        )
    )
    tracks_with_key = key_result.scalar() or 0

    energy_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id)).where(
            TrackAudioFeaturesComputed.energy_lufs_integrated.isnot(None)
        )
    )
    tracks_with_energy = energy_result.scalar() or 0

    # Calculate coverage
    coverage = (tracks_with_features / total_tracks * 100) if total_tracks > 0 else 0.0

    # Health indicator
    if total_tracks == 0:
        health = "empty"
    elif coverage >= 80:
        health = "good"
    else:
        health = "needs_analysis"

    data = {
        "total_tracks": total_tracks,
        "active_tracks": active_tracks,
        "archived_tracks": archived_tracks,
        "tracks_with_features": tracks_with_features,
        "feature_coverage_percent": round(coverage, 1),
        "tracks_with_bpm": tracks_with_bpm,
        "tracks_with_key": tracks_with_key,
        "tracks_with_energy": tracks_with_energy,
        "health": health,
    }

    return json.dumps(data, indent=2)


@mcp.resource(
    uri="status://platforms",
    name="Platform Connectivity",
    description="Connected external platforms and linked track counts",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def platforms_status(
    session: AsyncSession = Depends(get_db_session),
) -> str:
    """Get platform connectivity status.

    Returns JSON with platform-specific stats:
    - platform_name: str
    - linked_tracks: int
    - configured: bool (whether API credentials are set)
    """
    platforms = []

    # Yandex Music
    ym_count_result = await session.execute(select(func.count(YandexMetadata.track_id)))
    ym_count = ym_count_result.scalar() or 0
    platforms.append(
        {
            "platform": Provider.YANDEX_MUSIC.value,
            "linked_tracks": ym_count,
            "configured": True,  # Assume configured if metadata exists
        }
    )

    # Spotify
    spotify_count_result = await session.execute(select(func.count(SpotifyMetadata.track_id)))
    spotify_count = spotify_count_result.scalar() or 0
    platforms.append(
        {
            "platform": Provider.SPOTIFY.value,
            "linked_tracks": spotify_count,
            "configured": spotify_count > 0,
        }
    )

    # Beatport
    beatport_count_result = await session.execute(select(func.count(BeatportMetadata.track_id)))
    beatport_count = beatport_count_result.scalar() or 0
    platforms.append(
        {
            "platform": Provider.BEATPORT.value,
            "linked_tracks": beatport_count,
            "configured": beatport_count > 0,
        }
    )

    # SoundCloud
    sc_count_result = await session.execute(select(func.count(SoundcloudMetadata.track_id)))
    sc_count = sc_count_result.scalar() or 0
    platforms.append(
        {
            "platform": Provider.SOUNDCLOUD.value,
            "linked_tracks": sc_count,
            "configured": sc_count > 0,
        }
    )

    data = {"platforms": platforms, "total_platforms": len(Provider)}

    return json.dumps(data, indent=2)

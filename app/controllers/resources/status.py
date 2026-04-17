"""Static status resources — library health, data quality, and connectivity.

Resources:
- status://library — Library health: counts, coverage, health indicator
- status://platforms — Connected platforms + linked track counts
- status://analysis-quality — Audio analysis field coverage and run health
- status://set-integrity — Set/transition linkage integrity checks
- status://provider-coverage — Cross-platform ID and metadata coverage
"""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.core.constants import Provider
from app.db.models.audio import FeatureExtractionRun, TrackAudioFeaturesComputed
from app.db.models.platform import (
    BeatportMetadata,
    SoundcloudMetadata,
    SpotifyMetadata,
    YandexMetadata,
)
from app.db.models.set import DjSet, SetFeedback, SetItem, SetVersion
from app.db.models.track import Track, TrackExternalId
from app.db.models.transition import Transition


@resource(
    uri="status://library",
    name="Library Health",
    title="Library Health",
    description="Overall library statistics, feature coverage, and health indicators",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def library_status(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
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
            TrackAudioFeaturesComputed.integrated_lufs.isnot(None)
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

    return json_resource(data)


@resource(
    uri="status://platforms",
    name="Platform Connectivity",
    title="Platform Connectivity",
    description="Connected external platforms and linked track counts",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def platforms_status(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
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

    return json_resource(data)


@resource(
    uri="status://analysis-quality",
    name="Analysis Quality",
    title="Analysis Quality",
    description="Coverage of critical audio-analysis fields and pipeline run statuses",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def analysis_quality(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return analysis coverage and extraction-run quality indicators."""
    total_tracks = (await session.execute(select(func.count(Track.id)))).scalar() or 0
    total_features = (
        await session.execute(select(func.count(TrackAudioFeaturesComputed.track_id)))
    ).scalar() or 0

    coverage_fields = {
        "bpm": TrackAudioFeaturesComputed.bpm,
        "key_code": TrackAudioFeaturesComputed.key_code,
        "integrated_lufs": TrackAudioFeaturesComputed.integrated_lufs,
        "mood": TrackAudioFeaturesComputed.mood,
        "first_downbeat_ms": TrackAudioFeaturesComputed.first_downbeat_ms,
        "phrase_boundaries_ms": TrackAudioFeaturesComputed.phrase_boundaries_ms,
        "dominant_phrase_bars": TrackAudioFeaturesComputed.dominant_phrase_bars,
    }

    field_coverage: dict[str, dict[str, float | int]] = {}
    for field_name, column in coverage_fields.items():
        filled = (
            await session.execute(
                select(func.count(TrackAudioFeaturesComputed.track_id)).where(column.isnot(None))
            )
        ).scalar() or 0
        pct_of_features = round((filled / total_features * 100), 2) if total_features else 0.0
        pct_of_tracks = round((filled / total_tracks * 100), 2) if total_tracks else 0.0
        field_coverage[field_name] = {
            "filled_rows": filled,
            "pct_of_feature_rows": pct_of_features,
            "pct_of_all_tracks": pct_of_tracks,
        }

    run_status_rows = await session.execute(
        select(FeatureExtractionRun.status, func.count(FeatureExtractionRun.id))
        .group_by(FeatureExtractionRun.status)
        .order_by(FeatureExtractionRun.status)
    )
    run_status_counts = {status: count for status, count in run_status_rows}

    latest_run_at = (
        await session.execute(select(func.max(FeatureExtractionRun.updated_at)))
    ).scalar()
    latest_feature_update = (
        await session.execute(select(func.max(TrackAudioFeaturesComputed.updated_at)))
    ).scalar()

    data = {
        "totals": {
            "tracks": total_tracks,
            "feature_rows": total_features,
            "feature_row_coverage_pct": (
                round((total_features / total_tracks * 100), 2) if total_tracks else 0.0
            ),
        },
        "field_coverage": field_coverage,
        "pipeline_runs": {
            "total_runs": sum(run_status_counts.values()),
            "by_status": run_status_counts,
            "latest_run_at": latest_run_at.isoformat() if latest_run_at else None,
            "latest_feature_update_at": (
                latest_feature_update.isoformat() if latest_feature_update else None
            ),
        },
    }

    return json_resource(data)


@resource(
    uri="status://set-integrity",
    name="Set Integrity",
    title="Set Integrity",
    description="Integrity checks for set items, versions, and transition linkage",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def set_integrity(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return set/transition integrity diagnostics."""
    total_sets = (await session.execute(select(func.count(DjSet.id)))).scalar() or 0
    total_versions = (await session.execute(select(func.count(SetVersion.id)))).scalar() or 0
    total_set_items = (await session.execute(select(func.count(SetItem.id)))).scalar() or 0
    total_transitions = (await session.execute(select(func.count(Transition.id)))).scalar() or 0
    total_feedback = (await session.execute(select(func.count(SetFeedback.id)))).scalar() or 0

    linkage_row = await session.execute(
        select(
            func.count(SetItem.id)
            .filter(SetItem.transition_id.isnot(None))
            .label("with_transition_id"),
            func.count(SetItem.id)
            .filter(SetItem.mix_in_point_ms.isnot(None))
            .label("with_mix_in_point"),
            func.count(SetItem.id)
            .filter(SetItem.mix_out_point_ms.isnot(None))
            .label("with_mix_out_point"),
            func.count(SetItem.id).filter(SetItem.planned_eq.isnot(None)).label("with_planned_eq"),
            func.count(SetItem.id).filter(SetItem.notes.isnot(None)).label("with_notes"),
            func.count(SetItem.id).filter(SetItem.pinned.is_(True)).label("pinned_count"),
        )
    )
    linkage = linkage_row.one()

    dangling_transition_refs = (
        await session.execute(
            select(func.count(SetItem.id))
            .select_from(SetItem)
            .outerjoin(Transition, Transition.id == SetItem.transition_id)
            .where(and_(SetItem.transition_id.isnot(None), Transition.id.is_(None)))
        )
    ).scalar() or 0

    versions_with_quality = (
        await session.execute(
            select(func.count(SetVersion.id)).where(SetVersion.quality_score.isnot(None))
        )
    ).scalar() or 0
    versions_with_generator_meta = (
        await session.execute(
            select(func.count(SetVersion.id)).where(SetVersion.generator_run_meta.isnot(None))
        )
    ).scalar() or 0

    data = {
        "totals": {
            "sets": total_sets,
            "versions": total_versions,
            "set_items": total_set_items,
            "transitions": total_transitions,
            "feedback_rows": total_feedback,
        },
        "set_item_fields": {
            "with_transition_id": int(linkage.with_transition_id or 0),
            "with_mix_in_point": int(linkage.with_mix_in_point or 0),
            "with_mix_out_point": int(linkage.with_mix_out_point or 0),
            "with_planned_eq": int(linkage.with_planned_eq or 0),
            "with_notes": int(linkage.with_notes or 0),
            "pinned_count": int(linkage.pinned_count or 0),
            "dangling_transition_refs": dangling_transition_refs,
        },
        "version_fields": {
            "with_quality_score": versions_with_quality,
            "with_generator_run_meta": versions_with_generator_meta,
        },
    }

    return json_resource(data)


@resource(
    uri="status://provider-coverage",
    name="Provider Coverage",
    title="Provider Coverage",
    description="Coverage of external platform IDs and metadata by provider",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def provider_coverage(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return external-ID and provider metadata coverage for the track catalog."""
    total_tracks = (await session.execute(select(func.count(Track.id)))).scalar() or 0

    external_rows = await session.execute(
        select(TrackExternalId.platform, func.count(TrackExternalId.id))
        .group_by(TrackExternalId.platform)
        .order_by(func.count(TrackExternalId.id).desc())
    )
    external_by_platform = {platform: count for platform, count in external_rows}
    tracks_with_any_external_id = (
        await session.execute(select(func.count(func.distinct(TrackExternalId.track_id))))
    ).scalar() or 0

    metadata_rows = {
        Provider.YANDEX_MUSIC.value: (
            await session.execute(select(func.count(YandexMetadata.track_id)))
        ).scalar()
        or 0,
        Provider.SPOTIFY.value: (
            await session.execute(select(func.count(SpotifyMetadata.track_id)))
        ).scalar()
        or 0,
        Provider.BEATPORT.value: (
            await session.execute(select(func.count(BeatportMetadata.track_id)))
        ).scalar()
        or 0,
        Provider.SOUNDCLOUD.value: (
            await session.execute(select(func.count(SoundcloudMetadata.track_id)))
        ).scalar()
        or 0,
    }

    per_platform = []
    for provider in Provider:
        ext_count = int(external_by_platform.get(provider.value, 0))
        meta_count = int(metadata_rows.get(provider.value, 0))
        per_platform.append(
            {
                "platform": provider.value,
                "external_ids": ext_count,
                "metadata_rows": meta_count,
                "external_coverage_pct": (
                    round(ext_count / total_tracks * 100, 2) if total_tracks else 0.0
                ),
                "metadata_coverage_pct": (
                    round(meta_count / total_tracks * 100, 2) if total_tracks else 0.0
                ),
            }
        )

    data = {
        "total_tracks": total_tracks,
        "tracks_with_any_external_id": tracks_with_any_external_id,
        "tracks_with_any_external_id_pct": (
            round((tracks_with_any_external_id / total_tracks * 100), 2) if total_tracks else 0.0
        ),
        "per_platform": per_platform,
        "external_id_rows_by_platform": external_by_platform,
    }

    return json_resource(data)

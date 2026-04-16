"""Template resources — dynamic content based on URI parameters.

Resources:
- track://{track_id}/features — Audio features summary + full ``TrackAudioFeaturesComputed`` row
- track://{track_id}/identity — Track identity across artists/genres/releases/platform IDs
- track://{track_id}/sections{?limit,offset,section_type} — Paged structural sections
- set://{set_id}/summary — Latest version summary for a specific DJ set
- set://{set_id}/diagnostics{?version} — Version-level diagnostics and weak transitions
- playlist://{playlist_id}/status — Status information for a specific playlist
- playlist://{playlist_id}/profile{?limit,offset} — Feature and catalog profile for playlist
- catalog://stats{?mood,bpm_min,bpm_max} — Filtered catalog statistics (parametric)
"""

from __future__ import annotations

import contextlib
import json
from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.resources.feature_serialization import computed_features_row_to_jsonable
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.core.constants import CAMELOT_KEYS, TechnoSubgenre
from app.core.errors import NotFoundError
from app.db.models.audio import TrackAudioFeaturesComputed, TrackSection
from app.db.models.platform import YandexMetadata
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.set import DjSet, SetFeedback, SetItem, SetVersion
from app.db.models.track import (
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)
from app.db.models.track_feedback import TrackFeedback
from app.db.models.transition import Transition


@resource(
    uri="track://{track_id}/features",
    name="Track Audio Features",
    title="Track Audio Features",
    description=(
        "Audio features for a track: compact summary plus full row from "
        "track_audio_features_computed (audio_features)."
    ),
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def track_features(
    track_id: Annotated[int, "Track ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get audio features for a track.

    Returns JSON with:
    - track_id, title, artist, features_available
    - tempo / key / energy / spectral / rhythm / mood (compact summary, backward compatible)
    - audio_features: every scalar column on ``TrackAudioFeaturesComputed`` (full analysis row)
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
        return json_resource(data)

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
        "mood": features.mood,
        "mood_confidence": features.mood_confidence,
        "audio_features": computed_features_row_to_jsonable(features),
    }

    return json_resource(data)


@resource(
    uri="track://{track_id}/identity",
    name="Track Identity",
    title="Track Identity",
    description="Identity card for a track across artists, genres, releases, and platform IDs",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def track_identity(
    track_id: Annotated[int, "Track ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get a normalized identity card for one track."""
    track = (await session.execute(select(Track).where(Track.id == track_id))).scalar_one_or_none()
    if not track:
        raise NotFoundError("Track", track_id)

    feature = (
        await session.execute(
            select(TrackAudioFeaturesComputed).where(
                TrackAudioFeaturesComputed.track_id == track_id
            )
        )
    ).scalar_one_or_none()
    feedback = (
        await session.execute(select(TrackFeedback).where(TrackFeedback.track_id == track_id))
    ).scalar_one_or_none()
    yandex = (
        await session.execute(select(YandexMetadata).where(YandexMetadata.track_id == track_id))
    ).scalar_one_or_none()

    artist_rows = await session.execute(
        select(Artist.id, Artist.name, Artist.sort_name, TrackArtist.role)
        .join(TrackArtist, TrackArtist.artist_id == Artist.id)
        .where(TrackArtist.track_id == track_id)
        .order_by(Artist.name)
    )
    artists = [
        {"id": row.id, "name": row.name, "sort_name": row.sort_name, "role": row.role}
        for row in artist_rows
    ]

    genre_rows = await session.execute(
        select(Genre.id, Genre.name, Genre.parent_id)
        .join(TrackGenre, TrackGenre.genre_id == Genre.id)
        .where(TrackGenre.track_id == track_id)
        .order_by(Genre.name)
    )
    genres = [{"id": row.id, "name": row.name, "parent_id": row.parent_id} for row in genre_rows]

    release_rows = await session.execute(
        select(
            Release.id,
            Release.title,
            Release.release_date,
            Release.release_type,
            TrackRelease.track_number,
            Label.id.label("label_id"),
            Label.name.label("label_name"),
        )
        .join(TrackRelease, TrackRelease.release_id == Release.id)
        .outerjoin(Label, Label.id == Release.label_id)
        .where(TrackRelease.track_id == track_id)
        .order_by(Release.release_date.desc().nullslast(), Release.title)
    )
    releases = [
        {
            "id": row.id,
            "title": row.title,
            "release_date": row.release_date.isoformat() if row.release_date else None,
            "release_type": row.release_type,
            "track_number": row.track_number,
            "label": {"id": row.label_id, "name": row.label_name}
            if row.label_id is not None
            else None,
        }
        for row in release_rows
    ]

    ext_rows = await session.execute(
        select(TrackExternalId.platform, TrackExternalId.external_id).where(
            TrackExternalId.track_id == track_id
        )
    )
    external_ids = {row.platform: row.external_id for row in ext_rows}

    key_name = None
    if feature and feature.key_code is not None:
        camelot_notation, key_full_name = CAMELOT_KEYS.get(feature.key_code, ("?", "Unknown"))
        key_name = f"{camelot_notation} ({key_full_name})"

    data = {
        "track": {
            "id": track.id,
            "title": track.title,
            "sort_title": track.sort_title,
            "duration_ms": track.duration_ms,
            "status": track.status,
            "created_at": track.created_at.isoformat(),
            "updated_at": track.updated_at.isoformat(),
        },
        "artists": artists,
        "genres": genres,
        "releases": releases,
        "external_ids": external_ids,
        "platform_metadata": {
            "yandex_music": (
                {
                    "yandex_track_id": yandex.yandex_track_id,
                    "album_id": yandex.album_id,
                    "album_title": yandex.album_title,
                    "album_genre": yandex.album_genre,
                    "album_year": yandex.album_year,
                    "duration_ms": yandex.duration_ms,
                    "cover_uri": yandex.cover_uri,
                    "explicit": yandex.explicit,
                }
                if yandex
                else None
            )
        },
        "analysis_summary": (
            {
                "analysis_level": feature.analysis_level,
                "bpm": feature.bpm,
                "key_code": feature.key_code,
                "key_name": key_name,
                "integrated_lufs": feature.integrated_lufs,
                "mood": feature.mood,
                "mood_confidence": feature.mood_confidence,
            }
            if feature
            else None
        ),
        "feedback": (
            {
                "rating": feedback.rating,
                "status": feedback.status,
                "play_count": feedback.play_count,
                "skip_count": feedback.skip_count,
                "notes": feedback.notes,
            }
            if feedback
            else None
        ),
    }
    return json_resource(data)


@resource(
    uri="track://{track_id}/sections{?limit,offset,section_type}",
    name="Track Sections",
    title="Track Sections",
    description="Paged structural sections for one track with optional section-type filter",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def track_sections(
    track_id: Annotated[int, "Track ID"],
    limit: Annotated[int, "Page size"] = 100,
    offset: Annotated[int, "Row offset"] = 0,
    section_type: Annotated[int | None, "Optional section_type filter"] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get paged section rows for one track."""
    track_exists = (
        await session.execute(select(func.count(Track.id)).where(Track.id == track_id))
    ).scalar()
    if not track_exists:
        raise NotFoundError("Track", track_id)

    page_limit = max(1, min(limit, settings.pagination_max))
    page_offset = max(0, offset)

    where_clauses = [TrackSection.track_id == track_id]
    if section_type is not None:
        where_clauses.append(TrackSection.section_type == section_type)

    total_rows = (
        await session.execute(select(func.count(TrackSection.id)).where(*where_clauses))
    ).scalar() or 0

    section_rows = await session.execute(
        select(
            TrackSection.id,
            TrackSection.section_type,
            TrackSection.start_ms,
            TrackSection.end_ms,
            TrackSection.energy,
            TrackSection.confidence,
        )
        .where(*where_clauses)
        .order_by(TrackSection.start_ms, TrackSection.id)
        .offset(page_offset)
        .limit(page_limit)
    )
    rows = [
        {
            "id": row.id,
            "section_type": row.section_type,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "duration_ms": row.end_ms - row.start_ms,
            "energy": row.energy,
            "confidence": row.confidence,
        }
        for row in section_rows
    ]

    summary_row = await session.execute(
        select(
            func.min(TrackSection.start_ms).label("start_min"),
            func.max(TrackSection.end_ms).label("end_max"),
            func.avg(TrackSection.energy).label("avg_energy"),
            func.avg(TrackSection.confidence).label("avg_confidence"),
        ).where(*where_clauses)
    )
    summary = summary_row.one()

    data = {
        "track_id": track_id,
        "filters": {"section_type": section_type},
        "pagination": {
            "limit": page_limit,
            "offset": page_offset,
            "total": total_rows,
            "returned": len(rows),
        },
        "summary": {
            "start_ms_min": summary.start_min,
            "end_ms_max": summary.end_max,
            "avg_energy": round(summary.avg_energy, 4) if summary.avg_energy is not None else None,
            "avg_confidence": (
                round(summary.avg_confidence, 4) if summary.avg_confidence is not None else None
            ),
        },
        "sections": rows,
    }
    return json_resource(data)


@resource(
    uri="set://{set_id}/summary",
    name="DJ Set Summary",
    title="DJ Set Summary",
    description="Latest version summary for a specific DJ set",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def set_summary(
    set_id: Annotated[int, "DJ Set ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
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
        return json_resource(data)

    # Count tracks in latest version
    from app.db.models.set import SetItem

    track_count_result = await session.execute(
        select(func.count()).where(SetItem.version_id == latest_version.id)
    )
    track_count = track_count_result.scalar() or 0

    # Calculate total duration from track durations
    from app.db.models.track import Track as TrackModel

    dur_result = await session.execute(
        select(func.coalesce(func.sum(TrackModel.duration_ms), 0))
        .join(SetItem, SetItem.track_id == TrackModel.id)
        .where(SetItem.version_id == latest_version.id)
    )
    total_duration_min = round((dur_result.scalar() or 0) / 60_000)

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

    return json_resource(data)


@resource(
    uri="set://{set_id}/diagnostics{?version}",
    name="Set Diagnostics",
    title="Set Diagnostics",
    description="Version-level diagnostics for set structure, transition quality, and feedback",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def set_diagnostics(
    set_id: Annotated[int, "DJ Set ID"],
    version: Annotated[str | None, "Optional version label or numeric version ID"] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get diagnostics for one set version (latest by default)."""
    dj_set = (await session.execute(select(DjSet).where(DjSet.id == set_id))).scalar_one_or_none()
    if not dj_set:
        raise NotFoundError("DJ Set", set_id)

    selected_version: SetVersion | None = None
    if version is None:
        selected_version = (
            await session.execute(
                select(SetVersion)
                .where(SetVersion.set_id == set_id)
                .order_by(SetVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    else:
        if version.isdigit():
            selected_version = (
                await session.execute(
                    select(SetVersion).where(
                        and_(SetVersion.id == int(version), SetVersion.set_id == set_id)
                    )
                )
            ).scalar_one_or_none()
        if selected_version is None:
            selected_version = (
                await session.execute(
                    select(SetVersion).where(
                        and_(SetVersion.set_id == set_id, SetVersion.label == version)
                    )
                )
            ).scalar_one_or_none()

    if selected_version is None:
        return json_resource(
            {
                "set_id": set_id,
                "set_name": dj_set.name,
                "has_versions": False,
                "message": "No matching set version found",
            }
        )

    item_rows = await session.execute(
        select(SetItem.id, SetItem.sort_index, SetItem.track_id, SetItem.transition_id)
        .where(SetItem.version_id == selected_version.id)
        .order_by(SetItem.sort_index)
    )
    items = item_rows.all()
    total_items = len(items)
    with_transition = sum(1 for row in items if row.transition_id is not None)

    transition_rows = await session.execute(
        select(
            Transition.id,
            Transition.from_track_id,
            Transition.to_track_id,
            Transition.overall_quality,
            Transition.hard_reject,
            Transition.reject_reason,
            Transition.fx_type,
            Transition.transition_bars,
        )
        .join(SetItem, SetItem.transition_id == Transition.id)
        .where(SetItem.version_id == selected_version.id)
        .order_by(
            Transition.hard_reject.desc().nullslast(),
            Transition.overall_quality.asc().nullslast(),
            Transition.id,
        )
    )
    transition_list = transition_rows.all()

    hard_reject_count = sum(1 for t in transition_list if t.hard_reject is True)
    weak_transitions = [
        {
            "transition_id": t.id,
            "from_track_id": t.from_track_id,
            "to_track_id": t.to_track_id,
            "overall_quality": t.overall_quality,
            "hard_reject": t.hard_reject,
            "reject_reason": t.reject_reason,
            "fx_type": t.fx_type,
            "transition_bars": t.transition_bars,
        }
        for t in transition_list
        if (t.hard_reject is True) or (t.overall_quality is not None and t.overall_quality < 0.5)
    ][:20]

    avg_quality = (
        round(
            sum(
                (t.overall_quality or 0.0)
                for t in transition_list
                if t.overall_quality is not None
            )
            / max(1, sum(1 for t in transition_list if t.overall_quality is not None)),
            4,
        )
        if transition_list
        else None
    )

    missing_features = (
        await session.execute(
            select(func.count(SetItem.id))
            .select_from(SetItem)
            .outerjoin(
                TrackAudioFeaturesComputed, TrackAudioFeaturesComputed.track_id == SetItem.track_id
            )
            .where(
                and_(
                    SetItem.version_id == selected_version.id,
                    TrackAudioFeaturesComputed.track_id.is_(None),
                )
            )
        )
    ).scalar() or 0

    feedback_rows = await session.execute(
        select(SetFeedback.feedback_type, func.count(SetFeedback.id), func.avg(SetFeedback.rating))
        .where(SetFeedback.version_id == selected_version.id)
        .group_by(SetFeedback.feedback_type)
        .order_by(SetFeedback.feedback_type)
    )
    feedback_by_type = [
        {
            "feedback_type": ftype,
            "count": count,
            "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        }
        for ftype, count, avg_rating in feedback_rows
    ]

    data = {
        "set_id": set_id,
        "set_name": dj_set.name,
        "version": {
            "id": selected_version.id,
            "label": selected_version.label,
            "quality_score": selected_version.quality_score,
            "created_at": selected_version.created_at.isoformat(),
        },
        "items": {
            "total": total_items,
            "with_transition_id": with_transition,
            "transition_link_coverage_pct": (
                round(with_transition / total_items * 100, 2) if total_items else 0.0
            ),
            "missing_feature_rows": missing_features,
        },
        "transitions": {
            "rows": len(transition_list),
            "hard_reject_count": hard_reject_count,
            "avg_overall_quality": avg_quality,
            "weak_transitions": weak_transitions,
        },
        "feedback": {
            "total_rows": sum(item["count"] for item in feedback_by_type),
            "by_type": feedback_by_type,
        },
    }
    return json_resource(data)


@resource(
    uri="playlist://{playlist_id}/status",
    name="Playlist Status",
    title="Playlist Status",
    description="Status information for a specific playlist",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def playlist_status(
    playlist_id: Annotated[int, "Playlist ID"],
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
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

    # Count tracks in playlist
    from app.db.models.playlist import PlaylistItem

    tc_result = await session.execute(
        select(func.count()).where(PlaylistItem.playlist_id == playlist_id)
    )
    track_count = tc_result.scalar() or 0

    data = {
        "playlist_id": playlist_id,
        "name": playlist.name,
        "track_count": track_count,
        "source_of_truth": playlist.source_of_truth,
        "source_app": playlist.source_app,
        "platform_ids": playlist.platform_ids or {},
        "last_synced": None,  # TODO: track sync timestamps
    }

    return json_resource(data)


@resource(
    uri="playlist://{playlist_id}/profile{?limit,offset}",
    name="Playlist Profile",
    title="Playlist Profile",
    description=(
        "Feature and catalog profile for a playlist (BPM/LUFS/mood/key + top artists/genres)"
    ),
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def playlist_profile(
    playlist_id: Annotated[int, "Playlist ID"],
    limit: Annotated[int, "Page size for track sample"] = 100,
    offset: Annotated[int, "Track sample offset"] = 0,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Get profile summary for one playlist."""
    playlist = (
        await session.execute(select(Playlist).where(Playlist.id == playlist_id))
    ).scalar_one_or_none()
    if not playlist:
        raise NotFoundError("Playlist", playlist_id)

    page_limit = max(1, min(limit, settings.pagination_max))
    page_offset = max(0, offset)

    total_tracks = (
        await session.execute(
            select(func.count(PlaylistItem.id)).where(PlaylistItem.playlist_id == playlist_id)
        )
    ).scalar() or 0

    feature_stats = (
        await session.execute(
            select(
                func.count(TrackAudioFeaturesComputed.track_id).label("feature_rows"),
                func.avg(TrackAudioFeaturesComputed.bpm).label("avg_bpm"),
                func.min(TrackAudioFeaturesComputed.bpm).label("min_bpm"),
                func.max(TrackAudioFeaturesComputed.bpm).label("max_bpm"),
                func.avg(TrackAudioFeaturesComputed.integrated_lufs).label("avg_lufs"),
                func.min(TrackAudioFeaturesComputed.integrated_lufs).label("min_lufs"),
                func.max(TrackAudioFeaturesComputed.integrated_lufs).label("max_lufs"),
            )
            .select_from(PlaylistItem)
            .join(Track, Track.id == PlaylistItem.track_id)
            .outerjoin(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == PlaylistItem.track_id,
            )
            .where(PlaylistItem.playlist_id == playlist_id)
        )
    ).one()

    mood_rows = await session.execute(
        select(TrackAudioFeaturesComputed.mood, func.count(TrackAudioFeaturesComputed.track_id))
        .select_from(PlaylistItem)
        .join(
            TrackAudioFeaturesComputed,
            TrackAudioFeaturesComputed.track_id == PlaylistItem.track_id,
        )
        .where(
            and_(
                PlaylistItem.playlist_id == playlist_id,
                TrackAudioFeaturesComputed.mood.isnot(None),
            )
        )
        .group_by(TrackAudioFeaturesComputed.mood)
        .order_by(func.count(TrackAudioFeaturesComputed.track_id).desc())
    )
    mood_distribution = {mood: count for mood, count in mood_rows}

    key_rows = await session.execute(
        select(
            TrackAudioFeaturesComputed.key_code,
            func.count(TrackAudioFeaturesComputed.track_id),
        )
        .select_from(PlaylistItem)
        .join(
            TrackAudioFeaturesComputed,
            TrackAudioFeaturesComputed.track_id == PlaylistItem.track_id,
        )
        .where(
            and_(
                PlaylistItem.playlist_id == playlist_id,
                TrackAudioFeaturesComputed.key_code.isnot(None),
            )
        )
        .group_by(TrackAudioFeaturesComputed.key_code)
        .order_by(func.count(TrackAudioFeaturesComputed.track_id).desc())
    )
    key_distribution = []
    for key_code, count in key_rows:
        camelot, full_name = CAMELOT_KEYS.get(int(key_code), ("?", "Unknown"))
        key_distribution.append(
            {
                "key_code": int(key_code),
                "camelot": camelot,
                "name": full_name,
                "count": int(count),
            }
        )

    top_artists_rows = await session.execute(
        select(Artist.name, func.count(TrackArtist.track_id).label("track_count"))
        .select_from(PlaylistItem)
        .join(TrackArtist, TrackArtist.track_id == PlaylistItem.track_id)
        .join(Artist, Artist.id == TrackArtist.artist_id)
        .where(PlaylistItem.playlist_id == playlist_id)
        .group_by(Artist.name)
        .order_by(func.count(TrackArtist.track_id).desc(), Artist.name)
        .limit(20)
    )
    top_artists = [{"name": name, "track_count": count} for name, count in top_artists_rows]

    top_genres_rows = await session.execute(
        select(Genre.name, func.count(TrackGenre.track_id).label("track_count"))
        .select_from(PlaylistItem)
        .join(TrackGenre, TrackGenre.track_id == PlaylistItem.track_id)
        .join(Genre, Genre.id == TrackGenre.genre_id)
        .where(PlaylistItem.playlist_id == playlist_id)
        .group_by(Genre.name)
        .order_by(func.count(TrackGenre.track_id).desc(), Genre.name)
        .limit(20)
    )
    top_genres = [{"name": name, "track_count": count} for name, count in top_genres_rows]

    sample_rows = await session.execute(
        select(PlaylistItem.sort_index, Track.id, Track.title, Track.duration_ms)
        .join(Track, Track.id == PlaylistItem.track_id)
        .where(PlaylistItem.playlist_id == playlist_id)
        .order_by(PlaylistItem.sort_index)
        .offset(page_offset)
        .limit(page_limit)
    )
    track_sample = [
        {
            "sort_index": row.sort_index,
            "track_id": row.id,
            "title": row.title,
            "duration_ms": row.duration_ms,
        }
        for row in sample_rows
    ]

    platform_ids = {}
    if playlist.platform_ids:
        with_json = None
        with contextlib.suppress(Exception):
            with_json = json.loads(playlist.platform_ids)
        if isinstance(with_json, dict):
            platform_ids = with_json

    data = {
        "playlist": {
            "id": playlist.id,
            "name": playlist.name,
            "source_of_truth": playlist.source_of_truth,
            "source_app": playlist.source_app,
            "platform_ids": platform_ids,
        },
        "totals": {
            "tracks": total_tracks,
            "feature_rows": int(feature_stats.feature_rows or 0),
            "feature_coverage_pct": (
                round((feature_stats.feature_rows or 0) / total_tracks * 100, 2)
                if total_tracks
                else 0.0
            ),
        },
        "tempo": {
            "avg_bpm": (
                round(feature_stats.avg_bpm, 2) if feature_stats.avg_bpm is not None else None
            ),
            "min_bpm": feature_stats.min_bpm,
            "max_bpm": feature_stats.max_bpm,
        },
        "loudness": {
            "avg_integrated_lufs": (
                round(feature_stats.avg_lufs, 2) if feature_stats.avg_lufs is not None else None
            ),
            "min_integrated_lufs": feature_stats.min_lufs,
            "max_integrated_lufs": feature_stats.max_lufs,
        },
        "mood_distribution": mood_distribution,
        "key_distribution": key_distribution,
        "top_artists": top_artists,
        "top_genres": top_genres,
        "track_sample": {
            "limit": page_limit,
            "offset": page_offset,
            "returned": len(track_sample),
            "rows": track_sample,
        },
    }
    return json_resource(data)


@resource(
    uri="catalog://stats{?mood,bpm_min,bpm_max}",
    name="Catalog Statistics",
    title="Catalog Statistics",
    description="Filtered catalog statistics with optional mood and BPM range filters",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def catalog_stats(
    mood: Annotated[TechnoSubgenre | None, "Filter by mood/subgenre"] = None,
    bpm_min: Annotated[float | None, "Minimum BPM"] = None,
    bpm_max: Annotated[float | None, "Maximum BPM"] = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
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
    t = TrackAudioFeaturesComputed
    filters: list[Any] = []
    if mood:
        filters.append(t.mood == mood.value)
    if bpm_min is not None:
        filters.append(t.bpm >= bpm_min)
    if bpm_max is not None:
        filters.append(t.bpm <= bpm_max)
    where_clause = and_(*filters) if filters else None

    def _apply_filters(stmt: Any) -> Any:
        return stmt.where(where_clause) if where_clause is not None else stmt

    count_stmt = _apply_filters(select(func.count()).select_from(t))
    avg_bpm_stmt = _apply_filters(select(func.avg(t.bpm)).select_from(t))
    avg_lufs_stmt = _apply_filters(select(func.avg(t.integrated_lufs)).select_from(t))

    total_tracks = (await session.execute(count_stmt)).scalar() or 0
    avg_bpm = (await session.execute(avg_bpm_stmt)).scalar()
    avg_energy = (await session.execute(avg_lufs_stmt)).scalar()

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

    # One GROUP BY instead of N per-subgenre COUNTs; honors bpm filters like the aggregates above.
    if not mood:
        mood_stmt = select(t.mood, func.count()).select_from(t).where(t.mood.isnot(None))
        mood_stmt = _apply_filters(mood_stmt)
        mood_stmt = mood_stmt.group_by(t.mood)
        rows = await session.execute(mood_stmt)
        mood_distribution = {str(m): int(c) for m, c in rows if m is not None and c}
        data["mood_distribution"] = mood_distribution

    return json_resource(data)

"""Track tools — list, get, manage, features (4 tools, tag: core).

Thin wrappers calling :class:`TrackService` via ``Depends()``. All
entity resolution, parsing and taxonomy live in
:mod:`app.controllers.tools._shared` and :mod:`app.core.utils.parsing`.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_feature_repo, get_track_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ICON_TRACKS,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
    resolve_track_id,
)
from app.core.utils.parsing import ensure_dict
from app.db.repositories.feature import FeatureRepository
from app.schemas import PaginatedResponse, TrackBrief, TrackStandard
from app.services.track_service import TrackService

TrackManageAction = Literal["create", "update", "archive", "unarchive"]


def _parse_json(value: str | None) -> Any:
    """Parse a JSON string, returning ``None`` on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


@tool(
    title="List Tracks",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
@map_domain_errors
async def list_tracks(
    limit: Annotated[int, Field(description="Page size", ge=1)] = 20,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from previous page")
    ] = None,
    bpm_min: Annotated[float | None, Field(description="Minimum BPM filter")] = None,
    bpm_max: Annotated[float | None, Field(description="Maximum BPM filter")] = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> PaginatedResponse[TrackBrief]:
    """Lists tracks with optional BPM bounds and cursor pagination. Use when exploring the catalog or narrowing candidates by tempo."""
    if bpm_min is not None or bpm_max is not None:
        page = await svc.filter_by_features(
            bpm_min=bpm_min, bpm_max=bpm_max, limit=limit, cursor=cursor
        )
    else:
        page = await svc.list_all(limit=limit, cursor=cursor)

    track_ids = [t.id for t in page.items]
    artist_map = await svc.get_artist_names_batch(track_ids)
    features_map = await feat_repo.get_features_batch(track_ids)

    return PaginatedResponse[TrackBrief](
        items=[
            svc.to_brief(
                t,
                features=features_map.get(t.id),
                artist_names=artist_map.get(t.id),
            )
            for t in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@tool(
    title="Get Track",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_track(
    id: Annotated[int | None, Field(description="Local track ID")] = None,
    query: Annotated[str | None, Field(description="Text search to resolve track")] = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Returns full track details resolved by local id or text search. Use when you need complete metadata for one specific track."""
    track_id = await resolve_track_id(entity_id=id, query=query, search=svc.search)
    track, features = await svc.get_with_features(track_id)
    artist_map = await svc.get_artist_names_batch([track_id])
    return svc.to_standard(track, features, artist_names=artist_map.get(track_id))


@tool(
    title="Manage Tracks",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
@map_domain_errors
async def manage_tracks(
    action: Annotated[TrackManageAction, Field(description="Operation to perform")],
    data: Annotated[
        Any, Field(description="Dict with 'title' (create) or 'id' + fields (update/archive)")
    ] = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Creates, updates, archives, or unarchives a track from an action and payload. Use when curating the library or correcting a single track record."""

    data_dict = ensure_dict(data)

    if action == "create":
        if not data_dict or "title" not in data_dict:
            raise ToolError("data.title required for create")
        track = await svc.create(data_dict["title"], data_dict.get("duration_ms"))
        return svc.to_standard(track)

    track_id = (data_dict or {}).get("id")
    if track_id is None:
        raise ToolError("data.id required")

    if action == "archive":
        track = await svc.archive(track_id)
    elif action == "unarchive":
        track = await svc.unarchive(track_id)
    else:  # action == "update"
        assert data_dict is not None  # type narrowing for mypy
        fields = {k: v for k, v in data_dict.items() if k != "id"}
        track = await svc.update(track_id, **fields)

    artist_map = await svc.get_artist_names_batch([track_id])
    return svc.to_standard(track, artist_names=artist_map.get(track_id))


@tool(
    title="Get Track Features",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_track_features(
    id: Annotated[int | None, Field(description="Local track ID")] = None,
    query: Annotated[str | None, Field(description="Text search to resolve track")] = None,
    include_sections: Annotated[
        bool, Field(description="Include phrase/section breakdown when available")
    ] = False,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> dict[str, Any]:
    """Returns analyzed audio features for a track resolved by id or query, optionally including phrase sections. Use when planning mixes, scoring transitions, or auditing analysis output."""
    track_id = await resolve_track_id(entity_id=id, query=query, search=svc.search)
    track, features = await svc.get_with_features(track_id)

    if features is None:
        return {"track_id": track.id, "title": track.title, "has_features": False}

    response: dict[str, Any] = {
        "track_id": track.id,
        "title": track.title,
        "has_features": True,
        "analysis_level": features.analysis_level,
        "tempo": {
            "bpm": features.bpm,
            "confidence": features.bpm_confidence,
            "stability": features.bpm_stability,
        },
        "loudness": {"integrated_lufs": features.integrated_lufs},
        "energy": {"mean": features.energy_mean, "max": features.energy_max},
        "spectral": {
            "centroid_hz": features.spectral_centroid_hz,
            "flatness": features.spectral_flatness,
            "contrast": features.spectral_contrast,
        },
        "key": {"key_code": features.key_code, "confidence": features.key_confidence},
        "rhythm": {
            "kick_prominence": features.kick_prominence,
            "onset_rate": features.onset_rate,
            "pulse_clarity": features.pulse_clarity,
            "hp_ratio": features.hp_ratio,
        },
        "mood": features.mood,
        "advanced": {
            "danceability": features.danceability,
            "dissonance_mean": features.dissonance_mean,
            "dynamic_complexity": features.dynamic_complexity,
            "spectral_complexity_mean": features.spectral_complexity_mean,
            "pitch_salience_mean": features.pitch_salience_mean,
        },
        "phrase": {
            "boundaries_ms": (
                _parse_json(features.phrase_boundaries_ms)
                if features.phrase_boundaries_ms
                else None
            ),
            "dominant_phrase_bars": getattr(features, "dominant_phrase_bars", None),
        },
        "bpm_histogram": {
            "first_peak_weight": features.bpm_histogram_first_peak_weight,
            "second_peak_bpm": features.bpm_histogram_second_peak_bpm,
            "second_peak_weight": features.bpm_histogram_second_peak_weight,
        },
        "tonnetz": (_parse_json(features.tonnetz_vector) if features.tonnetz_vector else None),
    }

    if include_sections:
        response["sections"] = await svc.get_track_sections(track.id)

    return response

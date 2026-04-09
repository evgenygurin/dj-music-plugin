"""Track tools — list, get, manage, features (4 tools, tag: core).

Thin wrappers calling :class:`TrackService` via ``Depends()``. All
entity resolution, parsing and taxonomy live in
:mod:`app.controllers.tools._shared` and :mod:`app.core.utils.parsing`.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.controllers.dependencies import get_feature_repo, get_track_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    map_domain_errors,
    resolve_track_id,
)
from app.core.utils.parsing import ensure_dict
from app.db.repositories.feature import FeatureRepository
from app.schemas import PaginatedResponse, TrackBrief, TrackStandard
from app.services.track_service import TrackService

_TRACK_ACTIONS = frozenset({"create", "update", "archive", "unarchive"})


def _parse_json(value: str | None) -> Any:
    """Parse a JSON string, returning ``None`` on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> PaginatedResponse[TrackBrief]:
    """List tracks with optional filters and cursor pagination.

    BPM and Camelot key are populated from a single batched
    ``FeatureRepository.get_features_batch`` query — no per-track N+1
    lookup.
    """
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


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_track(
    id: int | None = None,
    query: str | None = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Get full track details by id or text query."""
    track_id = await resolve_track_id(entity_id=id, query=query, search=svc.search)
    track, features = await svc.get_with_features(track_id)
    artist_map = await svc.get_artist_names_batch([track_id])
    return svc.to_standard(track, features, artist_names=artist_map.get(track_id))


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def manage_tracks(
    action: str,
    data: Any = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Create, update, archive or unarchive a track.

    ``action`` ∈ ``{create, update, archive, unarchive}``.
    """
    if action not in _TRACK_ACTIONS:
        raise ToolError(f"Unknown action: {action}")

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


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_track_features(
    id: int | None = None,
    query: str | None = None,
    include_sections: bool = False,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> dict[str, Any]:
    """Get audio features for a track by id or query. Optionally include sections."""
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

"""Handler for entity_update(entity="track_features", data={track_id, level}).

Unlike the create handler, reanalyze always runs the pipeline regardless of
current analysis level. Use when a bug in the analyzer is fixed and features
need to be recomputed.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context

from app.handlers._beatport_enrich import enrich_beatport_genre
from app.handlers._context_log import safe_info, safe_report_progress
from app.handlers.track_features_analyze import AnalysisPipeline
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError


async def track_features_reanalyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
    registry: ProviderRegistry | None = None,
) -> dict[str, Any]:
    # entity_update wraps the primary key under "id"; the primary key of
    # TrackAudioFeaturesComputed is track_id, so either form is accepted.
    raw = data.get("track_id") if data.get("track_id") is not None else data.get("id")
    if raw is None:
        raise ValueError("track_features_reanalyze requires track_id or id in data")
    track_id: int = int(raw)
    level: int = int(data.get("level", 3))

    track = await uow.tracks.get(track_id)
    if track is None:
        raise NotFoundError("track", track_id)

    lib = await uow.audio_files.get_by_track_id(track_id)
    if lib is None:
        raise NotFoundError("audio_file", track_id)

    await safe_report_progress(ctx, progress=0, total=1, message=f"reanalyzing track {track_id}")

    result = await pipeline.analyze(lib.file_path)

    await safe_report_progress(
        ctx, progress=0.5, total=1, message=f"saving features for track {track_id}"
    )
    await uow.track_features.upsert_analysis(
        track_id=track_id,
        analysis_level=level,
        **result.features,
    )
    beatport = await enrich_beatport_genre(
        ctx, uow, registry, track_id=track_id, track=track, features=result.features
    )

    await safe_report_progress(ctx, progress=1, total=1, message=f"reanalyzed track {track_id}")

    await safe_info(ctx, f"reanalyzed track {track_id} at L{level}")

    return {
        "track_id": track_id,
        "level": level,
        "feature_count": len(result.features),
        "beatport_genre": (beatport or {}).get("genre"),
    }

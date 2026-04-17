"""Handler for entity_update(entity="track_features", data={track_id, level}).

Unlike the create handler, reanalyze always runs the pipeline regardless of
current analysis level. Use when a bug in the analyzer is fixed and features
need to be recomputed.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context

from app.handlers.track_features_analyze import AnalysisPipeline
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError


async def track_features_reanalyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
) -> dict[str, Any]:
    track_id: int = int(data["track_id"])
    level: int = int(data.get("level", 3))

    track = await uow.tracks.get(track_id)
    if track is None:
        raise NotFoundError("track", track_id)

    lib = await uow.audio_files.get_by_track_id(track_id)
    if lib is None:
        raise NotFoundError("audio_file", track_id)

    result = await pipeline.analyze_to_level(
        track_id=track_id, audio_path=lib.file_path, level=level
    )
    await uow.track_features.upsert(
        track_id=track_id,
        pipeline_run_id=result.pipeline_run_id,
        analysis_level=result.analysis_level,
        **result.features,
    )
    await ctx.info(f"reanalyzed track {track_id} at L{level}")

    return {
        "track_id": track_id,
        "level": result.analysis_level,
        "pipeline_run_id": result.pipeline_run_id,
        "feature_count": len(result.features),
    }

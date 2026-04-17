"""Handler for entity_create(entity="track_features", data={track_ids, level, force}).

Runs the audio analysis pipeline (TieredPipeline analogue) on each track at the
requested analysis level (L1-L4). Idempotent: skips tracks already at target
level unless force=True. Emits per-track progress.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.repositories.unit_of_work import UnitOfWork


class AnalysisPipeline(Protocol):
    async def analyze_to_level(self, *, track_id: int, audio_path: str, level: int) -> Any: ...


async def track_features_analyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
) -> dict[str, Any]:
    track_ids: list[int] = [int(x) for x in data["track_ids"]]
    level: int = int(data.get("level", 3))
    force: bool = bool(data.get("force", False))

    analyzed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    total = len(track_ids)
    for i, tid in enumerate(track_ids):
        track = await uow.tracks.get(tid)
        if track is None:
            errors.append({"track_id": tid, "error": "track not found"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        existing = await uow.track_features.get_by_track_id(tid)
        if existing is not None and not force:
            current_level = int(getattr(existing, "analysis_level", 0) or 0)
            if current_level >= level:
                skipped.append({"track_id": tid, "current_level": current_level, "target": level})
                await ctx.report_progress(progress=i + 1, total=total)
                continue

        lib = await uow.audio_files.get_by_track_id(tid)
        if lib is None:
            errors.append({"track_id": tid, "error": "no audio file registered"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            result = await pipeline.analyze_to_level(
                track_id=tid, audio_path=lib.file_path, level=level
            )
        except Exception as exc:
            errors.append({"track_id": tid, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        await uow.track_features.upsert(
            track_id=tid,
            pipeline_run_id=result.pipeline_run_id,
            analysis_level=result.analysis_level,
            **result.features,
        )
        analyzed.append(
            {
                "track_id": tid,
                "level": result.analysis_level,
                "feature_count": len(result.features),
                "errors": len(getattr(result, "errors", []) or []),
            }
        )
        await ctx.report_progress(progress=i + 1, total=total)

    await ctx.info(
        f"features_analyze L{level}: {len(analyzed)} analyzed, "
        f"{len(skipped)} skipped, {len(errors)} errors"
    )

    return {"analyzed": analyzed, "skipped": skipped, "errors": errors}

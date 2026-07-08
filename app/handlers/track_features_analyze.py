"""Handler for entity_create(entity="track_features", data={track_id(s), level, force}).

Runs the audio analysis pipeline (TieredPipeline analogue) on each track at the
requested analysis level (L1-L4). Idempotent: skips tracks already at target
level unless force=True. Emits per-track progress.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.handlers._beatport_enrich import enrich_beatport_genre
from app.handlers._context_log import safe_info, safe_report_progress
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork


class AnalysisPipeline(Protocol):
    """Structural type for ``app.audio.pipeline.AnalysisPipeline``.

    The real class exposes ``analyze(file_path: str, ...)`` returning a
    ``PipelineResult`` with ``.features`` (dict) and ``.errors`` (list).
    """

    async def analyze(self, file_path: str) -> Any: ...


async def track_features_analyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
    registry: ProviderRegistry | None = None,
) -> dict[str, Any]:
    raw_track_ids = data.get("track_ids")
    if raw_track_ids is None:
        raw_track_ids = [data["track_id"]]
    track_ids: list[int] = [int(x) for x in raw_track_ids]
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
            await safe_report_progress(ctx, progress=i + 1, total=total)
            continue

        existing = await uow.track_features.get_by_track_id(tid)
        if existing is not None and not force:
            current_level = int(getattr(existing, "analysis_level", 0) or 0)
            if current_level >= level:
                skipped.append({"track_id": tid, "current_level": current_level, "target": level})
                await safe_report_progress(ctx, progress=i + 1, total=total)
                continue

        lib = await uow.audio_files.get_by_track_id(tid)
        if lib is None:
            errors.append({"track_id": tid, "error": "no audio file registered"})
            await safe_report_progress(ctx, progress=i + 1, total=total)
            continue

        try:
            result = await pipeline.analyze(lib.file_path)
        except Exception as exc:
            errors.append({"track_id": tid, "error": str(exc)})
            await safe_report_progress(ctx, progress=i + 1, total=total)
            continue

        # The repository's upsert strips columns unknown to the ORM, so
        # anything extra in ``result.features`` is silently dropped — safe
        # to splat the whole feature dict here. ``analysis_level`` records
        # the caller-requested tier (L1..L5); the pipeline itself is
        # level-agnostic and runs whatever analyzers are enabled.
        await uow.track_features.upsert_analysis(
            track_id=tid,
            analysis_level=level,
            **result.features,
        )
        # Best-effort Beatport ground-truth genre (never fails analysis).
        beatport = await enrich_beatport_genre(
            ctx, uow, registry, track_id=tid, track=track, features=result.features
        )
        analyzed.append(
            {
                "track_id": tid,
                "level": level,
                "feature_count": len(result.features),
                "errors": len(getattr(result, "errors", []) or []),
                "beatport_genre": (beatport or {}).get("genre"),
            }
        )
        await safe_report_progress(ctx, progress=i + 1, total=total)

    await safe_info(
        ctx,
        f"features_analyze L{level}: {len(analyzed)} analyzed, "
        f"{len(skipped)} skipped, {len(errors)} errors",
    )

    return {"analyzed": analyzed, "skipped": skipped, "errors": errors}

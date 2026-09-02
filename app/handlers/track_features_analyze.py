"""Handler for entity_create(entity="track_features", data={track_ids, level, force}).

Runs the audio analysis pipeline on each track at the requested analysis level (L1-L4).
Idempotent: skips tracks already at target level unless force=True.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.handlers._batch import BaseBatchHandler
from app.handlers._beatport_enrich import enrich_beatport_genre
from app.handlers._context_log import safe_report_progress
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork


class AnalysisPipeline(Protocol):
    """Structural type for ``app.audio.pipeline.AnalysisPipeline``."""

    async def analyze(self, file_path: str) -> Any: ...


class TrackFeaturesAnalyzeHandler(BaseBatchHandler[int]):
    """Batch-analyze tracks via the audio pipeline."""

    def __init__(
        self, pipeline: AnalysisPipeline, registry: ProviderRegistry | None = None
    ) -> None:
        self._pipeline = pipeline
        self._registry = registry

    def parse_ids(self, data: dict[str, Any]) -> list[int]:
        return [int(x) for x in data["track_ids"]]

    async def _pre_check(
        self, uow: UnitOfWork, item_id: int, data: dict[str, Any], **deps: Any
    ) -> dict[str, Any] | None:
        level: int = int(data.get("level", 3))
        force: bool = bool(data.get("force", False))
        existing = await uow.track_features.get_by_track_id(item_id)
        if existing is not None and not force:
            current_level = int(getattr(existing, "analysis_level", 0) or 0)
            if current_level >= level:
                return {"id": item_id, "reason": f"already at L{current_level} (target L{level})"}
        return None

    async def process_one(
        self,
        ctx: Context,
        uow: UnitOfWork,
        item_id: int,
        data: dict[str, Any],
        *,
        index: int = 0,
        total: int = 1,
        **deps: Any,
    ) -> dict[str, Any]:
        level: int = int(data.get("level", 3))

        await safe_report_progress(
            ctx,
            progress=index + 1,
            total=total,
            message=f"track {index + 1}/{total}: loading metadata",
        )

        track = await uow.tracks.get(item_id)
        if track is None:
            raise LookupError("track not found")

        lib = await uow.audio_files.get_by_track_id(item_id)
        if lib is None:
            raise LookupError("no audio file registered")

        title = track.title or f"track_{item_id}"

        await safe_report_progress(
            ctx,
            progress=index + 1,
            total=total,
            message=f"track {index + 1}/{total}: {title} — running audio pipeline",
        )

        result = await self._pipeline.analyze(lib.file_path)

        await safe_report_progress(
            ctx,
            progress=index + 1,
            total=total,
            message=f"track {index + 1}/{total}: {title} — saving features",
        )

        await uow.track_features.upsert_analysis(
            track_id=item_id,
            analysis_level=level,
            **result.features,
        )

        await safe_report_progress(
            ctx,
            progress=index + 1,
            total=total,
            message=f"track {index + 1}/{total}: {title} — enriching metadata",
        )

        beatport = await enrich_beatport_genre(
            ctx, uow, self._registry, track_id=item_id, track=track, features=result.features
        )

        return {
            "track_id": item_id,
            "level": level,
            "feature_count": len(result.features),
            "errors": len(getattr(result, "errors", []) or []),
            "beatport_genre": (beatport or {}).get("genre"),
        }

    def success_key(self) -> str:
        return "analyzed"

    def summary_message(self, *, ok: int, skipped: int, errors: int) -> str:
        return f"features_analyze: {ok} analyzed, {skipped} skipped, {errors} errors"


async def track_features_analyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
    registry: ProviderRegistry | None = None,
) -> dict[str, Any]:
    return await TrackFeaturesAnalyzeHandler(pipeline, registry).run(
        ctx, uow, data, pipeline=pipeline, registry=registry
    )

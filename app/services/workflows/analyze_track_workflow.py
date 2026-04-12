"""Workflow for audio analysis orchestration."""

from __future__ import annotations

from typing import Any

from app.audio.level_config import AnalysisLevel
from app.core.errors import ValidationError
from app.db.repositories.playlist import PlaylistRepository
from app.services.audio_service import AudioService
from app.services.tiered_pipeline import TieredPipeline
from app.services.workflows._helpers import call_async_method


class AnalyzeTrackWorkflow:
    """Owns single-track and batch analysis orchestration."""

    def __init__(
        self,
        audio_service: AudioService,
        tiered_pipeline: TieredPipeline,
        playlist_repo: PlaylistRepository,
    ) -> None:
        self._audio_service = audio_service
        self._tiered_pipeline = tiered_pipeline
        self._playlist_repo = playlist_repo

    @staticmethod
    def _resolve_level(level: int) -> AnalysisLevel:
        valid_levels = tuple(lv.value for lv in AnalysisLevel if lv != AnalysisLevel.NONE)
        if level not in valid_levels:
            raise ValidationError(
                f"Invalid level: {level}. Valid levels: {list(valid_levels)} "
                "(TRIAGE=2, SCORING=3, TRANSITION=4, ADVANCED=5)"
            )
        return AnalysisLevel(level)

    async def analyze_track(
        self,
        *,
        track_id: int,
        analyzers: list[str] | None = None,
        force: bool = False,
        level: int = 3,
        log: Any = None,
    ) -> dict[str, Any]:
        """Analyze a single track, choosing the appropriate pipeline path."""
        if analyzers is not None:
            await call_async_method(
                log, "info", f"Analyzing track {track_id} with custom analyzers..."
            )
            result = await self._audio_service.analyze_track(
                track_id,
                analyzers=analyzers,
                force=force,
            )
            if result.get("error") == "No audio file linked":
                await call_async_method(
                    log, "info", "No local file — falling back to tiered pipeline..."
                )
                analysis = await self._tiered_pipeline.ensure_level(
                    [track_id],
                    AnalysisLevel.SCORING,
                    force=force,
                )
                return {
                    "track_id": track_id,
                    "level": int(AnalysisLevel.SCORING),
                    "status": "analyzed" if analysis["analyzed"] > 0 else "error",
                    **analysis,
                }
            return result

        target = self._resolve_level(level)
        await call_async_method(log, "info", f"Tiered analysis L{level} for track {track_id}...")
        analysis = await self._tiered_pipeline.ensure_level([track_id], target, force=force)
        return {
            "track_id": track_id,
            "level": level,
            "status": "analyzed" if analysis["analyzed"] > 0 else "skipped",
            **analysis,
        }

    async def analyze_batch(
        self,
        *,
        track_ids: list[int] | None = None,
        playlist_id: int | None = None,
        batch_size: int = 20,
        analyzers: list[str] | None = None,
        level: int = 3,
        force: bool = False,
        progress: Any = None,
    ) -> dict[str, Any]:
        """Analyze a batch of tracks by IDs or playlist membership."""
        if track_ids is None and playlist_id is None:
            raise ValidationError("Provide track_ids or playlist_id")
        if track_ids is not None and playlist_id is not None:
            raise ValidationError("Provide track_ids or playlist_id, not both")

        ids_list = track_ids or []
        if playlist_id is not None:
            ids_list = await self._playlist_repo.get_track_ids(playlist_id)

        if not ids_list:
            raise ValidationError("No tracks to analyze")

        ids_list = ids_list[:batch_size]
        total = len(ids_list)
        await call_async_method(progress, "set_total", total)
        target = self._resolve_level(level)

        if analyzers is not None:
            completed = 0
            failed = 0
            skipped = 0
            await call_async_method(
                progress,
                "set_message",
                f"Analyzing {total} tracks with custom analyzers...",
            )

            for index, track_id in enumerate(ids_list):
                await call_async_method(
                    progress, "set_message", f"Track {index + 1}/{total} (id={track_id})"
                )
                result = await self._audio_service.analyze_track(
                    track_id,
                    analyzers=analyzers,
                    force=force,
                )
                if result.get("error") == "No audio file linked":
                    tiered = await self._tiered_pipeline.ensure_level(
                        [track_id], target, force=force
                    )
                    result = {"status": "analyzed" if tiered["analyzed"] > 0 else "error"}
                status = result.get("status", "error")
                if status == "analyzed":
                    completed += 1
                elif status == "cached":
                    skipped += 1
                else:
                    failed += 1
                await call_async_method(progress, "increment")

            return {
                "total_tracks": total,
                "completed": completed,
                "failed": failed,
                "skipped": skipped,
            }

        await call_async_method(progress, "set_message", f"Tiered batch L{level}: {total} tracks")
        analysis = await self._tiered_pipeline.ensure_level(ids_list, target, force=force)
        await call_async_method(progress, "increment", total)
        return {
            "total_tracks": total,
            "completed": analysis["analyzed"],
            "failed": analysis["failed"],
            "skipped": analysis["skipped"],
            "level": level,
        }

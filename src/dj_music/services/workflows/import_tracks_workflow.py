"""Workflow for import and download orchestration."""

from __future__ import annotations

from typing import Any

from dj_music.audio.level_config import AnalysisLevel
from dj_music.services.import_service import ImportService
from dj_music.services.tiered_pipeline import TieredPipeline
from dj_music.services.workflows._helpers import call_async_method


class ImportTracksWorkflow:
    """Owns import and download tool orchestration."""

    def __init__(self, import_service: ImportService, tiered_pipeline: TieredPipeline) -> None:
        self._import_service = import_service
        self._tiered_pipeline = tiered_pipeline

    async def import_tracks(
        self,
        *,
        track_refs: list[str],
        playlist_id: int | None = None,
        auto_analyze: bool = False,
        log: Any = None,
    ) -> dict[str, Any]:
        """Import YM tracks and optionally run scoring-level analysis."""
        result = await self._import_service.import_tracks(
            track_refs=track_refs,
            playlist_id=playlist_id,
        )

        await call_async_method(
            log,
            "info",
            f"Import complete: {result['imported']} new, "
            f"{result['skipped']} skipped, {result['enriched']} enriched",
        )
        if playlist_id is not None:
            await call_async_method(
                log,
                "info",
                f"Added {result['playlist_added']} tracks to playlist {playlist_id}",
            )

        if auto_analyze and result["id_mapping"]:
            local_ids = list(result["id_mapping"].values())
            await call_async_method(
                log,
                "info",
                f"Running L3 tiered analysis on {len(local_ids)} tracks...",
            )
            result["analysis"] = await self._tiered_pipeline.ensure_level(
                local_ids,
                AnalysisLevel.SCORING,
            )

        return result

    async def download_tracks(
        self,
        *,
        track_refs: list[str],
        target_dir: str | None = None,
        skip_existing: bool = True,
        prefer_bitrate: int = 320,
        log: Any = None,
    ) -> dict[str, Any]:
        """Download YM tracks and link them into the library."""
        total = len(track_refs)
        await call_async_method(log, "info", f"Starting download of {total} tracks...")

        result = await self._import_service.download_tracks(
            track_refs=track_refs,
            target_dir=target_dir,
            skip_existing=skip_existing,
            prefer_bitrate=prefer_bitrate,
        )

        await call_async_method(log, "progress", total, total)
        await call_async_method(
            log,
            "info",
            f"Done: {result['downloaded']} downloaded, {result['skipped']} skipped, "
            f"{result['linked_to_library']} linked, {result['failed']} failed",
        )
        return result

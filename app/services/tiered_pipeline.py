"""Tiered analysis pipeline -- lazy, level-aware, parallel."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from app._version import __version__ as _PIPELINE_VERSION
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.audio.pipeline import AnalysisPipeline
    from app.audio.timeseries import TimeseriesStorage
    from app.db.repositories.audio import AudioRepository
    from app.db.repositories.track import TrackRepository
    from app.ym.client import YandexMusicClient


class TieredPipeline:
    """Orchestrates tiered audio analysis with temp downloads.

    Downloads audio from YM to temp files, runs level-appropriate analyzers,
    persists features, and cleans up temp files automatically.
    """

    def __init__(
        self,
        audio_repo: AudioRepository,
        track_repo: TrackRepository,
        pipeline: AnalysisPipeline,
        ym_client: YandexMusicClient,
        timeseries: TimeseriesStorage | None = None,
    ) -> None:
        self._audio = audio_repo
        self._tracks = track_repo
        self._pipeline = pipeline
        self._ym = ym_client
        self._timeseries = timeseries

    async def ensure_level(
        self,
        track_ids: list[int],
        target_level: AnalysisLevel,
        *,
        force: bool = False,
        progress_callback: Any = None,
    ) -> dict[str, int]:
        """Ensure all tracks have at least target analysis level.

        Downloads temp files, runs level-appropriate analyzers,
        saves features, deletes temps.

        Audio download+analysis runs concurrently (CPU/network bound).
        DB writes are sequential — SQLAlchemy async session is not
        safe for concurrent flush() calls from multiple coroutines.

        Returns: {"analyzed": N, "skipped": N, "failed": N}
        """
        if force:
            need_analysis = list(track_ids)
        else:
            need_analysis = await self._audio.get_tracks_below_level(track_ids, target_level)
        if not need_analysis:
            return {"analyzed": 0, "skipped": len(track_ids), "failed": 0}

        # Resolve local track IDs to YM IDs
        ym_map = await self._tracks.resolve_local_ids_to_ym(need_analysis)

        # Determine concurrency based on level (download+analyze phase only)
        if target_level <= AnalysisLevel.TRIAGE:
            max_workers = settings.audio_triage_workers
        else:
            max_workers = settings.audio_scoring_workers

        # Phase 1: parallel download + analyze (no DB writes)
        sem = asyncio.Semaphore(max_workers)

        async def download_and_analyze(track_id: int) -> tuple[int, Any] | None:
            """Download + analyze audio; return (track_id, pipeline_result) or None."""
            ym_id = ym_map.get(track_id)
            if not ym_id:
                logger.warning("No YM ID for track %s — skipping", track_id)
                return None
            async with sem:
                return await self._download_and_analyze(track_id, ym_id, target_level)

        tasks = [download_and_analyze(tid) for tid in need_analysis]
        raw_results: list[tuple[int, Any] | None | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Phase 2: sequential DB writes (one session, no concurrent flush)
        analyzed = 0
        failed = 0
        for r in raw_results:
            if isinstance(r, BaseException):
                logger.error("Unexpected error during download/analyze: %s", r)
                failed += 1
            elif r is None:
                failed += 1
            else:
                track_id, result = r
                success = await self._save_analysis(track_id, result, target_level)
                if success:
                    analyzed += 1
                else:
                    failed += 1

        return {
            "analyzed": analyzed,
            "skipped": len(track_ids) - len(need_analysis),
            "failed": failed,
        }

    async def _download_and_analyze(
        self, track_id: int, ym_track_id: str, level: AnalysisLevel
    ) -> tuple[int, Any] | None:
        """Download temp audio + run pipeline analyzers. No DB writes.

        Returns (track_id, pipeline_result) on success, None on failure.
        """
        from app.audio.temp_download import temp_download_track

        analyzers = get_analyzers_for_level(level)
        save_ts = self._timeseries is not None and level >= AnalysisLevel.SCORING

        try:
            async with temp_download_track(self._ym, ym_track_id) as tmp_path:
                result = await self._pipeline.analyze(
                    str(tmp_path),
                    analyzers=analyzers,
                    return_context=save_ts,
                )
            return (track_id, result)
        except Exception:
            logger.exception(
                "Download/analyze failed for track %s (ym=%s, level=%s)",
                track_id,
                ym_track_id,
                level,
            )
            return None

    async def _save_analysis(self, track_id: int, result: Any, level: AnalysisLevel) -> bool:
        """Persist pipeline result to DB. Must be called sequentially (one session).

        Returns True on success.
        """
        try:
            if not result.features:
                logger.warning("No features extracted for track %s at level %s", track_id, level)
                return False

            # Extract non-column fields before saving features
            sections = result.features.pop("sections", None)
            result.features.pop("section_count", None)
            beat_times: list[float] | None = result.features.pop("beat_times", None)
            result.features.pop("beats_intervals", None)

            # Create pipeline run record for traceability
            run = await self._audio.create_pipeline_run(
                track_id=track_id,
                name=f"tiered_L{int(level)}",
                version=_PIPELINE_VERSION,
                status="completed",
            )

            await self._audio.save_or_update_features(
                track_id=track_id,
                features_dict=result.features,
                level=level,
                pipeline_run_id=run.id,
            )

            # Run mood classifier (rule-based, <1ms)
            await self._classify_mood(track_id)

            # Persist sections to track_sections table
            if sections:
                await self._audio.save_sections(track_id, sections)

            # Persist beatgrid from detected beat positions
            if beat_times and len(beat_times) >= 2:
                bpm = result.features.get("bpm")
                if bpm and bpm > 0:
                    # first_downbeat = first detected beat position
                    first_downbeat_ms = beat_times[0] * 1000.0
                    bpm_confidence = result.features.get("bpm_confidence")
                    variable_tempo = bool(result.features.get("variable_tempo", False))
                    await self._audio.save_beatgrid(
                        track_id=track_id,
                        bpm=bpm,
                        first_downbeat_ms=first_downbeat_ms,
                        confidence=bpm_confidence,
                        variable_tempo=variable_tempo,
                    )

            # Save frame-level timeseries data (if collected)
            save_ts = self._timeseries is not None and level >= AnalysisLevel.SCORING
            if save_ts and result.context is not None and self._timeseries is not None:
                await self._save_timeseries(track_id, result.context)

            return True
        except Exception:
            logger.exception(
                "DB save failed for track %s (level=%s)",
                track_id,
                level,
            )
            return False

    async def _classify_mood(self, track_id: int) -> None:
        """Run rule-based mood classifier on saved features."""
        from app.audio.classification import MoodClassifier

        row = await self._audio.get_features_by_track_id(track_id)
        if row is None:
            return
        feat_dict = row.to_classifier_dict()
        classifier = MoodClassifier()
        result = classifier.classify(feat_dict)
        await self._audio.update_mood(row, result.mood.value, result.confidence)

    async def _save_timeseries(self, track_id: int, ctx: Any) -> None:
        """Save frame-level data from AnalysisContext to disk + DB reference."""
        import numpy as np

        assert self._timeseries is not None

        # Save energy timeseries
        if ctx.frame_energies is not None and len(ctx.frame_energies) > 0:
            metadata = self._timeseries.save(
                track_id=track_id,
                feature_set_name="energy",
                data={"energy": np.asarray(ctx.frame_energies)},
                hop_length=ctx.params.hop_length,
                sample_rate=ctx.sr,
            )
            await self._audio.save_timeseries_reference(track_id, metadata)

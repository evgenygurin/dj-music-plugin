"""Tiered analysis pipeline -- lazy, level-aware, parallel."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.audio.pipeline import AnalysisPipeline
    from app.audio.timeseries import TimeseriesStorage
    from app.repositories.audio import AudioRepository
    from app.repositories.track import TrackRepository
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
        progress_callback: Any = None,
    ) -> dict[str, int]:
        """Ensure all tracks have at least target analysis level.

        Downloads temp files, runs level-appropriate analyzers,
        saves features, deletes temps.

        Returns: {"analyzed": N, "skipped": N, "failed": N}
        """
        need_analysis = await self._audio.get_tracks_below_level(track_ids, target_level)
        if not need_analysis:
            return {"analyzed": 0, "skipped": len(track_ids), "failed": 0}

        # Resolve local track IDs to YM IDs
        ym_map = await self._tracks.resolve_local_ids_to_ym(need_analysis)

        # Determine concurrency based on level
        if target_level <= AnalysisLevel.TRIAGE:
            max_workers = settings.audio_triage_workers
        else:
            max_workers = settings.audio_scoring_workers

        sem = asyncio.Semaphore(max_workers)
        analyzed = 0
        failed = 0

        async def process_one(track_id: int) -> bool:
            ym_id = ym_map.get(track_id)
            if not ym_id:
                return False
            async with sem:
                return await self._analyze_at_level(track_id, ym_id, target_level)

        tasks = [process_one(tid) for tid in need_analysis]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if r is True:
                analyzed += 1
            else:
                failed += 1

        return {
            "analyzed": analyzed,
            "skipped": len(track_ids) - len(need_analysis),
            "failed": failed,
        }

    async def _analyze_at_level(
        self, track_id: int, ym_track_id: str, level: AnalysisLevel
    ) -> bool:
        """Download temp -> analyze -> save features -> delete temp."""
        from app.audio.temp_download import temp_download_track

        analyzers = get_analyzers_for_level(level)

        try:
            async with temp_download_track(self._ym, ym_track_id) as tmp_path:
                save_ts = self._timeseries is not None and level >= AnalysisLevel.SCORING
                result = await self._pipeline.analyze(
                    str(tmp_path),
                    analyzers=analyzers,
                    return_context=save_ts,
                )
                if result.features:
                    # Extract sections before saving features (not a DB column)
                    sections = result.features.pop("sections", None)
                    result.features.pop("section_count", None)

                    await self._audio.save_or_update_features(
                        track_id=track_id,
                        features_dict=result.features,
                        level=level,
                    )

                    # Run mood classifier (rule-based, <1ms)
                    await self._classify_mood(track_id)

                    # Persist sections to track_sections table
                    if sections:
                        await self._audio.save_sections(track_id, sections)

                    # Save frame-level timeseries data
                    if save_ts and result.context is not None and self._timeseries is not None:
                        await self._save_timeseries(track_id, result.context)

                    return True
        except Exception:
            logger.exception(
                "Tiered analysis failed for track %s (ym=%s, level=%s)",
                track_id,
                ym_track_id,
                level,
            )
            return False
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

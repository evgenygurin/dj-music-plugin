"""Audio analysis + mood classification service.

Framework-agnostic: no MCP/FastMCP imports.
Receives session and registry via constructor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.mood import MoodClassifier
from app.audio.pipeline import AnalysisPipeline
from app.audio.registry import AnalyzerRegistry
from app.config import settings
from app.models.audio import FeatureExtractionRun, TrackAudioFeaturesComputed
from app.models.library import DjLibraryItem
from app.models.track import Track

logger = logging.getLogger(__name__)


class AudioService:
    """Audio analysis + mood classification. Framework-agnostic."""

    def __init__(self, session: AsyncSession, registry: AnalyzerRegistry) -> None:
        self._session = session
        self._registry = registry

    async def analyze_track(
        self,
        track_id: int,
        analyzers: list[str] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Full pipeline: load audio -> analyze -> save features -> classify mood.

        Returns dict with status, feature_count, mood, errors.
        """
        # 1. Verify track exists
        track = (
            await self._session.execute(select(Track).where(Track.id == track_id))
        ).scalar_one_or_none()
        if not track:
            return {"track_id": track_id, "status": "error", "error": "Track not found"}

        # 2. Check cache
        if not force:
            existing = (
                await self._session.execute(
                    select(TrackAudioFeaturesComputed).where(
                        TrackAudioFeaturesComputed.track_id == track_id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                # If features exist but mood is missing, classify now
                if existing.mood is None:
                    await self._classify_existing(existing)
                return {
                    "track_id": track_id,
                    "status": "cached",
                    "has_features": True,
                    "mood": existing.mood,
                }

        # 3. Find audio file
        lib_item = (
            await self._session.execute(
                select(DjLibraryItem).where(DjLibraryItem.track_id == track_id)
            )
        ).scalar_one_or_none()

        if not lib_item or not lib_item.file_path:
            return {"track_id": track_id, "status": "error", "error": "No audio file linked"}

        file_path = Path(lib_item.file_path)
        if not file_path.exists():
            return {
                "track_id": track_id,
                "status": "error",
                "error": f"File not found: {file_path}",
            }

        # 4. Check iCloud stub
        stat = file_path.stat()
        if (
            hasattr(stat, "st_blocks")
            and stat.st_blocks * 512 < stat.st_size * settings.delivery_icloud_stub_threshold
        ):
            return {
                "track_id": track_id,
                "status": "error",
                "error": "iCloud stub (not downloaded)",
            }

        # 5. Run analysis pipeline
        pipeline = AnalysisPipeline(self._registry)
        result = await pipeline.analyze(str(file_path), analyzers=analyzers)

        # 6. Create FeatureExtractionRun
        run = FeatureExtractionRun(
            track_id=track_id,
            pipeline_name="audio_service",
            pipeline_version="1.0",
            status="completed",
        )
        self._session.add(run)
        await self._session.flush()

        # 7. Save features (upsert: delete old if force)
        if force:
            old = (
                await self._session.execute(
                    select(TrackAudioFeaturesComputed).where(
                        TrackAudioFeaturesComputed.track_id == track_id
                    )
                )
            ).scalar_one_or_none()
            if old:
                await self._session.delete(old)
                await self._session.flush()

        features = TrackAudioFeaturesComputed(
            track_id=track_id,
            pipeline_run_id=run.id,
            **TrackAudioFeaturesComputed.filter_features(result.features),
        )
        self._session.add(features)
        await self._session.flush()

        # 8. Auto-classify mood
        mood_result = await self._classify_existing(features)

        return {
            "track_id": track_id,
            "status": "analyzed",
            "analyzers_run": getattr(result, "analyzers_run", []),
            "errors": getattr(result, "errors", []),
            "feature_count": len(result.features) if hasattr(result, "features") else 0,
            "mood": mood_result.get("mood") if mood_result else None,
            "mood_confidence": mood_result.get("confidence") if mood_result else None,
        }

    async def classify_track(self, track_id: int) -> dict[str, Any]:
        """Classify mood for a track with existing features."""
        features = (
            await self._session.execute(
                select(TrackAudioFeaturesComputed).where(
                    TrackAudioFeaturesComputed.track_id == track_id
                )
            )
        ).scalar_one_or_none()

        if not features:
            return {"track_id": track_id, "status": "error", "error": "No features"}

        result = await self._classify_existing(features)
        return (
            {"track_id": track_id, **result}
            if result
            else {"track_id": track_id, "status": "error"}
        )

    async def _classify_existing(
        self, features: TrackAudioFeaturesComputed
    ) -> dict[str, Any] | None:
        """Run MoodClassifier on existing features and persist mood."""
        feat_dict = {
            "bpm": features.bpm,
            "integrated_lufs": features.integrated_lufs,
            "energy_mean": features.energy_mean,
            "energy_max": features.energy_max,
            "energy_std": features.energy_std,
            "energy_slope": features.energy_slope,
            "spectral_centroid_hz": features.spectral_centroid_hz,
            "spectral_flatness": features.spectral_flatness,
            "spectral_flux_mean": features.spectral_flux_mean,
            "spectral_flux_std": features.spectral_flux_std,
            "loudness_range_lu": features.loudness_range_lu,
            "crest_factor_db": features.crest_factor_db,
            "hp_ratio": features.hp_ratio,
            "onset_rate": features.onset_rate,
            "pulse_clarity": features.pulse_clarity,
            "kick_prominence": features.kick_prominence,
            "hnr_db": features.hnr_db,
        }

        classifier = MoodClassifier()
        result = classifier.classify(feat_dict)

        # Persist
        features.mood = result.mood.value
        features.mood_confidence = result.confidence
        await self._session.flush()

        return {
            "mood": result.mood.value,
            "confidence": round(result.confidence, 3),
            "reasoning": result.reasoning,
        }

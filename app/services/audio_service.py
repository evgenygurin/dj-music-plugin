"""Audio analysis + mood classification service.

Framework-agnostic: no MCP/FastMCP imports.
Receives AudioRepository and registry via constructor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.audio.classification import MoodClassifier
from app.audio.pipeline import AnalysisPipeline

if TYPE_CHECKING:
    from app.audio.analyzers import AnalyzerRegistry
    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.repositories.audio import AudioRepository

logger = logging.getLogger(__name__)


class AudioService:
    """Audio analysis + mood classification. Framework-agnostic."""

    def __init__(self, repo: AudioRepository, registry: AnalyzerRegistry) -> None:
        self._repo = repo
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
        track = await self._repo.get_track(track_id)
        if not track:
            return {"track_id": track_id, "status": "error", "error": "Track not found"}

        # 2. Check cache
        if not force:
            existing = await self._repo.get_features_by_track_id(track_id)
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
        lib_item = await self._repo.get_library_item_by_track_id(track_id)

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
        from app.core.utils.files import is_icloud_stub

        if is_icloud_stub(file_path):
            return {
                "track_id": track_id,
                "status": "error",
                "error": "iCloud stub (not downloaded)",
            }

        # 5. Run analysis pipeline
        pipeline = AnalysisPipeline(self._registry)
        result = await pipeline.analyze(str(file_path), analyzers=analyzers)

        # 6. Create FeatureExtractionRun
        run = await self._repo.create_pipeline_run(
            track_id=track_id,
            name="audio_service",
            version="1.0",
        )

        # 7. Extract sections before saving features (not a DB column)
        sections = result.features.pop("sections", None)
        result.features.pop("section_count", None)

        # 8. Save features (upsert: delete old if force)
        if force:
            await self._repo.delete_features(track_id)

        from app.db.models.audio import TrackAudioFeaturesComputed

        features = await self._repo.create_features_from_pipeline(
            track_id=track_id,
            features_dict=TrackAudioFeaturesComputed.filter_features(result.features),
            pipeline_run_id=run.id,
        )

        # 9. Persist sections to track_sections table
        if sections:
            await self._repo.save_sections(track_id, sections)

        # 10. Auto-classify mood
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
        features = await self._repo.get_features_by_track_id(track_id)

        if not features:
            return {"track_id": track_id, "status": "error", "error": "No features"}

        result = await self._classify_existing(features)
        return (
            {"track_id": track_id, **result}
            if result
            else {"track_id": track_id, "status": "error"}
        )

    async def gate_track(
        self,
        track_id: int,
        criteria: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Check a track against audio quality criteria. Returns pass/fail + reasons."""
        from app.config import settings

        features = await self._repo.get_features_by_track_id(track_id)

        if not features:
            return {"track_id": track_id, "passed": None, "reasons": ["no_features"]}

        reasons: list[str] = []

        def _check(name: str, value: float | None, op: str, threshold: float) -> None:
            if value is None:
                return
            if op == ">=" and value < threshold:
                reasons.append(f"{name}={value:.2f} (<{threshold})")
            elif op == "<=" and value > threshold:
                reasons.append(f"{name}={value:.2f} (>{threshold})")

        c = criteria or {}
        _check("bpm", features.bpm, ">=", c.get("bpm_min", settings.techno_bpm_min))
        _check("bpm", features.bpm, "<=", c.get("bpm_max", settings.techno_bpm_max))
        _check("lufs", features.integrated_lufs, ">=", c.get("lufs_min", settings.techno_lufs_min))
        _check("lufs", features.integrated_lufs, "<=", c.get("lufs_max", settings.techno_lufs_max))
        _check(
            "energy", features.energy_mean, ">=", c.get("energy_min", settings.techno_energy_min)
        )
        _check(
            "onset_rate",
            features.onset_rate,
            ">=",
            c.get("onset_rate_min", settings.techno_onset_rate_min),
        )
        _check(
            "kick",
            features.kick_prominence,
            ">=",
            c.get("kick_min", settings.techno_kick_prominence_min),
        )
        _check(
            "centroid",
            features.spectral_centroid_hz,
            ">=",
            c.get("centroid_min", settings.techno_centroid_min),
        )
        _check(
            "centroid",
            features.spectral_centroid_hz,
            "<=",
            c.get("centroid_max", settings.techno_centroid_max),
        )
        _check(
            "flatness",
            features.spectral_flatness,
            "<=",
            c.get("flatness_max", settings.techno_flatness_max),
        )
        _check(
            "hp_ratio",
            features.hp_ratio,
            "<=",
            c.get("hp_ratio_max", settings.techno_hp_ratio_max),
        )
        _check(
            "crest",
            features.crest_factor_db,
            "<=",
            c.get("crest_max", settings.techno_crest_factor_max),
        )
        _check("lra", features.loudness_range_lu, "<=", c.get("lra_max", settings.techno_lra_max))
        _check("hnr", features.hnr_db, ">=", c.get("hnr_min", settings.techno_hnr_min))
        _check(
            "tempo_conf",
            features.bpm_confidence,
            ">=",
            c.get("tempo_conf_min", settings.techno_tempo_confidence_min),
        )
        _check(
            "bpm_stab",
            features.bpm_stability,
            ">=",
            c.get("bpm_stab_min", settings.techno_bpm_stability_min),
        )
        _check(
            "pulse",
            features.pulse_clarity,
            ">=",
            c.get("pulse_min", settings.techno_pulse_clarity_min),
        )

        return {
            "track_id": track_id,
            "passed": len(reasons) == 0,
            "reasons": reasons,
        }

    async def _classify_existing(
        self, features: TrackAudioFeaturesComputed
    ) -> dict[str, Any] | None:
        """Run MoodClassifier on existing features and persist mood."""
        # DRY: use model method instead of manual field mapping
        feat_dict = features.to_classifier_dict()

        classifier = MoodClassifier()
        result = classifier.classify(feat_dict)

        # Persist
        await self._repo.update_mood(features, result.mood.value, result.confidence)

        return {
            "mood": result.mood.value,
            "confidence": round(result.confidence, 3),
            "reasoning": result.reasoning,
        }

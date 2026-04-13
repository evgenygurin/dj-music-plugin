"""Workflow for rendering a DJ mix from a set.

Orchestrates: load set → resolve audio files → stem separation → scoring → mix render.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.services.mix_service import mix_set
from app.services.stem_service import StemService
from app.services.workflows._helpers import call_async_method
from app.transition.scorer import TransitionScorer

logger = logging.getLogger(__name__)


class MixSetWorkflow:
    """Render a DJ set into a single mixed MP3 with stem-based transitions."""

    def __init__(
        self,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
        stem_service: StemService | None = None,
    ) -> None:
        self._sets = set_repo
        self._features = feature_repo
        self._stem_service = stem_service or StemService()

    async def render(
        self,
        *,
        set_id: int,
        version: str | None = None,
        output_dir: str | None = None,
        bpm: float | None = None,
        overlap_bars: int = 16,
        stem_backend: str | None = None,
        log: Any = None,
    ) -> dict[str, Any]:
        """Full render pipeline: load → separate → score → mix → MP3.

        Args:
            set_id: DJ set ID.
            version: Version label (latest if None).
            output_dir: Output directory (default: generated-sets/).
            bpm: Override BPM (auto-detect from features if None).
            overlap_bars: Transition overlap in bars.
            stem_backend: Force backend (mlx/cuda/onnx/torch_cpu/eq).
            log: ToolContext for progress reporting.
        """
        await call_async_method(log, "info", f"Loading set {set_id}...")

        # Stage 1: Load set tracks
        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            return {"error": f"Set {set_id} not found"}

        versions = await self._sets.get_versions(set_id)
        if version:
            target = next((v for v in versions if v.label == version), None)
        else:
            target = versions[-1] if versions else None
        if not target:
            return {"error": "No version found"}

        items = await self._sets.get_version_items(target.id)
        if len(items) < 2:
            return {"error": f"Need at least 2 tracks, got {len(items)}"}

        track_ids = [item.track_id for item in items]
        await call_async_method(log, "info", f"Stage 1/4: {len(items)} tracks loaded")

        # Stage 2: Resolve audio files
        audio_paths: list[Path] = []
        base = Path(output_dir or "generated-sets") / dj_set.name.replace(" ", "_").lower()
        base.mkdir(parents=True, exist_ok=True)

        # Check for already-downloaded MP3s in the output dir
        for item in items:
            patterns = list(base.glob(f"*{item.track_id}*")) or list(base.glob("*.mp3"))
            if patterns:
                audio_paths.append(patterns[0])

        if len(audio_paths) != len(items):
            return {
                "error": "Audio files not found. Run deliver_set with copy_files=True first.",
                "found": len(audio_paths),
                "needed": len(items),
                "hint": f"deliver_set(set_id={set_id}, copy_files=True)",
            }

        await call_async_method(log, "info", f"Stage 2/4: {len(audio_paths)} audio files resolved")

        # Stage 3: Stem separation
        stem_svc = StemService(backend=stem_backend) if stem_backend else self._stem_service

        await call_async_method(
            log,
            "info",
            f"Stage 3/4: Separating stems ({stem_svc.backend.value} backend)...",
        )

        async def _stem_progress(step: int, total: int, name: str) -> None:
            await call_async_method(log, "info", f"  [{step}/{total}] {name}")

        stems = await stem_svc.separate_batch(audio_paths, progress_callback=_stem_progress)

        # Stage 4: Score transitions + render
        await call_async_method(log, "info", "Stage 4/4: Scoring transitions and rendering mix...")

        # Load features for scoring
        scorer = TransitionScorer()
        features_map = await self._features.get_scoring_features_batch(track_ids)
        scores = []
        for i in range(len(track_ids) - 1):
            from app.entities.audio.features import TrackFeatures

            a_feat = features_map.get(track_ids[i], TrackFeatures())
            b_feat = features_map.get(track_ids[i + 1], TrackFeatures())
            score = scorer.score(a_feat, b_feat)
            scores.append(score)

        # Auto-detect BPM from features if not provided
        if bpm is None:
            bpms = [
                features_map[tid].bpm
                for tid in track_ids
                if tid in features_map and features_map[tid].bpm
            ]
            bpm = sum(bpms) / len(bpms) if bpms else 128.0

        output_path = base / "mix.mp3"
        mix_result = await mix_set(
            stems=stems,
            scores=scores,
            bpm=bpm,
            overlap_bars=overlap_bars,
            output_path=output_path,
        )

        await call_async_method(log, "info", f"Mix rendered: {mix_result.output_path}")

        return {
            "set_id": set_id,
            "set_name": dj_set.name,
            "output_path": str(mix_result.output_path),
            "duration_min": round(mix_result.duration_s / 60, 1),
            "size_mb": round(mix_result.size_bytes / 1_048_576, 1),
            "track_count": mix_result.track_count,
            "stem_backend": stem_svc.backend.value,
            "bpm": bpm,
            "overlap_bars": overlap_bars,
            "transitions": mix_result.transitions,
        }

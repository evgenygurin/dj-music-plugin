"""BPM detector — librosa-based tempo analysis.

Computes: bpm, bpm_confidence, bpm_stability, variable_tempo.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class BPMDetector(BaseAnalyzer):
    """Tempo detection using librosa beat tracking."""

    name: ClassVar[str] = "bpm"
    capabilities: ClassVar[frozenset[str]] = frozenset({"tempo", "rhythm"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # beat_track + onset_strength scale linearly with audio length.
    # Techno BPM is stable across the whole track — 60s is sufficient.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Detect BPM, confidence, and stability."""
        import librosa

        samples = ctx.samples
        sr = ctx.sr

        # Primary tempo detection
        tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sr, units="frames")
        bpm = float(np.atleast_1d(tempo)[0])

        # Beat times for stability analysis
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Confidence from onset strength (shared with beat/tempogram via ctx)
        onset_env = ctx.get_onset_env()
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
        confidence = float(np.max(pulse)) if len(pulse) > 0 else 0.5

        # Stability: how consistent are inter-beat intervals
        stability = 0.0
        variable_tempo = False
        if len(beat_times) > 2:
            ibis = np.diff(beat_times)
            if len(ibis) > 1 and np.mean(ibis) > 0:
                cv = float(np.std(ibis) / np.mean(ibis))
                stability = max(0.0, min(1.0, 1.0 - cv * 2))
                variable_tempo = cv > 0.15

        return {
            "bpm": round(bpm, 2),
            "bpm_confidence": round(min(1.0, confidence), 4),
            "bpm_stability": round(stability, 4),
            "variable_tempo": variable_tempo,
        }

"""BPM detector — librosa-based tempo analysis.

Computes: bpm, bpm_confidence, bpm_stability, variable_tempo.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer


class BPMDetector(BaseAnalyzer):
    """Tempo detection using librosa beat tracking."""

    name = "bpm"
    capabilities = {"tempo", "rhythm"}
    required_packages = ["librosa"]

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Detect BPM, confidence, and stability."""
        import librosa

        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")

        # Primary tempo detection
        tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sr, units="frames")
        bpm = float(np.atleast_1d(tempo)[0])

        # Beat times for stability analysis
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Confidence from onset strength
        onset_env = librosa.onset.onset_strength(y=samples, sr=sr)
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

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "bpm": round(bpm, 2),
                "bpm_confidence": round(min(1.0, confidence), 4),
                "bpm_stability": round(stability, 4),
                "variable_tempo": variable_tempo,
            },
        )

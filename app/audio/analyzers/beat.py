"""Beat detector — librosa-based rhythm analysis.

Computes: onset_rate, pulse_clarity, kick_prominence, hp_ratio.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class BeatDetector(BaseAnalyzer):
    """Rhythm analysis: onset detection, pulse clarity, kick prominence."""

    name: ClassVar[str] = "beat"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "beat"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # librosa.effects.hpss is O(N) and dominates runtime on long tracks
    # (~13s on 6.6 min, ~2s on 60s). Centered 60s clip is representative
    # for techno: stable rhythm, no intro/outro contamination.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Analyze rhythmic features from full audio signal."""
        import librosa

        samples = ctx.samples
        sr = ctx.sr
        analysis_duration = len(samples) / sr

        # Onset detection (envelope shared with bpm/tempogram via ctx)
        onset_env = ctx.get_onset_env()
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")
        onset_rate = float(len(onsets) / analysis_duration) if analysis_duration > 0 else 0.0

        # Pulse clarity (tempogram autocorrelation peak)
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        pulse_clarity = 0.0
        if tempogram.size > 0:
            # Mean autocorrelation at dominant tempo lag
            acf = np.mean(tempogram, axis=1)
            if len(acf) > 1:
                pulse_clarity = float(np.max(acf[1:]) / (acf[0] + 1e-10))
                pulse_clarity = max(0.0, min(1.0, pulse_clarity))

        # Harmonic-percussive separation for kick prominence and HP ratio
        harmonic, percussive = librosa.effects.hpss(samples)

        h_rms = float(np.sqrt(np.mean(harmonic**2)))
        p_rms = float(np.sqrt(np.mean(percussive**2)))
        hp_ratio = h_rms / (p_rms + 1e-10)

        # Kick prominence: energy in low frequencies of percussive component
        # Low-pass the percussive signal at ~200Hz
        s_perc = np.abs(librosa.stft(percussive))
        freqs = librosa.fft_frequencies(sr=sr)
        low_mask = freqs < 200
        total_perc_energy = float(np.sum(s_perc**2))
        low_perc_energy = float(np.sum(s_perc[low_mask, :] ** 2))
        kick_prominence = low_perc_energy / (total_perc_energy + 1e-10)

        beats_intervals = np.diff(onsets).tolist() if len(onsets) > 1 else []

        return {
            "onset_rate": round(onset_rate, 4),
            "pulse_clarity": round(pulse_clarity, 4),
            "kick_prominence": round(kick_prominence, 4),
            "hp_ratio": round(hp_ratio, 4),
            "beat_times": onsets.tolist(),
            "beats_intervals": beats_intervals,
        }

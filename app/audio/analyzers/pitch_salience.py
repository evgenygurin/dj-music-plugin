"""PitchSalienceAnalyzer — tonality measure 0-1 via essentia autocorrelation."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class PitchSalienceAnalyzer(BaseAnalyzer):
    """Mean pitch salience (0-1) via essentia. Proxy for vocal/melodic content.

    Uses harmonic peak energy ratio: ratio of harmonic peak energy to total
    spectral energy, computed per frame via PitchYin + HarmonicPeaks.
    Frames without a confident pitch estimate contribute 0.0 to the mean.
    """

    name: ClassVar[str] = "pitch_salience"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral", "harmony"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        frame_size = 2048
        hop_size = 1024
        sr = float(ctx.sr)

        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(sampleRate=sr)
        harmonic_peaks = es.HarmonicPeaks()
        pitch_yin = es.PitchYin(frameSize=frame_size, sampleRate=sr)

        values: list[float] = []

        for start in range(0, len(ctx.samples) - frame_size, hop_size):
            frame = ctx.samples[start : start + frame_size]
            pitch, conf = pitch_yin(frame)

            if pitch <= 0.0 or conf < 0.1:
                values.append(0.0)
                continue

            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)

            # HarmonicPeaks requires all frequencies > 0 Hz
            mask = freqs > 0.0
            freqs = freqs[mask]
            mags = mags[mask]

            if len(freqs) == 0:
                values.append(0.0)
                continue

            try:
                hfreqs, hmags = harmonic_peaks(freqs, mags, pitch)
            except RuntimeError:
                values.append(0.0)
                continue

            if len(hfreqs) == 0:
                values.append(0.0)
                continue

            harmonic_energy = float(np.sum(np.asarray(hmags) ** 2))
            total_energy = float(np.sum(np.asarray(mags) ** 2)) + 1e-10
            values.append(min(1.0, harmonic_energy / total_energy))

        mean_val = float(np.mean(values)) if values else 0.0
        return {"pitch_salience_mean": round(mean_val, 4)}

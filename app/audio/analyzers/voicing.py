"""VoicingAnalyzer — real vocal detection via essentia PitchYin + HarmonicPeaks."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class VoicingAnalyzer(BaseAnalyzer):
    """Voicing probability via essentia PitchYin + HarmonicPeaks.

    Real voice/vocal detection — not a spectral proxy. Computes per-frame
    harmonic energy ratio from pitch-aligned harmonic peaks, then aggregates.
    Frames without a confident pitch contribute voicing=0.0.
    """

    name: ClassVar[str] = "voicing"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral", "harmony"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        frame_size = 2048
        hop_size = 1024
        sr = float(ctx.sr)
        samples = ctx.samples

        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(sampleRate=sr)
        harmonic_peaks = es.HarmonicPeaks()
        pitch_yin = es.PitchYin(frameSize=frame_size, sampleRate=sr)

        voicing_values: list[float] = []

        for start in range(0, len(samples) - frame_size, hop_size):
            frame = samples[start : start + frame_size]
            pitch, conf = pitch_yin(frame)

            if pitch <= 0.0 or conf < 0.1:
                voicing_values.append(0.0)
                continue

            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)

            mask = freqs > 0.0
            freqs = freqs[mask]
            mags = mags[mask]

            if len(freqs) == 0:
                voicing_values.append(0.0)
                continue

            try:
                hfreqs, hmags = harmonic_peaks(freqs, mags, pitch)
            except RuntimeError:
                voicing_values.append(0.0)
                continue

            if len(hfreqs) == 0:
                voicing_values.append(0.0)
                continue

            harmonic_energy = float(np.sum(np.asarray(hmags) ** 2))
            total_energy = float(np.sum(np.asarray(mags) ** 2)) + 1e-10
            voicing_values.append(min(1.0, harmonic_energy / total_energy))

        if not voicing_values:
            return {"voicing_ratio": 0.0}

        arr = np.array(voicing_values)
        voicing_ratio = float(np.mean(arr > 0.3))

        return {"voicing_ratio": round(voicing_ratio, 4)}

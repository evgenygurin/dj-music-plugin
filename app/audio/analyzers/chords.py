from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class ChordsAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "chords"
    level: ClassVar[int] = 6
    required_packages: ClassVar[list[str]] = ["essentia"]

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"chords_strength": None, "chords_changes_rate": None}

        frame_size = 2048
        hop_size = 512
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(
            maxPeaks=100, magnitudeThreshold=1e-4, minFrequency=80, maxFrequency=4000
        )
        hpcp = es.HPCP(sampleRate=sample_rate)
        chords_detector = es.ChordsDetection()

        hop_generator = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
        hpcp_frames = []
        for frame in hop_generator:
            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)
            hpcp_vals = hpcp(freqs, mags)
            hpcp_frames.append(hpcp_vals)

        if len(hpcp_frames) < 2:
            return {"chords_strength": None, "chords_changes_rate": None}

        hpcp_stack = np.array(hpcp_frames)
        chords_result = chords_detector(hpcp_stack)
        chords_strength = float(np.mean(chords_result[1])) if chords_result[1].size > 0 else None
        chord_labels = chords_result[0]
        changes = sum(
            1 for i in range(1, len(chord_labels)) if chord_labels[i] != chord_labels[i - 1]
        )
        chords_changes = changes
        total_frames = len(chord_labels)
        chords_changes_rate = float(chords_changes / total_frames) if total_frames > 0 else None

        return {"chords_strength": chords_strength, "chords_changes_rate": chords_changes_rate}

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return self.analyze(ctx.samples.astype(np.float32, copy=False), ctx.sr)

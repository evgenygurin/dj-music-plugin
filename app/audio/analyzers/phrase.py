"""PhraseAnalyzer — phrase boundary detection via chroma clustering (librosa)."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class PhraseAnalyzer(BaseAnalyzer):
    """Detect phrase boundaries using agglomerative clustering on bar-level chroma."""

    name: ClassVar[str] = "phrase"
    capabilities: ClassVar[frozenset[str]] = frozenset({"structure"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import librosa

        beat_times = (prior_results or {}).get("beat_times", [])
        if len(beat_times) < 16:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        # Group beats into bars (4 beats per bar for 4/4 time)
        bar_times = [beat_times[i] for i in range(0, len(beat_times), 4)]
        n_bars = len(bar_times)
        if n_bars < 8:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        # Compute chroma
        chroma = librosa.feature.chroma_cqt(y=ctx.samples, sr=ctx.sr)

        # Guard against empty chroma (very short or silent signals)
        if chroma.shape[1] == 0:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        bar_frames = librosa.time_to_frames(bar_times, sr=ctx.sr)

        # Mean chroma per bar
        chroma_bars_list = []
        for i in range(len(bar_frames) - 1):
            start_f = max(0, bar_frames[i])
            end_f = bar_frames[i + 1]
            if end_f > start_f and end_f <= chroma.shape[1]:
                chroma_bars_list.append(chroma[:, start_f:end_f].mean(axis=1))
            else:
                chroma_bars_list.append(np.zeros(12))

        if len(chroma_bars_list) < 4:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        chroma_bars = np.array(chroma_bars_list).T  # shape: (12, n_bars-1)

        # Determine number of segments: k must be >= 2 and <= n_samples
        n_samples = chroma_bars.shape[1]
        k = max(2, min(n_samples, max(4, min(n_samples // 4, 64))))

        boundaries = librosa.segment.agglomerative(chroma_bars, k=k)

        # Convert bar indices to ms
        phrase_boundaries_ms = [
            int(bar_times[min(b, len(bar_times) - 1)] * 1000) for b in boundaries
        ]

        # Dominant phrase length (mode of segment lengths, quantized to 8/16/32)
        segment_lengths = np.diff(boundaries)
        if len(segment_lengths) > 0:
            quantized = [
                min([8, 16, 32], key=lambda x, sl=sl: abs(x - sl)) for sl in segment_lengths
            ]
            dominant = max(set(quantized), key=quantized.count)
        else:
            dominant = 16

        return {
            "phrase_boundaries_ms": phrase_boundaries_ms,
            "dominant_phrase_bars": int(dominant),
        }

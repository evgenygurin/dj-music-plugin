"""PhraseAnalyzer — phrase boundary detection via chroma clustering (librosa)."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext
from app.v2.audio.core.tonal import compute_pitch_class_chroma


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
        import librosa  # noqa: F401

        beat_times = (prior_results or {}).get("beat_times", [])
        if len(beat_times) < 16:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        # Group beats into bars (4 beats per bar for 4/4 time)
        bar_times = [beat_times[i] for i in range(0, len(beat_times), 4)]
        n_bars = len(bar_times)
        if n_bars < 8:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        chroma = compute_pitch_class_chroma(ctx.magnitude, ctx.freqs)

        # Guard against empty chroma (very short or silent signals)
        if chroma.shape[1] == 0:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        hop_seconds = ctx.params.hop_length / ctx.sr
        if hop_seconds <= 0:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}
        bar_frames = [round(t / hop_seconds) for t in bar_times]

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

        chroma_bars = np.array(chroma_bars_list)
        bar_changes = (
            np.linalg.norm(np.diff(chroma_bars, axis=0), axis=1)
            if len(chroma_bars) > 1
            else np.array([], dtype=np.float64)
        )

        candidates = [size for size in (8, 16, 32) if size < len(bar_times)]
        dominant = (
            max(candidates, key=lambda size: _phrase_length_score(bar_changes, size))
            if candidates
            else 16
        )

        boundaries = list(range(0, len(bar_times), dominant))
        if boundaries[-1] != len(bar_times) - 1:
            boundaries.append(len(bar_times) - 1)
        phrase_boundaries_ms = [int(bar_times[idx] * 1000) for idx in boundaries]

        return {
            "phrase_boundaries_ms": phrase_boundaries_ms,
            "dominant_phrase_bars": int(dominant),
        }


def _phrase_length_score(bar_changes: np.ndarray, phrase_bars: int) -> float:
    if len(bar_changes) == 0:
        return 0.0

    boundary_positions = [idx - 1 for idx in range(phrase_bars, len(bar_changes) + 1, phrase_bars)]
    if not boundary_positions:
        return 0.0
    return float(np.mean(bar_changes[boundary_positions]))

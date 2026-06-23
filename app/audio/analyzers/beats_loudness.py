"""Beats loudness band ratio analyzer — essentia per-band loudness at beats.

Computes: beat_loudness_band_ratio — 6-band loudness ratios at beat positions.
Depends on BeatDetector for beat_times.

This is a rhythmic timbre fingerprint: how loudness is distributed across
frequency bands at beat positions. Useful for distinguishing kick-heavy
tracks from hi-hat-heavy ones.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

# 7 boundaries → 6 frequency bands
# [20-150, 150-400, 400-3200, 3200-7000, 7000-10000, 10000-22000] Hz
_FREQUENCY_BANDS: list[float] = [20, 150, 400, 3200, 7000, 10000, 22000]


@register_analyzer
class BeatsLoudnessAnalyzer(BaseAnalyzer):
    """Per-band loudness at beat positions via essentia BeatsLoudness."""

    name: ClassVar[str] = "beats_loudness"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "spectral"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})
    # MUST match the ``beat`` analyzer's clip: beat_times are timestamps within
    # the 60s stitched clip, so BeatsLoudness has to run on those same samples.
    # Without this it inherited the full-track context (clip_duration_s=None) and
    # essentia got beat positions that don't correspond to its samples → the
    # feature came back NULL for the whole library. See
    # docs/research/2026-06-23-track-feature-reference-and-set-construction.md.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        beat_times = (prior_results or {}).get("beat_times")
        if not beat_times:
            return {}

        import essentia.standard as es

        bl = es.BeatsLoudness(
            beats=beat_times,
            sampleRate=float(ctx.sr),
            frequencyBands=_FREQUENCY_BANDS,
        )
        _loudness, loudness_band_ratio = bl(ctx.samples)

        # Mean across beats → 6 band ratios
        mean_ratio = [round(float(x), 4) for x in loudness_band_ratio.mean(axis=0)]
        return {"beat_loudness_band_ratio": mean_ratio}

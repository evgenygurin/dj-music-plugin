"""Post-render audio safety metrics validation."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioMetrics:
    duration_s: float
    channels: int
    sample_rate: int
    peak_db: float
    loudness_lufs: float
    finite: bool = True


@dataclass(frozen=True, slots=True)
class RenderedValidation:
    accepted: bool
    reasons: tuple[str, ...] = ()


class RenderedAudioValidator:
    def __init__(self, peak_ceiling_db: float = 0.0) -> None:
        self.peak_ceiling_db = peak_ceiling_db

    def validate(self, metrics: AudioMetrics) -> RenderedValidation:
        reasons: list[str] = []
        if not metrics.finite or not all(
            math.isfinite(v) for v in (metrics.duration_s, metrics.peak_db, metrics.loudness_lufs)
        ):
            reasons.append("finite")
        if metrics.duration_s <= 0:
            reasons.append("duration")
        if metrics.channels <= 0 or metrics.sample_rate <= 0:
            reasons.append("format")
        if metrics.peak_db > self.peak_ceiling_db:
            reasons.append("clipping")
        return RenderedValidation(not reasons, tuple(reasons))

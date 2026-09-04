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
    true_peak_db: float | None = None
    silence_ratio: float = 0.0
    beat_alignment_error_s: float | None = None
    drift_beats: float | None = None


@dataclass(frozen=True, slots=True)
class RenderedValidation:
    accepted: bool
    reasons: tuple[str, ...] = ()


class RenderedAudioValidator:
    def __init__(
        self,
        peak_ceiling_db: float = 0.0,
        max_silence_ratio: float = 0.95,
        max_alignment_error_s: float | None = 0.05,
        max_drift_beats: float | None = 0.5,
    ) -> None:
        self.peak_ceiling_db = peak_ceiling_db
        self.max_silence_ratio = max_silence_ratio
        self.max_alignment_error_s = max_alignment_error_s
        self.max_drift_beats = max_drift_beats

    def validate(self, metrics: AudioMetrics) -> RenderedValidation:
        reasons: list[str] = []
        values: tuple[float, ...] = (
            metrics.duration_s,
            metrics.peak_db,
            metrics.loudness_lufs,
        )
        if metrics.true_peak_db is not None:
            values += (metrics.true_peak_db,)
        if not metrics.finite or not all(math.isfinite(v) for v in values):
            reasons.append("finite")
        if metrics.duration_s <= 0:
            reasons.append("duration")
        if metrics.channels <= 0 or metrics.sample_rate <= 0:
            reasons.append("format")
        if metrics.peak_db > self.peak_ceiling_db or (
            metrics.true_peak_db is not None and metrics.true_peak_db > self.peak_ceiling_db
        ):
            reasons.append("clipping")
        if not 0.0 <= metrics.silence_ratio <= self.max_silence_ratio:
            reasons.append("silence")
        if self.max_alignment_error_s is not None and (
            metrics.beat_alignment_error_s is not None
            and metrics.beat_alignment_error_s > self.max_alignment_error_s
        ):
            reasons.append("beat_alignment")
        if self.max_drift_beats is not None and (
            metrics.drift_beats is not None and metrics.drift_beats > self.max_drift_beats
        ):
            reasons.append("drift")
        return RenderedValidation(not reasons, tuple(reasons))

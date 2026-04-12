"""Tests for template-aware intent wiring in optimization fitness."""

from __future__ import annotations

from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import transition_quality
from app.templates import get_template
from app.transition.intent import TransitionIntent
from app.transition.score import TransitionScore


class _CaptureScorer:
    """Minimal scorer stub that records intent values."""

    def __init__(self) -> None:
        self.intents: list[TransitionIntent | None] = []

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
    ) -> TransitionScore:
        self.intents.append(intent)
        return TransitionScore(
            bpm=0.8,
            harmonic=0.8,
            energy=0.8,
            spectral=0.8,
            groove=0.8,
            timbral=0.8,
            overall=0.8,
        )


def _make_tracks(n: int) -> tuple[list[TrackFeatures], list[int], dict[int, int]]:
    tracks = [
        TrackFeatures(
            bpm=128.0 + i * 0.2,
            key_code=14,
            integrated_lufs=-8.0,  # keep energy_delta ≈ 0 so phase dominates
            spectral_centroid_hz=2500.0,
            energy_mean=0.5,
            onset_rate=4.0,
            kick_prominence=0.5,
        )
        for i in range(n)
    ]
    order = list(range(1, n + 1))
    idx_map = {tid: tid - 1 for tid in order}
    return tracks, order, idx_map


def test_transition_quality_uses_template_phase_boundaries() -> None:
    """Position ~0.166 is warmup for default but not for peak_hour_60."""
    tracks, order, idx_map = _make_tracks(8)

    default_scorer = _CaptureScorer()
    transition_quality(default_scorer, tracks, order, idx_map, template=None)

    template_scorer = _CaptureScorer()
    peak_hour = get_template("peak_hour_60")
    transition_quality(template_scorer, tracks, order, idx_map, template=peak_hour)

    # i=1 -> position = 1/(n-2) = 1/6 ~= 0.166
    # default warmup_end=0.20 => RAMP_UP
    assert default_scorer.intents[1] == TransitionIntent.RAMP_UP
    # peak_hour warmup_end=0.10 => MAINTAIN
    assert template_scorer.intents[1] == TransitionIntent.MAINTAIN

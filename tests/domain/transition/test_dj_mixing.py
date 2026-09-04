"""Cell 16 — pure domain DJ mixing contract tests.

Pins the new bounded-context surface for ``app.domain.transition.dj_mixing``:

* TempoModel wraps hypotheses and applies octave correction deterministically.
* TransitionGrid projects TrackFeatures summary columns to a domain grid.
* Bar-constrained transition duration snaps to the allowed set.
* Score components (S_tempo, S_beat_alignment, S_phrase_alignment,
  S_drift) behave as documented.
* TransitionScore gains an ``align`` field without breaking the legacy
  six-component shape.
* TransitionCue candidate generation honours phrase boundaries and
  bar grid anchors.

Tests are pure dataclass + arithmetic, no audio fixtures, no Demucs,
no async. Determinism is mandatory.
"""

from __future__ import annotations

import math

import pytest

from app.domain.transition.dj_mixing import (
    ALIGNMENT_DEFAULT_WEIGHTS,
    MIXING_DEFAULT_TARGET_BARS,
    MIXING_DEFAULT_TRANSITION_BARS,
    MIXING_MAX_TRANSITION_BARS,
    MIXING_MIN_TRANSITION_BARS,
    NEUTRAL_ALIGNMENT,
    S_TEMPO_SIGMA,
    AlignmentScore,
    TempoModel,
    TransitionCue,
    TransitionGrid,
    compute_alignment,
    generate_transition_cues,
    score_beat_alignment,
    score_drift,
    score_phrase_alignment,
    score_tempo,
    select_transition_bars,
)
from app.domain.transition.score import TransitionScore
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures

# ── Helpers ─────────────────────────────────────────────────────────


def _tf(
    *,
    bpm: float | None = 128.0,
    bpm_confidence: float | None = 0.9,
    bpm_stability: float | None = 0.95,
    first_downbeat_ms: float | None = 0.0,
    phrase_boundaries_ms: list[int] | None = None,
    dominant_phrase_bars: int | None = None,
    integrated_lufs: float | None = -10.0,
    key_code: int | None = 8,
) -> TrackFeatures:
    """Build a TrackFeatures with the minimum fields the alignment path reads."""
    return TrackFeatures(
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        bpm_stability=bpm_stability,
        integrated_lufs=integrated_lufs,
        key_code=key_code,
        first_downbeat_ms=first_downbeat_ms,
        phrase_boundaries_ms=phrase_boundaries_ms,
        dominant_phrase_bars=dominant_phrase_bars,
    )


# ── TempoModel ──────────────────────────────────────────────────────


def test_tempo_model_from_features_uses_canonical_bpm() -> None:
    m = TempoModel.from_features(_tf(bpm=128.0, bpm_confidence=0.9))
    assert m.is_locked
    assert m.effective_bpm() == pytest.approx(128.0)
    assert m.confidence() == pytest.approx(0.9)


def test_tempo_model_applies_octave_correction() -> None:
    m = TempoModel.from_features(_tf(bpm=128.0), octave_correction=0.5)
    assert m.effective_bpm() == pytest.approx(64.0)
    m2 = TempoModel.from_features(_tf(bpm=128.0), octave_correction=2.0)
    assert m2.effective_bpm() == pytest.approx(256.0)


def test_tempo_model_unlocked_when_no_bpm() -> None:
    m = TempoModel.from_features(_tf(bpm=None))
    assert not m.is_locked
    assert m.effective_bpm() == 0.0


def test_tempo_model_unlocks_below_confidence_floor() -> None:
    m = TempoModel.from_features(_tf(bpm=128.0, bpm_confidence=0.1))
    assert not m.is_locked
    # Effective BPM is still derivable; the lock flag is about trust.
    assert m.effective_bpm() == pytest.approx(128.0)


# ── TransitionGrid ──────────────────────────────────────────────────


def test_transition_grid_is_valid_for_stable_track() -> None:
    grid = TransitionGrid.from_features(_tf(bpm=128.0))
    assert grid.is_valid
    assert grid.bar_period_s == pytest.approx(60.0 / 128.0 * 4)
    assert grid.beats_per_bar == 4
    assert grid.first_downbeat_s == pytest.approx(0.0)


def test_transition_grid_first_downbeat_modulo() -> None:
    grid = TransitionGrid.from_features(_tf(bpm=120.0, first_downbeat_ms=750.0))
    # 120 BPM → 0.5 s per beat. 750 ms > beat period, so the phase wraps.
    assert 0.0 <= grid.first_downbeat_s < (60.0 / 120.0)
    assert grid.first_downbeat_s == pytest.approx(0.25, abs=1e-9)


def test_transition_grid_invalid_for_missing_bpm() -> None:
    grid = TransitionGrid.from_features(_tf(bpm=None))
    assert not grid.is_valid
    assert grid.bar_period_s == 0.0


def test_transition_grid_bar_at_seconds() -> None:
    grid = TransitionGrid.from_features(_tf(bpm=120.0))
    period = 60.0 / 120.0 * 4
    assert grid.bar_at_seconds(0.0) == 0
    assert grid.bar_at_seconds(period * 7 + 0.1) == 7


def test_transition_grid_seconds_to_nearest_bar() -> None:
    grid = TransitionGrid.from_features(_tf(bpm=120.0))
    period = 60.0 / 120.0 * 4
    assert grid.seconds_to_nearest_bar(0.0) == pytest.approx(0.0)
    assert grid.seconds_to_nearest_bar(period / 2) == pytest.approx(period / 2)
    assert grid.seconds_to_nearest_bar(period) == pytest.approx(0.0)


def test_transition_grid_seconds_to_nearest_phrase_uses_phrase_list() -> None:
    grid = TransitionGrid.from_features(
        _tf(bpm=120.0, phrase_boundaries_ms=[0, 16_000, 32_000, 48_000])
    )
    # Phrase boundary at 16s; we test 16.5 → distance 0.5.
    assert grid.seconds_to_nearest_phrase(16.5) == pytest.approx(0.5)
    # 8.0 is exactly between 0 and 16: nearest phrase = 0 (distance 8).
    assert grid.seconds_to_nearest_phrase(8.0) == pytest.approx(8.0)


# ── select_transition_bars ──────────────────────────────────────────


def test_select_transition_bars_snap_to_nearest() -> None:
    # 16 is the techno phrase default — snapped exactly to itself.
    assert select_transition_bars(target_bars=16) == 16
    # 14 is closer to 16 than 8 (|16-14|=2 vs |8-14|=6) → 16 wins.
    assert select_transition_bars(target_bars=14) == 16
    # 10 is closer to 8 (|8-10|=2 vs |16-10|=6) → 8 wins.
    assert select_transition_bars(target_bars=10) == 8
    assert select_transition_bars(target_bars=15) == 16
    assert select_transition_bars(target_bars=20) == 16
    assert select_transition_bars(target_bars=33) == 32
    # 12 is equidistant from 8 and 16; tie-break to the shorter option.
    assert select_transition_bars(target_bars=12) == 8


def test_select_transition_bars_clamps_bounds() -> None:
    assert select_transition_bars(target_bars=2) == MIXING_MIN_TRANSITION_BARS
    assert select_transition_bars(target_bars=128) == MIXING_MAX_TRANSITION_BARS


def test_select_transition_bars_custom_allowed() -> None:
    assert select_transition_bars(target_bars=10, allowed=(4, 12, 24)) == 12
    assert select_transition_bars(target_bars=14, allowed=(4, 12, 24)) == 12


def test_select_transition_bars_handles_empty_allowed() -> None:
    # With no allowed set, the function returns the bounded target.
    assert select_transition_bars(target_bars=20, allowed=()) == 20


def test_select_transition_bars_uses_default_target() -> None:
    # Default target = 16 → pick 16.
    assert select_transition_bars() == MIXING_DEFAULT_TARGET_BARS


# ── score_tempo (S_tempo) ───────────────────────────────────────────


def test_score_tempo_perfect_match_is_one() -> None:
    assert score_tempo(_tf(bpm=128.0), _tf(bpm=128.0)) == pytest.approx(1.0)


def test_score_tempo_double_time_is_one() -> None:
    assert score_tempo(_tf(bpm=128.0), _tf(bpm=256.0)) == pytest.approx(1.0, abs=1e-3)


def test_score_tempo_half_time_is_one() -> None:
    assert score_tempo(_tf(bpm=128.0), _tf(bpm=64.0)) == pytest.approx(1.0, abs=1e-3)


def test_score_tempo_unknown_returns_neutral() -> None:
    assert score_tempo(_tf(bpm=None), _tf(bpm=128.0)) == NEUTRAL_ALIGNMENT
    assert score_tempo(_tf(bpm=128.0), _tf(bpm=None)) == NEUTRAL_ALIGNMENT


def test_score_tempo_matches_legacy_gauss() -> None:
    # 5 BPM delta is the well-known techno sync tolerance; sigma=10
    # gives ~0.88, matching docs § S_tempo table.
    score = score_tempo(_tf(bpm=128.0), _tf(bpm=133.0))
    expected = math.exp(-(5.0**2) / (2 * S_TEMPO_SIGMA**2))
    assert score == pytest.approx(expected, abs=1e-6)
    assert score == pytest.approx(0.88, abs=0.01)


# ── score_beat_alignment (S_beat_alignment) ─────────────────────────


def test_score_beat_alignment_perfect_phase_is_one() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=0.0))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=0.0))
    assert score_beat_alignment(g1, g2) == pytest.approx(1.0)


def test_score_beat_alignment_half_beat_offset_is_near_zero() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=0.0))
    # 128 BPM → 0.46875 s per beat. A 234 ms phase offset is
    # essentially a half-beat anti-alignment; the score curve
    # (sigma = 0.06 s) is intentionally tight so a half-beat
    # misalignment reads as a near-total failure.
    g2 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=234.0))
    score = score_beat_alignment(g1, g2)
    assert score < 0.1


def test_score_beat_alignment_quarter_beat_offset_is_partial() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=0.0))
    # 128 BPM → 0.46875 s per beat. A 117 ms offset = quarter-beat
    # misalignment; the score should be in (0, 1).
    g2 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=117.0))
    score = score_beat_alignment(g1, g2)
    assert 0.0 < score < 1.0


def test_score_beat_alignment_small_offset_high_score() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=0.0))
    # 20 ms offset is small enough to score well above 0.9.
    g2 = TransitionGrid.from_features(_tf(bpm=128.0, first_downbeat_ms=20.0))
    score = score_beat_alignment(g1, g2)
    assert score > 0.7


def test_score_beat_alignment_unknown_returns_neutral() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=None))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    assert score_beat_alignment(g1, g2) == NEUTRAL_ALIGNMENT
    g3 = TransitionGrid.from_features(_tf(bpm=128.0))
    g4 = TransitionGrid.from_features(_tf(bpm=None))
    assert score_beat_alignment(g3, g4) == NEUTRAL_ALIGNMENT


# ── score_phrase_alignment (S_phrase_alignment) ─────────────────────


def test_score_phrase_alignment_perfect_bar_lock_is_one() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    # planned_out_bar=0 with no phrase boundaries on g2 → falls back
    # to bar_period distance = 0 → score = 1.0.
    assert score_phrase_alignment(g1, g2) == pytest.approx(1.0)


def test_score_phrase_alignment_with_phrase_hits_landmark() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0))
    # 8-bar phrase = 8 * (60/128)*4 = 15.0 s at 128 BPM. We add a phrase
    # boundary at 15.0 s.
    g2 = TransitionGrid.from_features(
        _tf(bpm=128.0, phrase_boundaries_ms=[0, 15_000])
    )
    # planned_out_bar=0 → t=0.0 is exactly the g2 phrase boundary at 0.
    assert score_phrase_alignment(g1, g2, planned_out_bar=0) == pytest.approx(1.0)


def test_score_phrase_alignment_unknown_returns_neutral() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=None))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    assert score_phrase_alignment(g1, g2) == NEUTRAL_ALIGNMENT


# ── score_drift (S_drift) ───────────────────────────────────────────


def test_score_drift_perfect_match_is_one() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    assert score_drift(g1, g2, transition_bars=16) == pytest.approx(1.0)


def test_score_drift_drops_with_bpm_gap() -> None:
    g_stable = TransitionGrid.from_features(_tf(bpm=128.0))
    g_drift = TransitionGrid.from_features(_tf(bpm=128.5))
    s_stable = score_drift(g_stable, g_stable, transition_bars=16)
    s_drift = score_drift(g_stable, g_drift, transition_bars=16)
    assert s_drift < s_stable
    assert s_drift > 0.0


def test_score_drift_saturates_at_max() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0))
    g2 = TransitionGrid.from_features(_tf(bpm=140.0))  # 12 BPM gap
    score = score_drift(g1, g2, transition_bars=64)
    # 12 BPM / 128 BPM ≈ 9 % per-beat drift. Over 64 bars x 4 beats
    # x 0.469 s = 0.469 * 256 * 0.094 = 11.3 s of accumulated drift,
    # well past S_DRIFT_MAX_S → score should be 0.
    assert score == pytest.approx(0.0)


def test_score_drift_unknown_returns_neutral() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=None))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    assert score_drift(g1, g2, transition_bars=16) == NEUTRAL_ALIGNMENT


def test_score_drift_zero_bars_returns_neutral() -> None:
    g1 = TransitionGrid.from_features(_tf(bpm=128.0))
    g2 = TransitionGrid.from_features(_tf(bpm=128.0))
    assert score_drift(g1, g2, transition_bars=0) == NEUTRAL_ALIGNMENT


# ── compute_alignment (composite) ──────────────────────────────────


def test_compute_alignment_returns_all_four_components() -> None:
    a = _tf(bpm=128.0, first_downbeat_ms=0.0)
    b = _tf(bpm=128.0, first_downbeat_ms=0.0)
    align = compute_alignment(a, b, transition_bars=16)
    assert isinstance(align, AlignmentScore)
    assert 0.0 <= align.s_tempo <= 1.0
    assert 0.0 <= align.s_beat_alignment <= 1.0
    assert 0.0 <= align.s_phrase_alignment <= 1.0
    assert 0.0 <= align.s_drift <= 1.0
    # Perfect match → all four near 1.0.
    assert align.s_tempo == pytest.approx(1.0)
    assert align.s_beat_alignment == pytest.approx(1.0)
    assert align.s_drift == pytest.approx(1.0)


def test_compute_alignment_overall_uses_weights() -> None:
    weights = ALIGNMENT_DEFAULT_WEIGHTS
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)


def test_compute_alignment_overall_clamps_to_unit() -> None:
    a = _tf(bpm=120.0)
    b = _tf(bpm=130.0)
    align = compute_alignment(a, b)
    assert 0.0 <= align.overall <= 1.0


# ── generate_transition_cues ────────────────────────────────────────


def test_generate_transition_cues_invalid_grid_empty() -> None:
    cues = generate_transition_cues(
        track_id=1,
        features=_tf(bpm=None),
        role="mix_out",
    )
    assert cues == []


def test_generate_transition_cues_uses_phrase_boundaries() -> None:
    features = _tf(
        bpm=128.0,
        phrase_boundaries_ms=[0, 15_000, 30_000, 45_000, 60_000],
    )
    cues = generate_transition_cues(
        track_id=1, features=features, role="mix_out", n_candidates=4
    )
    # First phrase boundary (t=0) is skipped because it has bar_index=0;
    # the remaining four produce 3 phrase cues + 1 grid anchor.
    assert len(cues) == 4
    assert all(isinstance(c, TransitionCue) for c in cues)
    assert cues[0].role == "mix_out"
    # All cues are sorted by score descending.
    scores = [c.score for c in cues]
    assert scores == sorted(scores, reverse=True)
    # Length bars snap to a bar-constrained value.
    assert cues[0].length_bars in MIXING_DEFAULT_TRANSITION_BARS


def test_generate_transition_cues_uses_grid_anchor_when_no_phrase() -> None:
    features = _tf(bpm=120.0, phrase_boundaries_ms=None)
    cues = generate_transition_cues(
        track_id=2, features=features, role="mix_in", n_candidates=2
    )
    # Without phrase boundaries, every cue is a grid anchor.
    assert all(c.reason == "grid_anchor" for c in cues)
    assert all(c.role == "mix_in" for c in cues)
    assert len(cues) == 2
    # Grid anchors step by the transition length (16 bars default).
    bar_period = 60.0 / 120.0 * 4  # 2.0 s
    expected = [16 * bar_period, 32 * bar_period]
    actual = [c.position_s for c in cues]
    assert actual == pytest.approx(expected)


# ── TransitionScore.align field ────────────────────────────────────


def test_transition_score_align_field_default_none() -> None:
    s = TransitionScore()
    assert s.align is None


def test_transition_score_align_field_assignable() -> None:
    s = TransitionScore()
    s.align = AlignmentScore(
        s_tempo=0.8, s_beat_alignment=0.7,
        s_phrase_alignment=0.6, s_drift=0.9, overall=0.75,
    )
    assert s.align is not None
    assert s.align.s_tempo == 0.8


# ── TransitionScorer integration ───────────────────────────────────


def test_scorer_legacy_path_unchanged_with_default() -> None:
    """Legacy callers see byte-identical results when align is not requested."""
    a = _tf(bpm=128.0)
    b = _tf(bpm=128.5)
    s = TransitionScorer()
    score = s.score(a, b)
    assert score.align is None
    # Overall should still be the six-component weighted sum.
    assert 0.0 < score.overall < 1.0


def test_scorer_with_align_true_populates_alignment() -> None:
    a = _tf(bpm=128.0, first_downbeat_ms=0.0)
    b = _tf(bpm=128.0, first_downbeat_ms=0.0)
    score = TransitionScorer().score(a, b, align=True, transition_bars=16)
    assert score.align is not None
    assert score.align.s_tempo == pytest.approx(1.0)
    assert score.align.s_beat_alignment == pytest.approx(1.0)
    assert score.align.s_drift == pytest.approx(1.0)


def test_scorer_with_align_true_on_hard_reject_returns_alignment() -> None:
    """Hard-rejected pairs still carry alignment data so the UI can
    explain *why* a near-miss was rejected (Cell 18 mix composer)."""
    a = _tf(bpm=128.0, key_code=0)
    b = _tf(bpm=128.0, key_code=12)  # Camelot distance >= 5
    score = TransitionScorer().score(a, b, align=True, soft_camelot=False)
    assert score.hard_reject
    assert score.align is not None


def test_scorer_score_with_candidates_align() -> None:
    a = _tf(bpm=128.0)
    b = _tf(bpm=128.0)
    score = TransitionScorer().score_with_candidates(
        a, b, align=True, transition_bars=8
    )
    assert score.align is not None
    assert score.align.s_tempo == pytest.approx(1.0)

"""Unit tests for TransitionStyle enum and recommend_style/style_profile."""

from __future__ import annotations

import pytest

from app.core.constants import TRANSITION_STYLE_PROFILES, TransitionStyle
from app.domain.transition import TransitionScore, recommend_style, style_profile


def _score(**overrides: float | bool | str | None) -> TransitionScore:
    """Build a TransitionScore with sensible defaults; override per test."""
    base: dict[str, float | bool | str | None] = {
        "bpm": 0.85,
        "harmonic": 0.80,
        "energy": 0.80,
        "spectral": 0.75,
        "groove": 0.80,
        "timbral": 0.75,
        "overall": 0.80,
        "hard_reject": False,
        "reject_reason": None,
    }
    base.update(overrides)
    return TransitionScore(**base)  # type: ignore[arg-type]


# ── Style profile table integrity ────────────────────────────────────


def test_style_profiles_cover_every_enum_member() -> None:
    """Every TransitionStyle must have a profile entry — table can't drift."""
    enum_members = set(TransitionStyle)
    table_members = set(TRANSITION_STYLE_PROFILES.keys())
    assert enum_members == table_members


def test_style_profile_returns_metadata() -> None:
    profile = style_profile(TransitionStyle.BASS_SWAP_LONG)
    assert profile["bars"] == 32
    assert isinstance(profile["reason"], str)


def test_style_profile_bars_are_non_negative() -> None:
    for style in TransitionStyle:
        bars = style_profile(style)["bars"]
        assert isinstance(bars, int | float)
        assert bars >= 0


# ── recommend_style decision tree ────────────────────────────────────


def test_hard_reject_returns_filter_sweep() -> None:
    score = _score(hard_reject=True, reject_reason="bpm gap")
    assert recommend_style(score) == TransitionStyle.FILTER_SWEEP


def test_spectral_collision_takes_priority_over_other_axes() -> None:
    # Even with otherwise great scores, low spectral wins.
    score = _score(spectral=0.30, bpm=0.99, harmonic=0.99, groove=0.99, overall=0.90)
    assert recommend_style(score) == TransitionStyle.FILTER_SWEEP


def test_energy_gap_returns_echo_out() -> None:
    score = _score(energy=0.30, spectral=0.80)
    assert recommend_style(score) == TransitionStyle.ECHO_OUT


def test_harmonic_drift_returns_long_blend() -> None:
    score = _score(harmonic=0.40, spectral=0.80, energy=0.80)
    assert recommend_style(score) == TransitionStyle.LONG_BLEND


def test_perfect_match_returns_cut() -> None:
    score = _score(
        bpm=0.99,
        harmonic=0.95,
        groove=0.90,
        energy=0.85,
        spectral=0.85,
        overall=0.92,
    )
    assert recommend_style(score) == TransitionStyle.CUT


def test_strong_overall_returns_short_bass_swap() -> None:
    # Good but not perfect — bpm just below the cut threshold.
    score = _score(
        bpm=0.85,
        harmonic=0.80,
        groove=0.78,
        energy=0.80,
        spectral=0.78,
        overall=0.80,
    )
    assert recommend_style(score) == TransitionStyle.BASS_SWAP_SHORT


def test_default_returns_long_bass_swap() -> None:
    # Mid-range scores across the board → default DJ blend.
    score = _score(
        bpm=0.70,
        harmonic=0.65,
        groove=0.60,
        energy=0.60,
        spectral=0.60,
        overall=0.65,
    )
    assert recommend_style(score) == TransitionStyle.BASS_SWAP_LONG


# ── Boundary tests ───────────────────────────────────────────────────


def test_spectral_boundary_just_above_threshold() -> None:
    # 0.45 is the threshold — at exactly 0.45 we should NOT trigger sweep.
    score = _score(spectral=0.45, energy=0.80, harmonic=0.80)
    assert recommend_style(score) != TransitionStyle.FILTER_SWEEP


def test_energy_boundary_just_above_threshold() -> None:
    score = _score(energy=0.40, spectral=0.80, harmonic=0.80)
    assert recommend_style(score) != TransitionStyle.ECHO_OUT


@pytest.mark.parametrize(
    ("score_kwargs", "expected"),
    [
        ({"hard_reject": True}, TransitionStyle.FILTER_SWEEP),
        ({"spectral": 0.20}, TransitionStyle.FILTER_SWEEP),
        ({"energy": 0.10, "spectral": 0.80}, TransitionStyle.ECHO_OUT),
        (
            {"harmonic": 0.30, "spectral": 0.80, "energy": 0.80},
            TransitionStyle.LONG_BLEND,
        ),
    ],
)
def test_recommend_style_branches(
    score_kwargs: dict[str, float | bool], expected: TransitionStyle
) -> None:
    assert recommend_style(_score(**score_kwargs)) == expected

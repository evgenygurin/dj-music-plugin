"""Tests for subgenre pair classification + bar clamping."""

from __future__ import annotations

from app.domain.transition.subgenre_rules import (
    SubgenrePairType,
    clamp_bars,
    classify_pair,
)
from app.shared.constants import TechnoSubgenre


def test_classify_ambient_pair() -> None:
    assert (
        classify_pair(TechnoSubgenre.DUB_TECHNO, TechnoSubgenre.AMBIENT_DUB)
        == SubgenrePairType.AMBIENT_PAIR
    )


def test_classify_hard_pair() -> None:
    assert (
        classify_pair(TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO)
        == SubgenrePairType.HARD_PAIR
    )


def test_classify_acid_pair() -> None:
    assert classify_pair(TechnoSubgenre.ACID, TechnoSubgenre.DRIVING) == SubgenrePairType.ACID_PAIR


def test_classify_melodic_pair() -> None:
    assert (
        classify_pair(TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE)
        == SubgenrePairType.MELODIC_PAIR
    )


def test_classify_hypnotic_pair() -> None:
    assert (
        classify_pair(TechnoSubgenre.MINIMAL, TechnoSubgenre.HYPNOTIC)
        == SubgenrePairType.HYPNOTIC_PAIR
    )


def test_classify_mixed_pair() -> None:
    assert (
        classify_pair(TechnoSubgenre.PEAK_TIME, TechnoSubgenre.DUB_TECHNO)
        == SubgenrePairType.MIXED_PAIR
    )


def test_classify_none_mood() -> None:
    assert classify_pair(None, TechnoSubgenre.DRIVING) == SubgenrePairType.MIXED_PAIR


def test_classify_string_mood() -> None:
    assert classify_pair("industrial", "hard_techno") == SubgenrePairType.HARD_PAIR


def test_clamp_bars_ambient_lifts_to_floor() -> None:
    assert clamp_bars(16, SubgenrePairType.AMBIENT_PAIR) == 32


def test_clamp_bars_hard_lowers_to_ceiling() -> None:
    assert clamp_bars(64, SubgenrePairType.HARD_PAIR) == 16


def test_clamp_bars_hypnotic_inside_range() -> None:
    assert clamp_bars(32, SubgenrePairType.HYPNOTIC_PAIR) == 32


def test_clamp_bars_mixed_within_range() -> None:
    assert clamp_bars(16, SubgenrePairType.MIXED_PAIR) == 16

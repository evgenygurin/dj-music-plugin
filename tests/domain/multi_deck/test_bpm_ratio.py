from __future__ import annotations

import pytest

from app.domain.multi_deck.bpm_ratio import analyze_bpm_ratio


@pytest.mark.parametrize(
    ("bpm", "expected"),
    [(135.0, 3), (60.0, 5), (120.0, 4)],
)
def test_bpm_ratio_finds_matches(bpm: float, expected: int) -> None:
    result = analyze_bpm_ratio(bpm)
    assert len(result.matches) >= expected


def test_bpm_ratio_respects_range() -> None:
    result = analyze_bpm_ratio(60.0, bpm_range=(100, 200))
    assert all(100 <= match.bpm_b <= 200 for match in result.matches)


def test_bpm_ratio_filters_requested_ratios() -> None:
    result = analyze_bpm_ratio(120.0, ratios_of_interest=["3:4", "2:3"])
    assert {match.ratio_label for match in result.matches} <= {"3:4", "2:3"}


def test_bpm_ratio_has_alignment_metadata() -> None:
    result = analyze_bpm_ratio(128.0, ratios_of_interest=["3:4"])
    assert result.matches
    assert result.matches[0].bars_to_align == 12
    assert result.matches[0].seconds_to_align > 0


def test_unknown_ratio_is_ignored() -> None:
    result = analyze_bpm_ratio(120.0, ratios_of_interest=["7:8"])
    assert result.matches == []

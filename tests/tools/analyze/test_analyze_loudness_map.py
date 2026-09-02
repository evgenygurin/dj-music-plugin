"""Failing tests for analyze_loudness_map (TDD step 1)."""

from __future__ import annotations

from app.schemas.analyzer import LoudnessProfile
from app.tools.analyze.analyze_loudness_map import analyze_loudness_map


def test_loudness_profile_contract():
    lp = LoudnessProfile(bar=1, low=-25.0, mid=-20.0, high=-15.0, flux=2.5, lufs=-14.5)
    assert lp.bar == 1
    assert lp.low == -25.0
    assert lp.high == -15.0
    assert lp.flux > 0


def test_analyze_loudness_map_exists_and_is_pure():
    # Without DB access; pure function over synthetic signal.
    result = analyze_loudness_map(track_id=1, bars=16)
    assert isinstance(result, list)
    assert all(isinstance(r, LoudnessProfile) for r in result)
    assert len(result) == 1  # default phrase length = 16 bars → 1 phrase entry

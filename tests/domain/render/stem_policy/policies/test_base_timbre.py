"""Tests for BaseTimbrePolicy."""

from app.domain.render.stem_policy.models import (
    AvailableData,
    FadePlan,
    StemTransitionContext,
)
from app.domain.render.stem_policy.policies.base_timbre import BaseTimbrePolicy


def test_base_timbre_sets_hpf_and_gain_for_drums():
    """Drums stem: no HPF, 0 dB gain."""
    ctx = StemTransitionContext(stem="drums", track_input={})
    policy = BaseTimbrePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.hpf_hz is None
    assert result.gain_db == 0.0


def test_base_timbre_sets_hpf_for_vocals():
    """Vocals stem: 120 Hz HPF."""
    ctx = StemTransitionContext(stem="vocals", track_input={})
    policy = BaseTimbrePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.hpf_hz == 120


def test_base_timbre_sets_harmonic_to_80hz_at_minus_2db():
    """Harmonic stem: 80 Hz HPF, -2 dB gain."""
    ctx = StemTransitionContext(stem="harmonic", track_input={})
    policy = BaseTimbrePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.hpf_hz == 80
    assert result.gain_db == -2.0


def test_base_timbre_sets_percussion_to_120hz():
    """Percussion stem: 120 Hz HPF (per design)."""
    ctx = StemTransitionContext(stem="percussion", track_input={})
    policy = BaseTimbrePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.hpf_hz == 120


def test_base_timbre_raises_for_unknown_stem():
    """Unknown stems should raise ValueError (defense in depth)."""
    import pytest

    ctx = StemTransitionContext(stem="bogus", track_input={})
    policy = BaseTimbrePolicy()
    with pytest.raises(ValueError):
        policy.merge(FadePlan.identity(), ctx)


def test_base_timbre_adds_note():
    """Policy must add an explanatory note."""
    ctx = StemTransitionContext(stem="bass", track_input={})
    policy = BaseTimbrePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert any("base_timbre" in note for note in result.notes)

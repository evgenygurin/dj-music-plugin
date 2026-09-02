"""Tests for UserOverridePolicy."""

from app.domain.render.stem_policy.models import (
    AvailableData,
    FadePlan,
    StemTransitionContext,
)
from app.domain.render.stem_policy.policies.user_override import UserOverridePolicy


def test_user_override_applies_hpf():
    """User override sets hpf_hz."""
    ctx = StemTransitionContext(
        stem="drums",
        track_input={"user_overrides": {"hpf_hz": 80}},
    )
    policy = UserOverridePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.hpf_hz == 80


def test_user_override_applies_gain():
    """User override sets gain_db."""
    ctx = StemTransitionContext(
        stem="bass",
        track_input={"user_overrides": {"gain_db": -3.0}},
    )
    policy = UserOverridePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.gain_db == -3.0


def test_user_override_applies_curves():
    """User override sets fade_in/out curves."""
    ctx = StemTransitionContext(
        stem="vocals",
        track_input={
            "user_overrides": {
                "fade_in_curve": "tri",
                "fade_out_curve": "exp",
            }
        },
    )
    policy = UserOverridePolicy()
    result = policy.merge(FadePlan.identity(), ctx)
    assert result.fade_in_curve == "tri"
    assert result.fade_out_curve == "exp"


def test_user_override_no_overrides_returns_unchanged():
    """No overrides → plan unchanged (no notes added)."""
    ctx = StemTransitionContext(stem="drums", track_input={})
    policy = UserOverridePolicy()
    plan = FadePlan.identity()
    result = policy.merge(plan, ctx)
    assert result == plan


def test_user_override_always_wins_last_in_composite():
    """When composed with other policies, user_override runs last."""
    from app.domain.render.stem_policy.base import CompositeStemTransitionPolicy
    from app.domain.render.stem_policy.policies.base_timbre import BaseTimbrePolicy

    ctx = StemTransitionContext(
        stem="harmonic",
        track_input={"user_overrides": {"hpf_hz": 200}},
    )
    composite = CompositeStemTransitionPolicy([BaseTimbrePolicy(), UserOverridePolicy()])
    result = composite.compute(ctx)
    # User override (200) wins over base_timbre (80).
    assert result.hpf_hz == 200

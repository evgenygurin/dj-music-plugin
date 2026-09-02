"""Tests for FadePlan and AvailableData dataclasses."""

from app.domain.render.stem_policy.models import AvailableData, FadePlan, StemTransitionContext


def test_fade_plan_identity_is_neutral():
    """Identity fade plan has all defaults."""
    plan = FadePlan.identity()
    assert plan.fade_in_s is None
    assert plan.fade_out_s is None
    assert plan.gain_db == 0.0
    assert plan.hpf_hz is None
    assert plan.pinpoint_s is None
    assert plan.notes == ()


def test_fade_plan_update_returns_new_instance():
    """update() returns a new FadePlan with replacements."""
    plan = FadePlan.identity()
    new = plan.update(gain_db=-2.0, hpf_hz=120)
    assert new.gain_db == -2.0
    assert new.hpf_hz == 120
    # Original is unchanged (frozen).
    assert plan.gain_db == 0.0
    assert plan.hpf_hz is None


def test_available_data_defaults_all_false():
    """AvailableData defaults to all flags False."""
    avail = AvailableData()
    assert avail.has_beatgrid is False
    assert avail.has_sections is False
    assert avail.has_stem_features is False
    assert avail.has_embedding is False
    assert avail.analysis_levels_in == ()


def test_stem_transition_context_defaults_to_first_track():
    """Default StemTransitionContext has sensible defaults."""
    ctx = StemTransitionContext(stem="bass", track_input={})
    assert ctx.stem == "bass"
    assert ctx.is_first is False
    assert ctx.is_last is False
    assert ctx.base_d_in_s == 8.0
    assert ctx.target_bpm == 130.0
    assert ctx.available is not None


def test_stem_transition_context_is_immutable():
    """StemTransitionContext is frozen."""
    ctx = StemTransitionContext(stem="vocals", track_input={})
    try:
        ctx.stem = "drums"  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "FrozenInstanceError" in str(type(exc).__name__)
    else:
        raise AssertionError("expected mutation to fail on frozen dataclass")

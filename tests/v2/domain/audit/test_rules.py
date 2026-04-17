"""Techno audit rules tests (v2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.v2.domain.audit import (
    DEFAULT_AUDIT_RULES,
    AuditIssue,
    run_audit_rules,
)
from app.v2.domain.audit.rules import (
    BpmRangeRule,
    ClippingRiskRule,
    ExcessiveDynamicsRule,
    LufsRangeRule,
    NoiseSpectrumRule,
    TooHarmonicRule,
    UnreliableBpmRule,
    UnreliableKeyRule,
    VariableTempoRule,
)


@dataclass
class _FakeFeatures:
    """Duck-typed surrogate for TrackAudioFeaturesComputed."""

    bpm: float | None = None
    bpm_confidence: float | None = None
    variable_tempo: bool | None = None
    integrated_lufs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    key_confidence: float | None = None
    hp_ratio: float | None = None
    spectral_flatness: float | None = None


def test_default_rules_chain_has_nine() -> None:
    assert len(DEFAULT_AUDIT_RULES) == 9


def test_bpm_range_flags_low() -> None:
    rule = BpmRangeRule()
    issues = rule.check(1, "t", _FakeFeatures(bpm=100.0))
    assert len(issues) == 1
    assert issues[0].issue == "bpm_out_of_range"
    assert issues[0].severity == "warning"


def test_bpm_range_ok_in_range() -> None:
    rule = BpmRangeRule()
    assert rule.check(1, "t", _FakeFeatures(bpm=130.0)) == []


def test_bpm_range_skips_none() -> None:
    rule = BpmRangeRule()
    assert rule.check(1, "t", _FakeFeatures(bpm=None)) == []


def test_lufs_range_flags_too_loud() -> None:
    rule = LufsRangeRule()
    issues = rule.check(1, "t", _FakeFeatures(integrated_lufs=-2.0))
    assert len(issues) == 1
    assert issues[0].issue == "lufs_out_of_range"


def test_lufs_range_ok() -> None:
    rule = LufsRangeRule()
    assert rule.check(1, "t", _FakeFeatures(integrated_lufs=-8.0)) == []


def test_clipping_risk_flags_high_peak() -> None:
    rule = ClippingRiskRule()
    issues = rule.check(1, "t", _FakeFeatures(true_peak_db=0.5))
    assert len(issues) == 1
    assert issues[0].issue == "clipping_risk"


def test_clipping_risk_ok_below_threshold() -> None:
    rule = ClippingRiskRule()
    assert rule.check(1, "t", _FakeFeatures(true_peak_db=-1.0)) == []


def test_unreliable_bpm_flags_low_confidence() -> None:
    rule = UnreliableBpmRule()
    issues = rule.check(1, "t", _FakeFeatures(bpm_confidence=0.1))
    assert len(issues) == 1
    assert issues[0].issue == "unreliable_bpm"


def test_unreliable_key_flags_low_confidence() -> None:
    rule = UnreliableKeyRule()
    issues = rule.check(1, "t", _FakeFeatures(key_confidence=0.1))
    assert len(issues) == 1
    assert issues[0].issue == "unreliable_key"


def test_variable_tempo_flags_true() -> None:
    rule = VariableTempoRule()
    issues = rule.check(1, "t", _FakeFeatures(variable_tempo=True))
    assert len(issues) == 1
    assert issues[0].issue == "variable_tempo"
    assert issues[0].severity == "info"


def test_variable_tempo_skips_false() -> None:
    rule = VariableTempoRule()
    assert rule.check(1, "t", _FakeFeatures(variable_tempo=False)) == []


def test_too_harmonic_flags_high_hp() -> None:
    rule = TooHarmonicRule()
    issues = rule.check(1, "t", _FakeFeatures(hp_ratio=20.0))
    assert len(issues) == 1
    assert issues[0].issue == "too_harmonic"


def test_excessive_dynamics_flags_high_crest() -> None:
    rule = ExcessiveDynamicsRule()
    issues = rule.check(1, "t", _FakeFeatures(crest_factor_db=40.0))
    assert len(issues) == 1
    assert issues[0].issue == "excessive_dynamics"


def test_noise_spectrum_flags_high_flatness() -> None:
    rule = NoiseSpectrumRule()
    issues = rule.check(1, "t", _FakeFeatures(spectral_flatness=0.9))
    assert len(issues) == 1
    assert issues[0].issue == "noise_spectrum"


def test_run_audit_rules_collects_all_issues() -> None:
    feats = _FakeFeatures(
        bpm=100.0,  # out of range
        integrated_lufs=-2.0,  # too loud
        variable_tempo=True,  # info
    )
    issues = run_audit_rules(DEFAULT_AUDIT_RULES, 1, "t", feats)
    issues_by_type = {i.issue for i in issues}
    assert "bpm_out_of_range" in issues_by_type
    assert "lufs_out_of_range" in issues_by_type
    assert "variable_tempo" in issues_by_type


def test_audit_issue_is_frozen() -> None:
    issue = AuditIssue(track_id=1, title="x", issue="foo", severity="warning")
    import pytest

    with pytest.raises(Exception):  # dataclass FrozenInstanceError
        issue.track_id = 99  # type: ignore[misc]

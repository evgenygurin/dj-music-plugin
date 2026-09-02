"""Tests for analyze_harmonic_profile (pure, no DB)."""

from app.tools.analyze.analyze_harmonic_profile import analyze_harmonic_profile


def test_harmonic_profile_pure():
    result = analyze_harmonic_profile(track_id=42, target_keys=["Am", "F"])
    assert isinstance(result, dict)
    assert "S_h" in result
    assert result["key_agreements"] == ["Am", "F"]

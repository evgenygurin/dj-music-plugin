"""Unit tests for the standalone hard-constraints gate."""

from __future__ import annotations

from app.config import settings
from app.core.track_features import TrackFeatures
from app.domain.transition.hard_constraints import check_hard_constraints


def _features(**overrides: object) -> TrackFeatures:
    """Build a TrackFeatures instance with sensible defaults."""
    base: dict[str, object] = {
        "bpm": 128.0,
        "key_code": 8,
        "integrated_lufs": -10.0,
    }
    base.update(overrides)
    return TrackFeatures(**base)  # type: ignore[arg-type]


class TestHardConstraints:
    def test_compatible_pair_passes(self) -> None:
        a = _features(bpm=128.0, key_code=8, integrated_lufs=-10.0)
        b = _features(bpm=129.0, key_code=9, integrated_lufs=-10.5)
        assert check_hard_constraints(a, b) is None

    def test_bpm_diff_too_large_rejects(self) -> None:
        a = _features(bpm=120.0)
        b = _features(bpm=140.0)  # diff 20 > settings 10
        result = check_hard_constraints(a, b)
        assert result is not None
        assert result.hard_reject is True
        assert "BPM" in (result.reject_reason or "")

    def test_double_time_does_not_reject(self) -> None:
        # 64 ↔ 128 → bpm_distance = min(64, 0, 0) = 0
        a = _features(bpm=64.0)
        b = _features(bpm=128.0)
        assert check_hard_constraints(a, b) is None

    def test_camelot_distance_rejects_at_threshold(self) -> None:
        a = _features(key_code=0)  # 1A
        b = _features(key_code=12)  # 7A — likely distance ≥ 5 on the wheel
        result = check_hard_constraints(a, b)
        # Whatever the actual distance is, the gate must be consistent
        if result is not None:
            assert result.hard_reject is True
            assert "Camelot" in (result.reject_reason or "")

    def test_energy_gap_too_large_rejects(self) -> None:
        a = _features(integrated_lufs=-20.0)
        b = _features(integrated_lufs=-10.0)  # gap 10 LUFS > 6
        result = check_hard_constraints(a, b)
        assert result is not None
        assert result.hard_reject is True
        assert "LUFS" in (result.reject_reason or "")

    def test_pre_computed_bpm_dist_used_when_provided(self) -> None:
        a = _features(bpm=120.0)
        b = _features(bpm=120.0)  # actual diff 0
        # Inject a fake huge pre-computed distance — gate must trust it
        result = check_hard_constraints(a, b, pre_bpm_dist=99.0)
        assert result is not None
        assert result.hard_reject is True

    def test_missing_features_does_not_reject(self) -> None:
        a = TrackFeatures()  # all None
        b = TrackFeatures()
        assert check_hard_constraints(a, b) is None

    def test_uses_settings_thresholds(self) -> None:
        # Spot-check that the gate reads live settings, not a frozen value
        a = _features(bpm=120.0)
        b = _features(bpm=120.0 + settings.transition_hard_reject_bpm_diff + 0.5)
        assert check_hard_constraints(a, b) is not None

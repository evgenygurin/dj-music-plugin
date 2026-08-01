from __future__ import annotations

from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.shared.features import TrackFeatures


def _t(key_code: int) -> TrackFeatures:
    return TrackFeatures(bpm=128.0, key_code=key_code, key_confidence=0.9, atonality=False)


def test_strict_returns_reason():
    a, b = _t(0), _t(12)  # distance >= 5 on the wheel
    reason, warning = CamelotDistanceSpec().check(a, b)
    assert reason is not None and "Camelot" in reason
    assert warning is None


def test_soft_returns_warning_not_reason():
    a, b = _t(0), _t(12)
    reason, warning = CamelotDistanceSpec().check(a, b, soft=True)
    assert reason is None
    assert warning is not None and "Camelot" in warning and "(soft)" in warning


def test_compatible_pair_returns_none_none():
    a, b = _t(8), _t(9)
    assert CamelotDistanceSpec().check(a, b) == (None, None)
    assert CamelotDistanceSpec().check(a, b, soft=True) == (None, None)


def test_unreliable_key_never_rejects():
    a = TrackFeatures(bpm=128.0, key_code=0, key_confidence=0.9, atonality=True)
    b = TrackFeatures(bpm=128.0, key_code=12, key_confidence=0.9)
    assert CamelotDistanceSpec().check(a, b) == (None, None)

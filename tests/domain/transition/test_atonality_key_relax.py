"""Atonality-aware Camelot hard-reject relaxation.

The Camelot distance >= N hard reject must only fire when BOTH tracks have
reliable tonal content (not atonal AND key_confidence >= floor). On atonal /
low-confidence percussive tracks the key "clash" is inaudible, so the reject
is a false positive. Verifies the scalar gate and the vectorised bulk mask
agree (parity).
"""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.camelot.wheel import camelot_distance
from app.domain.transition.bulk_scorer import (
    extract_feature_arrays,
    hard_reject_mask_bulk,
    score_bass_bulk,
    score_harmonics_bulk,
)
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.neural_mix import score_bass_compat, score_harmonic_compat
from app.shared.features import TrackFeatures

# key_code 0 (1A) and 10 (6A) sit Camelot distance 5 apart → would hard-reject.
FAR_A, FAR_B = 0, 10


def test_far_key_fixture_is_a_reject_distance() -> None:
    assert camelot_distance(FAR_A, FAR_B) >= 5


def _tf(**kw: object) -> TrackFeatures:
    base: dict[str, object] = {"bpm": 128.0, "integrated_lufs": -8.0}
    base.update(kw)
    return TrackFeatures(**base)  # type: ignore[arg-type]


def test_tonal_confident_far_key_hard_rejects() -> None:
    a = _tf(key_code=FAR_A, atonality=False, key_confidence=0.9)
    b = _tf(key_code=FAR_B, atonality=False, key_confidence=0.9)
    res = check_hard_constraints(a, b)
    assert res is not None and res.hard_reject
    assert "Camelot" in (res.reject_reason or "")


def test_both_atonal_far_key_not_rejected() -> None:
    a = _tf(key_code=FAR_A, atonality=True, key_confidence=0.9)
    b = _tf(key_code=FAR_B, atonality=True, key_confidence=0.9)
    assert check_hard_constraints(a, b) is None


def test_one_atonal_far_key_not_rejected() -> None:
    a = _tf(key_code=FAR_A, atonality=True, key_confidence=0.9)
    b = _tf(key_code=FAR_B, atonality=False, key_confidence=0.9)
    assert check_hard_constraints(a, b) is None


def test_low_confidence_far_key_not_rejected() -> None:
    a = _tf(key_code=FAR_A, atonality=False, key_confidence=0.2)
    b = _tf(key_code=FAR_B, atonality=False, key_confidence=0.2)
    assert check_hard_constraints(a, b) is None


def test_unknown_fields_preserve_legacy_reject() -> None:
    # atonality / key_confidence None → treated as reliable → legacy reject.
    res = check_hard_constraints(_tf(key_code=FAR_A), _tf(key_code=FAR_B))
    assert res is not None and res.hard_reject


def test_atonal_still_rejects_on_bpm() -> None:
    # Relaxing the KEY gate must not relax the BPM gate.
    a = _tf(key_code=FAR_A, atonality=True, bpm=120.0)
    b = _tf(key_code=FAR_B, atonality=True, bpm=140.0)
    res = check_hard_constraints(a, b)
    assert res is not None and res.hard_reject
    assert "BPM" in (res.reject_reason or "")


def test_bulk_matches_scalar_on_atonal_relax() -> None:
    tracks = [
        _tf(key_code=FAR_A, atonality=True, key_confidence=0.9),  # 0
        _tf(key_code=FAR_B, atonality=True, key_confidence=0.9),  # 1 — atonal pair
        _tf(key_code=FAR_A, atonality=False, key_confidence=0.9),  # 2
        _tf(key_code=FAR_B, atonality=False, key_confidence=0.9),  # 3 — tonal pair
    ]
    fa = extract_feature_arrays(tracks)
    mask = hard_reject_mask_bulk(fa, np.array([0, 2]), np.array([1, 3]))
    assert mask.tolist() == [False, True]
    # Scalar agrees pair-for-pair.
    assert (check_hard_constraints(tracks[0], tracks[1]) is None) is True
    assert (check_hard_constraints(tracks[2], tracks[3]) is not None) is True


# ── Soft-score key neutralization (the Camelot term, not just the gate) ──


def test_atonal_key_neutralized_in_soft_bass() -> None:
    # For atonal pairs the key term is neutral → bass score is independent of
    # the Camelot distance (same-key and far-key score identically).
    near = score_bass_compat(_tf(key_code=0, atonality=True), _tf(key_code=0, atonality=True))
    far = score_bass_compat(
        _tf(key_code=FAR_A, atonality=True), _tf(key_code=FAR_B, atonality=True)
    )
    assert near == far


def test_tonal_key_still_matters_in_soft_bass() -> None:
    near = score_bass_compat(
        _tf(key_code=0, atonality=False, key_confidence=0.9),
        _tf(key_code=0, atonality=False, key_confidence=0.9),
    )
    far = score_bass_compat(
        _tf(key_code=FAR_A, atonality=False, key_confidence=0.9),
        _tf(key_code=FAR_B, atonality=False, key_confidence=0.9),
    )
    assert near > far


def test_atonal_key_neutralized_in_soft_harmonic() -> None:
    near = score_harmonic_compat(_tf(key_code=0, atonality=True), _tf(key_code=0, atonality=True))
    far = score_harmonic_compat(
        _tf(key_code=FAR_A, atonality=True), _tf(key_code=FAR_B, atonality=True)
    )
    assert near == far


def test_soft_bulk_matches_scalar_on_atonal() -> None:
    tracks = [_tf(key_code=0, atonality=True), _tf(key_code=FAR_B, atonality=True)]
    fa = extract_feature_arrays(tracks)
    ia, ib = np.array([0]), np.array([1])
    assert score_bass_bulk(fa, ia, ib)[0] == pytest.approx(
        score_bass_compat(tracks[0], tracks[1]), abs=1e-9
    )
    assert score_harmonics_bulk(fa, ia, ib)[0] == pytest.approx(
        score_harmonic_compat(tracks[0], tracks[1]), abs=1e-9
    )

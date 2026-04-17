"""Numeric parity: v2 TransitionScorer matches legacy on the same input."""

from __future__ import annotations

import pytest

from app.entities.audio.features import TrackFeatures as LegacyFeatures
from app.transition.scorer import TransitionScorer as LegacyScorer
from app.v2.domain.transition.features import TrackFeatures as V2Features
from app.v2.domain.transition.scorer import TransitionScorer as V2Scorer

_SHARED_KW = dict(
    bpm=128.0,
    key_code=5,
    integrated_lufs=-8.0,
    energy_mean=0.3,
    spectral_centroid_hz=3000.0,
    onset_rate=5.0,
    kick_prominence=0.5,
    hnr_db=10.0,
    chroma_entropy=0.6,
)
_NEXT_KW = {
    **_SHARED_KW,
    "bpm": 130.0,
    "key_code": 7,
    "integrated_lufs": -7.5,
    "energy_mean": 0.32,
}


def test_scorer_overall_parity() -> None:
    legacy = LegacyScorer().score(LegacyFeatures(**_SHARED_KW), LegacyFeatures(**_NEXT_KW))
    v2 = V2Scorer().score(V2Features(**_SHARED_KW), V2Features(**_NEXT_KW))
    assert legacy.overall == pytest.approx(v2.overall, abs=1e-9)
    assert legacy.hard_reject == v2.hard_reject


def test_scorer_component_parity() -> None:
    legacy = LegacyScorer().score(LegacyFeatures(**_SHARED_KW), LegacyFeatures(**_NEXT_KW))
    v2 = V2Scorer().score(V2Features(**_SHARED_KW), V2Features(**_NEXT_KW))
    for attr in ("bpm", "harmonic", "energy", "spectral", "groove", "timbral"):
        a, b = getattr(legacy, attr), getattr(v2, attr)
        assert a == pytest.approx(b, abs=1e-9), f"{attr}: legacy={a}, v2={b}"


def test_scorer_hard_reject_parity() -> None:
    a = _SHARED_KW
    b = {**_SHARED_KW, "bpm": 180.0}
    legacy = LegacyScorer().score(LegacyFeatures(**a), LegacyFeatures(**b))
    v2 = V2Scorer().score(V2Features(**a), V2Features(**b))
    assert legacy.hard_reject == v2.hard_reject
    assert legacy.overall == pytest.approx(v2.overall, abs=1e-9)

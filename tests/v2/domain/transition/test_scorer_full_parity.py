"""End-to-end parity: v2 TransitionScorer matches legacy on 5 representative pairs.

Covers full-score output (overall + 6 components + hard_reject flag) at 1e-9.
Complements the per-component parity harness in test_components_parity.py.
"""

from __future__ import annotations

import pytest

from app.entities.audio.features import TrackFeatures as LegacyFeatures
from app.transition.scorer import TransitionScorer as LegacyScorer
from app.v2.domain.transition.features import TrackFeatures as V2Features
from app.v2.domain.transition.scorer import TransitionScorer as V2Scorer

# ── 5 representative TrackFeatures pairs ───────────────────────────────────

# 1. Low-energy ambient (dub techno style)
_AMBIENT_A = dict(
    bpm=122.0,
    key_code=9,
    integrated_lufs=-18.0,
    spectral_centroid_hz=1500.0,
    spectral_flatness=0.08,
    energy_mean=0.10,
    onset_rate=1.5,
    kick_prominence=0.08,
    hnr_db=5.0,
    chroma_entropy=0.4,
    mfcc_vector=[0.1] * 13,
    energy_bands=[0.2, 0.3, 0.2, 0.15, 0.1, 0.03, 0.02],
    hp_ratio=3.0,
    pulse_clarity=0.05,
)
_AMBIENT_B = {
    **_AMBIENT_A,
    "bpm": 123.5,
    "key_code": 9,
    "integrated_lufs": -17.5,
    "energy_mean": 0.11,
}

# 2. Peak-time techno (driving, energetic)
_PEAK_A = dict(
    bpm=132.0,
    key_code=3,
    integrated_lufs=-6.5,
    spectral_centroid_hz=4200.0,
    spectral_flatness=0.15,
    energy_mean=0.55,
    onset_rate=8.5,
    kick_prominence=0.75,
    hnr_db=18.0,
    chroma_entropy=0.7,
    mfcc_vector=[0.5] * 13,
    energy_bands=[0.15, 0.25, 0.20, 0.15, 0.10, 0.10, 0.05],
    hp_ratio=0.8,
    pulse_clarity=0.25,
)
_PEAK_B = {**_PEAK_A, "bpm": 133.0, "key_code": 4, "integrated_lufs": -6.0, "energy_mean": 0.58}

# 3. Acid mismatch (should hard-reject on large BPM gap)
_ACID_A = dict(
    bpm=126.0,
    key_code=11,
    integrated_lufs=-8.0,
    spectral_centroid_hz=3800.0,
    energy_mean=0.45,
    onset_rate=6.0,
    kick_prominence=0.5,
    hnr_db=12.0,
    chroma_entropy=0.65,
)
_ACID_B = {**_ACID_A, "bpm": 145.0, "key_code": 11}  # 19 BPM gap → hard reject

# 4. Atonal pair (industrial, noisy)
_ATONAL_A = dict(
    bpm=135.0,
    key_code=0,
    integrated_lufs=-5.5,
    spectral_centroid_hz=5500.0,
    spectral_flatness=0.35,
    energy_mean=0.6,
    onset_rate=7.0,
    kick_prominence=0.8,
    hnr_db=-5.0,
    chroma_entropy=0.95,
    atonality=True,
    key_confidence=0.2,
    mfcc_vector=[0.6] * 13,
)
_ATONAL_B = {
    **_ATONAL_A,
    "bpm": 136.5,
    "key_code": 2,
    "integrated_lufs": -5.0,
    "atonality": True,
    "key_confidence": 0.25,
}

# 5. Drum-only-friendly pair (sparse minimal with low HP ratio)
_DRUM_A = dict(
    bpm=128.0,
    key_code=5,
    integrated_lufs=-9.0,
    spectral_centroid_hz=2800.0,
    spectral_flatness=0.12,
    energy_mean=0.35,
    onset_rate=4.5,
    kick_prominence=0.6,
    hnr_db=8.0,
    chroma_entropy=0.55,
    mfcc_vector=[0.3] * 13,
    energy_bands=[0.18, 0.22, 0.18, 0.14, 0.12, 0.10, 0.06],
    hp_ratio=0.5,
    pulse_clarity=0.15,
)
_DRUM_B = {
    **_DRUM_A,
    "bpm": 128.5,
    "key_code": 10,  # far on Camelot
    "integrated_lufs": -8.5,
    "energy_mean": 0.36,
}


_PAIRS = [
    ("ambient", _AMBIENT_A, _AMBIENT_B),
    ("peak_time", _PEAK_A, _PEAK_B),
    ("acid_gap", _ACID_A, _ACID_B),
    ("atonal", _ATONAL_A, _ATONAL_B),
    ("drum_only", _DRUM_A, _DRUM_B),
]


@pytest.mark.parametrize(("label", "kw_a", "kw_b"), _PAIRS, ids=[p[0] for p in _PAIRS])
def test_scorer_full_parity(label: str, kw_a: dict, kw_b: dict) -> None:
    """For each representative pair, legacy and v2 TransitionScorer agree at 1e-9.

    Checks: overall + 6 components (bpm, harmonic, energy, spectral, groove,
    timbral) + hard_reject flag. End-to-end parity — not just per-component.
    """
    legacy = LegacyScorer().score(LegacyFeatures(**kw_a), LegacyFeatures(**kw_b))
    v2 = V2Scorer().score(V2Features(**kw_a), V2Features(**kw_b))

    assert legacy.hard_reject == v2.hard_reject, (
        f"[{label}] hard_reject differs: legacy={legacy.hard_reject} v2={v2.hard_reject}"
    )
    assert legacy.overall == pytest.approx(v2.overall, abs=1e-9), f"[{label}] overall differs"
    for attr in ("bpm", "harmonic", "energy", "spectral", "groove", "timbral"):
        a, b = getattr(legacy, attr), getattr(v2, attr)
        assert a == pytest.approx(b, abs=1e-9), f"[{label}] {attr}: legacy={a}, v2={b}"

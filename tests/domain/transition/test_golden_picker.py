"""Level 3 golden tests -- picker decisions.

For each representative (score, fa, fb, context, subgenre_pair, intent)
input, snapshot the PickerDecision (transition, confidence, reason,
warnings, rescue). Used to guard the Chain-of-Responsibility migration
in Phase 6: first-match-wins rule order must be preserved exactly.
"""

from __future__ import annotations

import pytest

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.picker import pick_neural_mix
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

from ._golden_harness import load_or_write
from .test_golden_scoring import _acid_a, _acid_b, _vocal_techno_a, _vocal_techno_b


def _high_vocal_track() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        key_code=8,
        integrated_lufs=-8.0,
        pitch_salience_mean=0.75,
        spectral_centroid_hz=2800.0,
        energy_bands=[0.08, 0.10, 0.18, 0.22, 0.20, 0.22],
        tonnetz_vector=[0.1] * 6,
        mfcc_vector=[1.0] * 13,
    )


def _low_vocal_track() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        key_code=8,
        integrated_lufs=-8.0,
        pitch_salience_mean=0.2,
        spectral_centroid_hz=1800.0,
        energy_bands=[0.15, 0.18, 0.12, 0.14, 0.20, 0.21],
        tonnetz_vector=[0.1] * 6,
        mfcc_vector=[1.0] * 13,
    )


def _harmonic_motif_track() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        key_code=8,
        integrated_lufs=-8.0,
        pitch_salience_mean=0.25,
        spectral_centroid_hz=1500.0,
        tonnetz_vector=[0.2, 0.15, 0.1, 0.05, 0.03, 0.01],
        mfcc_vector=[1.0] * 13,
        energy_bands=[0.15, 0.18, 0.20, 0.18, 0.15, 0.14],
    )


def _low_energy_track() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        key_code=8,
        integrated_lufs=-9.0,
        pitch_salience_mean=0.2,
        spectral_centroid_hz=1800.0,
        energy_bands=[0.15] * 6,
        mfcc_vector=[1.0] * 13,
    )


def _high_energy_track() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        key_code=8,
        integrated_lufs=-5.0,
        pitch_salience_mean=0.2,
        spectral_centroid_hz=1800.0,
        energy_bands=[0.15] * 6,
        mfcc_vector=[1.0] * 13,
    )


def _b_vocal_missing() -> TrackFeatures:
    return TrackFeatures(bpm=125.0, key_code=8, integrated_lufs=-8.0)


CASES: list[dict] = [
    {
        "id": "hard_reject",
        "score": TransitionScore(hard_reject=True, reject_reason="BPM diff 15 > 10"),
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "drum_only_high_drums",
        "score": TransitionScore(drums=0.92),
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
        "sg": None,
        "int": None,
    },
    {
        "id": "drum_only_mid_drums",
        "score": TransitionScore(drums=0.75),
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
        "sg": None,
        "int": None,
    },
    {
        "id": "drum_only_low_drums",
        "score": TransitionScore(drums=0.50),
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "ctx": SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),
        "sg": None,
        "int": None,
    },
    {
        "id": "vocal_active_a_low_b",
        "score": TransitionScore(bpm=0.95, energy=0.9),
        "a": _high_vocal_track,
        "b": _low_vocal_track,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "vocal_active_a_high_b",
        "score": TransitionScore(bpm=0.95, energy=0.9),
        "a": _high_vocal_track,
        "b": _high_vocal_track,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "vocal_active_a_missing_b",
        "score": TransitionScore(bpm=0.95, energy=0.9),
        "a": _high_vocal_track,
        "b": _b_vocal_missing,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "harmonic_motif_a_low_b",
        "score": TransitionScore(bpm=0.95, harmonics=0.9),
        "a": _harmonic_motif_track,
        "b": _low_vocal_track,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "energy_ramp_up",
        "score": TransitionScore(bpm=0.92, energy=0.7),
        "a": _low_energy_track,
        "b": _high_energy_track,
        "ctx": None,
        "sg": None,
        "int": TransitionIntent.RAMP_UP,
    },
    {
        "id": "energy_ramp_up_hard_pair",
        "score": TransitionScore(bpm=0.92, energy=0.7),
        "a": _low_energy_track,
        "b": _high_energy_track,
        "ctx": None,
        "sg": SubgenrePairType.HARD_PAIR,
        "int": None,
    },
    {
        "id": "ambient_pair",
        "score": TransitionScore(bpm=0.95, energy=0.9),
        "a": _low_vocal_track,
        "b": _low_vocal_track,
        "ctx": None,
        "sg": SubgenrePairType.AMBIENT_PAIR,
        "int": None,
    },
    {
        "id": "cool_down_intent",
        "score": TransitionScore(bpm=0.95, energy=0.9),
        "a": _low_vocal_track,
        "b": _low_vocal_track,
        "ctx": None,
        "sg": None,
        "int": TransitionIntent.COOL_DOWN,
    },
    {
        "id": "default_safe",
        "score": TransitionScore(bpm=0.9, energy=0.85),
        "a": _low_vocal_track,
        "b": _low_vocal_track,
        "ctx": None,
        "sg": None,
        "int": None,
    },
    {
        "id": "acid_pair_v1_4_0_regression",
        "score": TransitionScore(
            bpm=0.99,
            energy=0.96,
            drums=0.84,
            bass=0.92,
            harmonics=0.81,
            vocals=0.42,
            overall=0.83,
        ),
        "a": _acid_a,
        "b": _acid_b,
        "ctx": None,
        "sg": None,
        "int": None,
    },
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_picker_decision_golden(case: dict) -> None:
    a = case["a"]()
    b = case["b"]()
    decision = pick_neural_mix(
        case["score"],
        a,
        b,
        section_context=case["ctx"],
        subgenre_pair=case["sg"],
        intent=case["int"],
    )
    actual = {
        "transition": str(decision.transition),
        "confidence": decision.confidence,
        "reason": decision.reason,
        "warnings": list(decision.warnings),
        "rescue": str(decision.rescue),
    }
    expected = load_or_write(f"picker_{case['id']}", actual)
    assert actual["transition"] == expected["transition"], f"{case['id']}.transition"
    assert abs(actual["confidence"] - expected["confidence"]) <= 1e-9, f"{case['id']}.confidence"
    assert actual["reason"] == expected["reason"], f"{case['id']}.reason"
    assert actual["warnings"] == expected["warnings"], f"{case['id']}.warnings"
    assert actual["rescue"] == expected["rescue"], f"{case['id']}.rescue"

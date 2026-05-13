"""Level 1 golden tests — scoring math snapshots.

Twenty representative (from_track, to_track, intent, section_context)
scenarios. Each emits a frozen TransitionScore. Snapshot persisted in
_golden/scoring_<id>.json. Tolerance: 1e-9 for component fields, 1e-7
for overall (accumulator noise).

Coverage targets:
  * Phase-0 acid pair: vocal_active false-positive fix.
  * Phase-1 drum-only overlay: section_pair_class="drum_only".
  * Phase-1 SectionContext=None: identical to no-overlay path.
  * Hard reject cases: BPM, Camelot, energy gap.
  * All four TransitionIntent values, with and without section_context.
  * Missing-field cases: bpm=None, key_code=None, integrated_lufs=None.
"""

from __future__ import annotations

import pytest

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionContext
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

from ._golden_harness import assert_close, load_or_write


def _vocal_techno_a() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.0,
        bpm_stability=0.92,
        bpm_confidence=0.88,
        variable_tempo=False,
        key_code=8,
        integrated_lufs=-8.5,
        loudness_range_lu=5.2,
        crest_factor_db=10.1,
        energy_slope=0.05,
        spectral_centroid_hz=3200.0,
        spectral_contrast=0.55,
        chroma_entropy=0.7,
        pitch_salience_mean=0.72,
        onset_rate=4.5,
        kick_prominence=0.65,
        hnr_db=-12.0,
        dissonance_mean=0.32,
        mfcc_vector=[10.0, -5.0, 2.0, 1.5, -0.5, 0.3, 0.1, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.1, 0.05, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.10, 0.15, 0.12, 0.18, 0.22, 0.23],
        beat_loudness_band_ratio=[0.8, 0.6, 0.4, 0.3, 0.2, 0.1],
    )


def _vocal_techno_b() -> TrackFeatures:
    return TrackFeatures(
        bpm=125.5,
        bpm_stability=0.90,
        bpm_confidence=0.85,
        variable_tempo=False,
        key_code=8,
        integrated_lufs=-8.0,
        loudness_range_lu=5.0,
        crest_factor_db=10.0,
        energy_slope=0.06,
        spectral_centroid_hz=3100.0,
        spectral_contrast=0.50,
        chroma_entropy=0.65,
        pitch_salience_mean=0.70,
        onset_rate=4.6,
        kick_prominence=0.67,
        hnr_db=-13.0,
        dissonance_mean=0.30,
        mfcc_vector=[9.5, -4.8, 1.8, 1.4, -0.4, 0.3, 0.1, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.1, 0.04, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.11, 0.16, 0.13, 0.18, 0.20, 0.22],
        beat_loudness_band_ratio=[0.85, 0.55, 0.4, 0.3, 0.2, 0.1],
    )


def _acid_a() -> TrackFeatures:
    """Acid TB-303-style — pitch_salience+centroid high but energy in highmid."""
    return TrackFeatures(
        bpm=128.0,
        bpm_stability=0.95,
        bpm_confidence=0.92,
        variable_tempo=False,
        key_code=2,
        integrated_lufs=-6.8,
        loudness_range_lu=4.2,
        crest_factor_db=8.5,
        energy_slope=0.02,
        spectral_centroid_hz=3600.0,
        spectral_contrast=0.65,
        chroma_entropy=0.5,
        pitch_salience_mean=0.78,
        onset_rate=5.2,
        kick_prominence=0.72,
        hnr_db=-15.0,
        dissonance_mean=0.45,
        mfcc_vector=[12.0, -6.0, 3.0, 2.0, -1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        # Energy concentrated in highmid (idx 4) — distinctly NOT lowmid+mid.
        energy_bands=[0.08, 0.10, 0.10, 0.12, 0.35, 0.25],
        beat_loudness_band_ratio=[0.9, 0.7, 0.5, 0.4, 0.3, 0.2],
    )


def _acid_b() -> TrackFeatures:
    return TrackFeatures(
        bpm=128.5,
        bpm_stability=0.93,
        bpm_confidence=0.90,
        variable_tempo=False,
        key_code=2,
        integrated_lufs=-6.5,
        loudness_range_lu=4.0,
        crest_factor_db=8.2,
        energy_slope=0.03,
        spectral_centroid_hz=3700.0,
        spectral_contrast=0.68,
        chroma_entropy=0.48,
        pitch_salience_mean=0.80,
        onset_rate=5.4,
        kick_prominence=0.74,
        hnr_db=-14.0,
        dissonance_mean=0.42,
        mfcc_vector=[12.2, -5.8, 3.1, 2.1, -1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        energy_bands=[0.08, 0.10, 0.10, 0.12, 0.35, 0.25],
        beat_loudness_band_ratio=[0.9, 0.7, 0.5, 0.4, 0.3, 0.2],
    )


def _hard_reject_bpm_far() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=145.0,
        bpm_stability=0.9,
        bpm_confidence=0.85,
        variable_tempo=False,
        key_code=8,
        integrated_lufs=-8.0,
        loudness_range_lu=5.0,
        crest_factor_db=10.0,
        spectral_centroid_hz=3100.0,
        mfcc_vector=[0.0] * 13,
    )
    return a, b


def _hard_reject_camelot_far() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=125.5,
        bpm_stability=0.9,
        bpm_confidence=0.85,
        variable_tempo=False,
        key_code=15,
        integrated_lufs=-8.0,
        loudness_range_lu=5.0,
        crest_factor_db=10.0,
        spectral_centroid_hz=3100.0,
        mfcc_vector=[0.0] * 13,
    )
    return a, b


def _hard_reject_energy() -> tuple[TrackFeatures, TrackFeatures]:
    a = _vocal_techno_a()
    b = TrackFeatures(
        bpm=125.5,
        bpm_stability=0.9,
        bpm_confidence=0.85,
        variable_tempo=False,
        key_code=8,
        integrated_lufs=-0.5,
        loudness_range_lu=5.0,
        crest_factor_db=10.0,
        spectral_centroid_hz=3100.0,
        mfcc_vector=[0.0] * 13,
    )
    return a, b


def _missing_fields() -> tuple[TrackFeatures, TrackFeatures]:
    return TrackFeatures(), TrackFeatures()


CASES: list[dict] = [
    {
        "id": "vocal_techno_pair_no_context",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "vocal_techno_pair_maintain",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": TransitionIntent.MAINTAIN,
        "section_context": None,
    },
    {
        "id": "vocal_techno_pair_ramp_up",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": TransitionIntent.RAMP_UP,
        "section_context": None,
    },
    {
        "id": "vocal_techno_pair_cool_down",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": TransitionIntent.COOL_DOWN,
        "section_context": None,
    },
    {
        "id": "vocal_techno_pair_contrast",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": TransitionIntent.CONTRAST,
        "section_context": None,
    },
    {
        "id": "vocal_techno_drum_only_overlay",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.OUTRO, to_section=SectionType.INTRO
        ),
    },
    {
        "id": "vocal_techno_drop_to_drop",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.DROP, to_section=SectionType.DROP
        ),
    },
    {
        "id": "vocal_techno_breakdown_out",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.BREAKDOWN, to_section=SectionType.INTRO
        ),
    },
    {
        "id": "vocal_techno_buildup_in",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.BUILD, to_section=SectionType.DROP
        ),
    },
    {
        "id": "vocal_techno_generic_pair",
        "a": _vocal_techno_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.ATTACK, to_section=SectionType.SUSTAIN
        ),
    },
    {
        "id": "acid_pair_no_context_phase0_regression",
        "a": _acid_a,
        "b": _acid_b,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "acid_pair_drum_only_phase1",
        "a": _acid_a,
        "b": _acid_b,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.OUTRO, to_section=SectionType.INTRO
        ),
    },
    {
        "id": "acid_pair_ramp_up",
        "a": _acid_a,
        "b": _acid_b,
        "intent": TransitionIntent.RAMP_UP,
        "section_context": None,
    },
    {
        "id": "hard_reject_bpm_too_far",
        "ab": _hard_reject_bpm_far,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "hard_reject_camelot_too_far",
        "ab": _hard_reject_camelot_far,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "hard_reject_energy_gap",
        "ab": _hard_reject_energy,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "missing_all_fields",
        "ab": _missing_fields,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "missing_all_fields_drum_only",
        "ab": _missing_fields,
        "intent": None,
        "section_context": SectionContext(
            from_section=SectionType.OUTRO, to_section=SectionType.INTRO
        ),
    },
    {
        "id": "asymmetric_vocal_to_acid",
        "a": _vocal_techno_a,
        "b": _acid_b,
        "intent": None,
        "section_context": None,
    },
    {
        "id": "asymmetric_acid_to_vocal",
        "a": _acid_a,
        "b": _vocal_techno_b,
        "intent": None,
        "section_context": None,
    },
]


def _resolve(case: dict) -> tuple[TrackFeatures, TrackFeatures]:
    if "ab" in case:
        return case["ab"]()
    return case["a"](), case["b"]()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_scoring_golden(case: dict) -> None:
    a, b = _resolve(case)
    scorer = TransitionScorer()
    score = scorer.score(a, b, intent=case["intent"], section_context=case["section_context"])
    actual = {
        "bpm": score.bpm,
        "energy": score.energy,
        "drums": score.drums,
        "bass": score.bass,
        "harmonics": score.harmonics,
        "vocals": score.vocals,
        "overall": score.overall,
        "hard_reject": score.hard_reject,
        "reject_reason": score.reject_reason,
        "best_transition": (
            str(score.best_transition) if score.best_transition is not None else None
        ),
        "section_pair_class": score.section_pair_class,
    }
    expected = load_or_write(f"scoring_{case['id']}", actual)
    for field in ("bpm", "energy", "drums", "bass", "harmonics", "vocals"):
        assert_close(actual[field], expected[field], tol=1e-9, label=f"{case['id']}.{field}")
    assert_close(actual["overall"], expected["overall"], tol=1e-7, label=f"{case['id']}.overall")
    assert actual["hard_reject"] == expected["hard_reject"], f"{case['id']}.hard_reject"
    assert actual["reject_reason"] == expected["reject_reason"], f"{case['id']}.reject_reason"
    assert actual["best_transition"] == expected["best_transition"], (
        f"{case['id']}.best_transition"
    )
    assert actual["section_pair_class"] == expected["section_pair_class"], (
        f"{case['id']}.section_pair_class"
    )

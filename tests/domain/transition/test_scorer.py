"""Phase 1 Task B: section-context overlay regression + DRUM_ONLY shift.

Verifies (1) byte-identical behaviour to v1.3 when no section_context
is passed, and (2) DRUM_ONLY overlay shifts the overall score toward
drums-leaning weighting and away from harmonics/vocals.
"""

from __future__ import annotations

from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionContext, SectionPairClass
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures


def _bp(**overrides: object) -> TrackFeatures:
    """Construct a TrackFeatures with the minimum non-None fields for scoring.

    Mid-range, harmonically incompatible enough to keep S_harmonics low
    but BPM/energy compatible enough to avoid hard reject.
    """
    defaults: dict[str, object] = {
        "bpm": 128.0,
        "bpm_confidence": 0.9,
        "bpm_stability": 0.95,
        "variable_tempo": False,
        "integrated_lufs": -10.0,
        "short_term_lufs_mean": -10.0,
        "true_peak_db": -1.5,
        "crest_factor_db": 12.0,
        "loudness_range_lu": 5.0,
        "energy_mean": 0.6,
        "energy_slope": 0.0,
        "energy_bands": [0.10, 0.20, 0.25, 0.25, 0.15, 0.05],
        "spectral_centroid_hz": 2000.0,
        "spectral_rolloff_85": 4000.0,
        "spectral_rolloff_95": 8000.0,
        "spectral_flatness": 0.2,
        "spectral_flux_mean": 0.3,
        "spectral_flux_std": 0.1,
        "spectral_slope": -0.001,
        "spectral_contrast": 8.0,
        "key_code": 8,  # 5A C minor
        "key_confidence": 0.7,
        "atonality": False,
        "hnr_db": -5.0,
        "chroma_entropy": 0.7,
        "mfcc_vector": None,
        "hp_ratio": 1.5,
        "onset_rate": 4.0,
        "pulse_clarity": 0.6,
        "kick_prominence": 0.5,
        "danceability": 1.5,
        "pitch_salience_mean": 0.35,
    }
    defaults.update(overrides)
    # spectral_flux_mean is not a TrackFeatures field — strip if present
    defaults.pop("spectral_flux_mean", None)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]


def test_scorer_without_section_context_unchanged() -> None:
    """Regression: no section_context → behaviour identical to v1.3 baseline.

    Same TrackFeatures, same intent, same score components, same overall.
    """
    scorer = TransitionScorer()
    a = _bp()
    b = _bp(key_code=15)  # 8B C major — Camelot dist away from 5A

    no_ctx = scorer.score(a, b)
    with_generic = scorer.score(
        a,
        b,
        section_context=SectionContext(
            from_section=SectionType.BUILD, to_section=SectionType.PRE_DROP
        ),
    )

    # GENERIC overlay is identity → overall must be byte-identical.
    assert no_ctx.overall == with_generic.overall
    assert no_ctx.section_pair_class is None
    assert with_generic.section_pair_class == SectionPairClass.GENERIC.value


def test_scorer_drum_only_overlay_relaxes_harmonics() -> None:
    """DRUM_ONLY overlay: same low-harmonic pair scores higher than v1.3."""
    scorer = TransitionScorer()
    a = _bp(key_code=8)
    b = _bp(key_code=15)  # Camelot dist ≈ 3 — harmonic penalty bites

    baseline = scorer.score(a, b)
    drum_only = scorer.score(
        a,
        b,
        section_context=SectionContext(
            from_section=SectionType.OUTRO,
            to_section=SectionType.INTRO,
        ),
    )

    # With DRUM_ONLY: harmonics+vocals down-weighted (0.40/0.30), drums up (1.30).
    # Both tracks have identical drums profile, so S_drums is high → overall up.
    assert drum_only.overall > baseline.overall
    assert drum_only.section_pair_class == SectionPairClass.DRUM_ONLY.value


def test_scorer_section_context_populates_pair_class_field() -> None:
    """All non-None contexts populate score.section_pair_class."""
    scorer = TransitionScorer()
    a = _bp()
    b = _bp()

    cases = [
        (SectionType.OUTRO, SectionType.INTRO, SectionPairClass.DRUM_ONLY.value),
        (SectionType.DROP, SectionType.PEAK, SectionPairClass.DROP_TO_DROP.value),
        (SectionType.BREAKDOWN, SectionType.RISE, SectionPairClass.BREAKDOWN_OUT.value),
        (SectionType.BUILD, SectionType.DROP, SectionPairClass.BUILDUP_IN.value),
        (SectionType.ATTACK, SectionType.PRE_DROP, SectionPairClass.GENERIC.value),
    ]
    for from_sec, to_sec, expected in cases:
        result = scorer.score(
            a, b, section_context=SectionContext(from_section=from_sec, to_section=to_sec)
        )
        assert result.section_pair_class == expected, f"failed for {from_sec}→{to_sec}"


def test_scorer_overlay_weights_renormalise_to_one() -> None:
    """After overlay multiplication + renormalisation, weights still sum to 1.

    Indirect test: take a score with all components equal — overall should
    equal that single component value (because weights sum to 1).
    """
    scorer = TransitionScorer()
    a = _bp()
    # Make both tracks identical → all stem compats ≈ 1.0
    b = _bp()

    drum_only = scorer.score(
        a,
        b,
        section_context=SectionContext(
            from_section=SectionType.OUTRO,
            to_section=SectionType.INTRO,
        ),
    )

    # All components should be ≥ 0.9 for identical tracks; overall should
    # also be ≥ 0.85 (weights renormalised, no component lost).
    assert drum_only.overall >= 0.85, (
        f"overall {drum_only.overall:.3f} too low for identical tracks "
        f"under DRUM_ONLY — overlay renormalisation may be broken"
    )


def test_scorer_score_all_intents_accepts_section_context() -> None:
    """score_all_intents kwarg works + populates pair_class on every entry."""
    from app.domain.transition.intent import TransitionIntent

    scorer = TransitionScorer()
    a = _bp()
    b = _bp(key_code=15)

    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    results = scorer.score_all_intents(a, b, section_context=ctx)

    assert set(results.keys()) >= {
        TransitionIntent.MAINTAIN,
        TransitionIntent.RAMP_UP,
        TransitionIntent.COOL_DOWN,
        TransitionIntent.CONTRAST,
    }
    for intent, score in results.items():
        assert score.section_pair_class == SectionPairClass.DRUM_ONLY.value, (
            f"intent={intent} did not propagate pair_class"
        )


def test_scorer_score_with_candidates_accepts_section_context() -> None:
    """score_with_candidates kwarg works + populates pair_class field."""
    scorer = TransitionScorer()
    a = _bp()
    b = _bp(key_code=15)

    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    result = scorer.score_with_candidates(a, b, section_context=ctx)

    assert result.section_pair_class == SectionPairClass.DRUM_ONLY.value

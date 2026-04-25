"""Section-aware transition scoring (commit 5).

Tests both the SectionContext dataclass invariants and the integration
points: harmonic relaxation floor and the drum-only weight override
on the full TransitionScorer.
"""

from __future__ import annotations

from app.domain.transition import SectionContext, TransitionScorer
from app.domain.transition.components.harmonic import score_harmonic
from app.domain.transition.weights import (
    DRUM_ONLY_HARMONIC_FLOOR,
    DRUM_ONLY_WEIGHT_OVERRIDE,
)
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

# ── SectionContext invariants ────────────────────────────────────────


class TestSectionContext:
    def test_drum_only_pair_intro_to_intro(self) -> None:
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is True

    def test_drum_only_pair_outro_to_intro(self) -> None:
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is True

    def test_drum_only_pair_sustain_to_ambient(self) -> None:
        ctx = SectionContext(from_section=SectionType.SUSTAIN, to_section=SectionType.AMBIENT)
        assert ctx.is_drum_only_pair is True

    def test_drop_to_intro_is_not_drum_only(self) -> None:
        ctx = SectionContext(from_section=SectionType.DROP, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is False

    def test_intro_to_drop_is_not_drum_only(self) -> None:
        ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.DROP)
        assert ctx.is_drum_only_pair is False

    def test_none_section_means_no_information(self) -> None:
        ctx = SectionContext(from_section=None, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is False
        ctx2 = SectionContext(from_section=SectionType.OUTRO, to_section=None)
        assert ctx2.is_drum_only_pair is False
        ctx3 = SectionContext(from_section=None, to_section=None)
        assert ctx3.is_drum_only_pair is False

    def test_frozen_dataclass(self) -> None:
        from dataclasses import FrozenInstanceError

        import pytest

        ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.OUTRO)
        with pytest.raises(FrozenInstanceError):
            ctx.from_section = SectionType.DROP  # type: ignore[misc]


# ── score_harmonic relaxation ────────────────────────────────────────


def _atonal_pair_with_key_drift() -> tuple[TrackFeatures, TrackFeatures]:
    """Two tracks with high Camelot distance but typical techno features."""
    a = TrackFeatures(
        bpm=128.0,
        key_code=0,
        key_confidence=0.6,
        atonality=False,
        hnr_db=-5.0,
        tonnetz_vector=None,
    )
    b = TrackFeatures(
        bpm=128.0,
        key_code=8,  # 4 steps away on Camelot wheel
        key_confidence=0.6,
        atonality=False,
        hnr_db=-5.0,
        tonnetz_vector=None,
    )
    return a, b


class TestHarmonicSectionRelax:
    def test_no_context_keeps_baseline_score(self) -> None:
        a, b = _atonal_pair_with_key_drift()
        score = score_harmonic(a, b)
        # Baseline has Camelot dist 4 → very low base
        assert score < 0.5

    def test_drum_only_pair_gets_floor(self) -> None:
        a, b = _atonal_pair_with_key_drift()
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
        score = score_harmonic(a, b, section_context=ctx)
        assert score >= DRUM_ONLY_HARMONIC_FLOOR

    def test_non_drum_pair_does_not_get_floor(self) -> None:
        a, b = _atonal_pair_with_key_drift()
        ctx = SectionContext(from_section=SectionType.DROP, to_section=SectionType.PEAK)
        score = score_harmonic(a, b, section_context=ctx)
        # Drop→peak is not drum-only → no relax
        assert score < DRUM_ONLY_HARMONIC_FLOOR


# ── TransitionScorer with drum-only override ─────────────────────────


def _compatible_techno_pair() -> tuple[TrackFeatures, TrackFeatures]:
    """A pair that passes hard constraints with rich features."""
    a = TrackFeatures(
        bpm=128.0,
        key_code=0,
        key_confidence=0.7,
        bpm_confidence=0.9,
        bpm_stability=0.9,
        integrated_lufs=-10.0,
        atonality=False,
        hnr_db=-5.0,
        spectral_centroid_hz=2000.0,
        onset_rate=4.0,
        kick_prominence=0.6,
    )
    b = TrackFeatures(
        bpm=129.0,
        key_code=8,  # Camelot dist 4 → harmonic should be quite low
        key_confidence=0.7,
        bpm_confidence=0.9,
        bpm_stability=0.9,
        integrated_lufs=-10.5,
        atonality=False,
        hnr_db=-5.0,
        spectral_centroid_hz=2050.0,
        onset_rate=4.1,
        kick_prominence=0.62,
    )
    return a, b


class TestScorerSectionContext:
    def test_default_score_unchanged_without_context(self) -> None:
        a, b = _compatible_techno_pair()
        scorer = TransitionScorer()

        baseline = scorer.score(a, b)
        with_none = scorer.score(a, b, section_context=None)

        assert baseline.harmonic == with_none.harmonic
        assert baseline.overall == with_none.overall

    def test_drum_only_context_lifts_harmonic(self) -> None:
        a, b = _compatible_techno_pair()
        scorer = TransitionScorer()
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)

        baseline = scorer.score(a, b)
        drum_only = scorer.score(a, b, section_context=ctx)

        assert drum_only.harmonic > baseline.harmonic
        assert drum_only.harmonic >= DRUM_ONLY_HARMONIC_FLOOR

    def test_drum_only_context_uses_override_weights(self) -> None:
        """The weighted sum must use the override (groove boosted,
        harmonic suppressed) and therefore differ from the default
        weighted sum even when component scores match."""
        a, b = _compatible_techno_pair()
        scorer = TransitionScorer()
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)

        baseline = scorer.score(a, b)
        drum_only = scorer.score(a, b, section_context=ctx)

        # Manually compute what the override would produce given the
        # drum-only harmonic and the rest of the components from baseline.
        expected_overall = (
            DRUM_ONLY_WEIGHT_OVERRIDE["bpm"] * baseline.bpm
            + DRUM_ONLY_WEIGHT_OVERRIDE["harmonic"] * drum_only.harmonic
            + DRUM_ONLY_WEIGHT_OVERRIDE["energy"] * baseline.energy
            + DRUM_ONLY_WEIGHT_OVERRIDE["spectral"] * baseline.spectral
            + DRUM_ONLY_WEIGHT_OVERRIDE["groove"] * baseline.groove
            + DRUM_ONLY_WEIGHT_OVERRIDE["timbral"] * baseline.timbral
        )
        assert abs(drum_only.overall - expected_overall) < 1e-9

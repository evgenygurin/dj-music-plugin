"""Tests for P2 TransitionScorer enrichments.

Covers: timbral component, tonnetz harmonic enrichment, dissonance/complexity
spectral penalties, beat_loudness groove enrichment, BPM stability factor,
and backward compatibility with missing P2 features.
"""

from __future__ import annotations

import pytest

from app.entities.audio.features import TrackFeatures
from app.transition.scorer import TransitionScorer


def _base_features(**overrides: object) -> TrackFeatures:
    """Minimal valid features for scoring (no hard reject)."""
    defaults: dict[str, object] = {
        "bpm": 130.0,
        "key_code": 0,
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 2000.0,
        "spectral_flatness": 0.2,
        "energy_mean": 0.5,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": 5.0,
        "chroma_entropy": 3.0,
        "mfcc_vector": [0.1] * 13,
        "energy_bands": [0.1, 0.2, 0.15, 0.15, 0.1, 0.05],
    }
    defaults.update(overrides)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]


# ── Timbral component ───────────────────────────────


class TestTimbralComponent:
    """Tests for the new _score_timbral method."""

    def test_timbral_score_exists(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        result = scorer.score(a, b)
        assert hasattr(result, "timbral")
        assert 0.0 <= result.timbral <= 1.0

    def test_timbral_identical_tracks_high(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        result = scorer.score(a, b)
        assert result.timbral > 0.95

    def test_timbral_similar_tracks_high(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=6.0, pitch_salience_mean=0.35)
        result = scorer.score(a, b)
        assert result.timbral > 0.7

    def test_timbral_very_different_low(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=2.0, pitch_salience_mean=0.1)
        b = _base_features(spectral_contrast=17.0, pitch_salience_mean=0.6)
        result = scorer.score(a, b)
        assert result.timbral < 0.5

    def test_timbral_neutral_when_unavailable(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=None, pitch_salience_mean=None)
        b = _base_features(spectral_contrast=None, pitch_salience_mean=None)
        result = scorer.score(a, b)
        assert result.timbral == pytest.approx(0.5)

    def test_timbral_partial_features(self) -> None:
        """Only spectral contrast, no pitch salience."""
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=None)
        b = _base_features(spectral_contrast=5.0, pitch_salience_mean=None)
        result = scorer.score(a, b)
        assert result.timbral > 0.9  # identical contrast

    def test_timbral_contributes_to_overall(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        result = scorer.score(a, b)
        # timbral has 0.10 weight, should contribute to overall
        assert result.overall > 0.0

    def test_timbral_in_default_weights(self) -> None:
        """Timbral must be in DEFAULT_TRANSITION_WEIGHTS."""
        from app.core.constants import DEFAULT_TRANSITION_WEIGHTS

        assert "timbral" in DEFAULT_TRANSITION_WEIGHTS
        # Rebalanced 0.10 → 0.15 in commit 6 of the transition redesign.
        # See docs/research/2026-04-08-techno-transitions-research.md §4.4
        assert DEFAULT_TRANSITION_WEIGHTS["timbral"] == pytest.approx(0.15)

    def test_weights_sum_to_one(self) -> None:
        """All default weights must sum to 1.0."""
        from app.core.constants import DEFAULT_TRANSITION_WEIGHTS

        assert sum(DEFAULT_TRANSITION_WEIGHTS.values()) == pytest.approx(1.0)


# ── Tonnetz harmonic enrichment ──────────────────────


class TestTonnetzEnrichment:
    """Tests for tonnetz cosine similarity in harmonic scoring."""

    def test_harmonic_with_identical_tonnetz_higher(self) -> None:
        scorer = TransitionScorer()
        vec = [0.1, 0.2, -0.1, 0.0, 0.15, -0.05]
        a = _base_features(tonnetz_vector=vec)
        b = _base_features(tonnetz_vector=vec)
        score_with = scorer.score(a, b)

        a_no = _base_features(tonnetz_vector=None)
        b_no = _base_features(tonnetz_vector=None)
        score_without = scorer.score(a_no, b_no)

        # Identical tonnetz should boost (or at least not hurt) harmonic score
        assert score_with.harmonic >= score_without.harmonic - 0.05

    def test_harmonic_with_opposite_tonnetz_lower(self) -> None:
        scorer = TransitionScorer()
        vec_a = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        vec_b = [-0.5, -0.5, -0.5, -0.5, -0.5, -0.5]
        a = _base_features(tonnetz_vector=vec_a)
        b = _base_features(tonnetz_vector=vec_b)
        score_opposite = scorer.score(a, b)

        a_same = _base_features(tonnetz_vector=vec_a)
        b_same = _base_features(tonnetz_vector=vec_a)
        score_same = scorer.score(a_same, b_same)

        assert score_same.harmonic > score_opposite.harmonic

    def test_harmonic_without_tonnetz_unchanged(self) -> None:
        """Without tonnetz, harmonic scoring should work as before."""
        scorer = TransitionScorer()
        a = _base_features(tonnetz_vector=None)
        b = _base_features(tonnetz_vector=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.harmonic <= 1.0


# ── Dissonance penalty ───────────────────────────────


class TestDissonancePenalty:
    """Tests for dissonance penalty in spectral scoring."""

    def test_both_high_dissonance_penalized(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(dissonance_mean=0.7)
        b = _base_features(dissonance_mean=0.6)
        score_high = scorer.score(a, b)

        a_low = _base_features(dissonance_mean=0.1)
        b_low = _base_features(dissonance_mean=0.1)
        score_low = scorer.score(a_low, b_low)

        assert score_low.spectral >= score_high.spectral

    def test_one_low_dissonance_no_penalty(self) -> None:
        """Penalty only when BOTH tracks are harsh."""
        scorer = TransitionScorer()
        a = _base_features(dissonance_mean=0.7)
        b = _base_features(dissonance_mean=0.2)  # one is low
        score_mixed = scorer.score(a, b)

        a_low = _base_features(dissonance_mean=0.1)
        b_low = _base_features(dissonance_mean=0.1)
        score_low = scorer.score(a_low, b_low)

        # No penalty applied — spectral should be similar
        assert abs(score_mixed.spectral - score_low.spectral) < 0.2

    def test_dissonance_none_no_penalty(self) -> None:
        """Missing dissonance = no penalty."""
        scorer = TransitionScorer()
        a = _base_features(dissonance_mean=None)
        b = _base_features(dissonance_mean=None)
        result = scorer.score(a, b)
        assert result.spectral > 0.0


# ── Spectral complexity penalty ──────────────────────


class TestSpectralComplexityPenalty:
    """Tests for spectral complexity penalty."""

    def test_large_complexity_diff_penalized(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_complexity_mean=5.0)
        b = _base_features(spectral_complexity_mean=20.0)  # diff=15 > 10
        score_diff = scorer.score(a, b)

        a_sim = _base_features(spectral_complexity_mean=5.0)
        b_sim = _base_features(spectral_complexity_mean=6.0)  # diff=1 < 10
        score_sim = scorer.score(a_sim, b_sim)

        assert score_sim.spectral >= score_diff.spectral

    def test_small_complexity_diff_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(spectral_complexity_mean=5.0)
        b = _base_features(spectral_complexity_mean=8.0)  # diff=3 < 10
        score = scorer.score(a, b)
        # No penalty applied — spectral should be decent
        assert score.spectral > 0.0


# ── Beat loudness groove enrichment ──────────────────


class TestBeatLoudnessGroove:
    """Tests for beat_loudness_band_ratio in groove scoring."""

    def test_groove_with_beat_loudness_similar(self) -> None:
        scorer = TransitionScorer()
        ratio = [0.3, 0.5, 0.2]
        a = _base_features(beat_loudness_band_ratio=ratio)
        b = _base_features(beat_loudness_band_ratio=ratio)
        result = scorer.score(a, b)
        assert result.groove > 0.7

    def test_groove_with_beat_loudness_different(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(beat_loudness_band_ratio=[0.9, 0.05, 0.05])
        b = _base_features(beat_loudness_band_ratio=[0.05, 0.05, 0.9])
        result_diff = scorer.score(a, b)

        a_same = _base_features(beat_loudness_band_ratio=[0.3, 0.5, 0.2])
        b_same = _base_features(beat_loudness_band_ratio=[0.3, 0.5, 0.2])
        result_same = scorer.score(a_same, b_same)

        assert result_same.groove > result_diff.groove

    def test_groove_without_beat_loudness(self) -> None:
        """Without beat_loudness, groove uses 50/50 onset/kick."""
        scorer = TransitionScorer()
        a = _base_features(beat_loudness_band_ratio=None)
        b = _base_features(beat_loudness_band_ratio=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.groove <= 1.0


# ── BPM stability factor ────────────────────────────


class TestBpmStabilityFactor:
    """Tests for BPM stability enrichment."""

    def test_unstable_bpm_penalizes(self) -> None:
        scorer = TransitionScorer()
        a_stable = _base_features(bpm_stability=0.95)
        b_stable = _base_features(bpm_stability=0.95, bpm=131.0)
        score_stable = scorer.score(a_stable, b_stable)

        a_unstable = _base_features(bpm_stability=0.4)
        b_unstable = _base_features(bpm_stability=0.4, bpm=131.0)
        score_unstable = scorer.score(a_unstable, b_unstable)

        assert score_stable.bpm > score_unstable.bpm

    def test_stable_bpm_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(bpm_stability=0.99)
        b = _base_features(bpm_stability=0.99)
        result = scorer.score(a, b)
        # Stability near 1.0 should not reduce BPM score significantly
        assert result.bpm > 0.9

    def test_missing_stability_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(bpm_stability=None)
        b = _base_features(bpm_stability=None)
        result = scorer.score(a, b)
        assert result.bpm > 0.9  # identical BPM = high score

    def test_stability_floor_at_07(self) -> None:
        """max(0.7, stability) floors at 0.7 — worst case 30% penalty."""
        scorer = TransitionScorer()
        a = _base_features(bpm_stability=0.1)  # very unstable
        b = _base_features(bpm_stability=0.1)
        result = scorer.score(a, b)
        # identical BPM base score ~1.0, multiplied by 0.7
        assert result.bpm >= 0.65


# ── Backward compatibility ──────────────────────────


class TestBackwardCompatibility:
    """Ensure scores work correctly when P2 features are absent."""

    def test_scores_valid_without_p2_features(self) -> None:
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=132.0, key_code=1, integrated_lufs=-9.0)
        result = scorer.score(a, b)
        assert 0.0 <= result.overall <= 1.0
        assert not result.hard_reject

    def test_all_none_features_neutral(self) -> None:
        scorer = TransitionScorer()
        a = TrackFeatures()  # all None
        b = TrackFeatures()
        result = scorer.score(a, b)
        assert not result.hard_reject
        assert abs(result.overall - 0.5) < 0.15

    def test_hard_reject_still_works(self) -> None:
        scorer = TransitionScorer()
        a = _base_features(bpm=128.0)
        b = _base_features(bpm=145.0)  # diff > 10
        result = scorer.score(a, b)
        assert result.hard_reject is True

    def test_custom_weights_without_timbral(self) -> None:
        """Old-style weights without timbral key should still work."""
        scorer = TransitionScorer(
            weights={
                "bpm": 0.25,
                "harmonic": 0.20,
                "energy": 0.25,
                "spectral": 0.15,
                "groove": 0.15,
            }
        )
        a = _base_features()
        b = _base_features(bpm=131.0)
        result = scorer.score(a, b)
        # timbral defaults to weight=0 via .get("timbral", 0)
        assert 0.0 <= result.overall <= 1.0

    def test_score_with_candidates_still_works(self) -> None:
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=131.0)
        result = scorer.score_with_candidates(
            a, b, candidate_bpm_distance=1.0, candidate_key_distance=0
        )
        assert not result.hard_reject
        assert result.timbral >= 0.0


# ── _compute_score weights parameter ────────────────


class TestComputeScoreWeightsParam:
    """Test that _compute_score accepts optional weights override."""

    def test_override_weights(self) -> None:
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=131.0)

        default_result = scorer._compute_score(a, b)
        custom_result = scorer._compute_score(
            a,
            b,
            weights={
                "bpm": 1.0,
                "harmonic": 0,
                "energy": 0,
                "spectral": 0,
                "groove": 0,
                "timbral": 0,
            },
        )

        # Custom weights put all weight on BPM — should differ from default
        assert default_result.overall != custom_result.overall
        assert custom_result.overall == pytest.approx(custom_result.bpm, abs=0.01)


# ── TransitionIntent ─────────────────────────────────


class TestTransitionIntent:
    """Tests for TransitionIntent enum, weight modifiers, and infer_intent."""

    def test_infer_ramp_up_early_position(self) -> None:
        from app.transition.intent import TransitionIntent, infer_intent

        assert infer_intent(0.1, 0.0) == TransitionIntent.RAMP_UP

    def test_infer_cool_down_late_position(self) -> None:
        from app.transition.intent import TransitionIntent, infer_intent

        assert infer_intent(0.9, 0.0) == TransitionIntent.COOL_DOWN

    def test_infer_ramp_up_energy_delta(self) -> None:
        from app.transition.intent import TransitionIntent, infer_intent

        assert infer_intent(0.5, 3.0) == TransitionIntent.RAMP_UP

    def test_infer_cool_down_energy_delta(self) -> None:
        from app.transition.intent import TransitionIntent, infer_intent

        assert infer_intent(0.5, -3.0) == TransitionIntent.COOL_DOWN

    def test_infer_maintain_default(self) -> None:
        from app.transition.intent import TransitionIntent, infer_intent

        assert infer_intent(0.5, 0.5) == TransitionIntent.MAINTAIN

    def test_all_intents_weights_sum_to_one(self) -> None:
        from app.transition.intent import INTENT_WEIGHT_MODIFIERS

        for intent, weights in INTENT_WEIGHT_MODIFIERS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{intent}: weights sum to {total}"

    def test_scorer_with_intent_produces_valid_score(self) -> None:
        from app.transition.intent import TransitionIntent

        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=132.0, key_code=1)
        for intent in TransitionIntent:
            score = scorer.score(a, b, intent=intent)
            assert 0.0 <= score.overall <= 1.0
            assert not score.hard_reject

    def test_scorer_without_intent_unchanged(self) -> None:
        """score() without intent behaves as before (no regression)."""
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=131.0)
        result = scorer.score(a, b)
        assert 0.0 <= result.overall <= 1.0
        assert not result.hard_reject

    def test_intent_is_keyword_only(self) -> None:
        """intent must be passed as keyword argument."""
        import inspect

        sig = inspect.signature(TransitionScorer.score)
        params = list(sig.parameters)
        # 'intent' should be in parameters and keyword-only
        assert "intent" in params
        assert sig.parameters["intent"].kind == inspect.Parameter.KEYWORD_ONLY

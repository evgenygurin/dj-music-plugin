"""Tests for MoodClassifier.

Covers:
- Classification of each subgenre by ideal profile features
- Catch-all penalty verification (driving, hypnotic)
- Confidence calculation correctness
- Edge cases: empty features, all zeros, extreme values
- Gaussian scoring internals
- Reasoning string format
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.audio.mood import (
    _CATCH_ALL_SUBGENRES,
    SUBGENRE_PROFILES,
    MoodClassifier,
    MoodResult,
)
from app.config import settings
from app.core.constants import TechnoSubgenre

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ideal_features_for(subgenre: TechnoSubgenre) -> dict[str, float]:
    """Build a feature dict with ideal values for a given subgenre profile."""
    profile = SUBGENRE_PROFILES[subgenre]
    return {name: ideal for name, (_weight, ideal, _tol) in profile.items()}


def _make_classifier() -> MoodClassifier:
    return MoodClassifier()


# ---------------------------------------------------------------------------
# Basic contract tests
# ---------------------------------------------------------------------------


class TestMoodClassifierContract:
    """Verify the basic contract of classify() return value."""

    def test_returns_mood_result_type(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5})
        assert isinstance(result, MoodResult)

    def test_mood_is_valid_subgenre(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5})
        assert result.mood in TechnoSubgenre

    def test_confidence_between_0_and_1(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5, "spectral_centroid_hz": 2000.0})
        assert 0.0 <= result.confidence <= 1.0

    def test_all_15_subgenres_scored(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5})
        assert len(result.scores) == 15
        assert set(result.scores.keys()) == set(TechnoSubgenre)

    def test_all_scores_nonnegative(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5, "spectral_centroid_hz": 2000.0})
        for subgenre, score in result.scores.items():
            assert score >= 0.0, f"{subgenre.value} has negative score: {score}"

    def test_reasoning_contains_top_match(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.5})
        assert "Top match:" in result.reasoning
        assert "runner-up:" in result.reasoning

    def test_reasoning_contains_winner_name(self) -> None:
        result = _make_classifier().classify({"energy_mean": 0.85})
        assert result.mood.value in result.reasoning


# ---------------------------------------------------------------------------
# Subgenre profile tests -- each ideal profile should win its own subgenre
# ---------------------------------------------------------------------------


class TestSubgenreIdealProfiles:
    """When features exactly match a subgenre's ideal values, that subgenre
    should be the top scorer (before catch-all penalty) or at least top-3
    (after penalty for driving/hypnotic)."""

    @pytest.mark.parametrize(
        "subgenre",
        list(TechnoSubgenre),
        ids=[s.value for s in TechnoSubgenre],
    )
    def test_each_subgenre_has_profile(self, subgenre: TechnoSubgenre) -> None:
        assert subgenre in SUBGENRE_PROFILES, f"Missing profile for {subgenre.value}"

    # Progressive shares ideal centroid/flux/energy with detroit, causing a tie
    # where sort order determines winner. Tested separately below.
    _OVERLAPPING = {TechnoSubgenre.PROGRESSIVE}

    @pytest.mark.parametrize(
        "subgenre",
        [
            s
            for s in TechnoSubgenre
            if s not in _CATCH_ALL_SUBGENRES and s != TechnoSubgenre.PROGRESSIVE
        ],
        ids=[
            s.value
            for s in TechnoSubgenre
            if s not in _CATCH_ALL_SUBGENRES and s != TechnoSubgenre.PROGRESSIVE
        ],
    )
    def test_ideal_features_win_for_non_catchall(self, subgenre: TechnoSubgenre) -> None:
        """Ideal features for a non-catch-all subgenre should make it the winner."""
        features = _ideal_features_for(subgenre)
        result = _make_classifier().classify(features)
        assert result.mood == subgenre, (
            f"Expected {subgenre.value} but got {result.mood.value}. "
            f"Scores: {subgenre.value}={result.scores[subgenre]:.4f}, "
            f"winner={result.mood.value}={result.scores[result.mood]:.4f}"
        )

    def test_progressive_ideal_scores_max_but_ties_detroit(self) -> None:
        """Progressive and detroit share several ideal values (centroid=2000,
        flux_mean=5.0, energy_mean=0.4), so both score 1.0 with progressive's
        ideal features. We verify progressive scores perfectly at 1.0."""
        features = _ideal_features_for(TechnoSubgenre.PROGRESSIVE)
        classifier = _make_classifier()
        raw = classifier._score_subgenre(TechnoSubgenre.PROGRESSIVE, features)
        assert raw == pytest.approx(1.0, abs=1e-6)
        # And it should be in top-2 at minimum after classify
        result = classifier.classify(features)
        sorted_scores = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
        top_2 = [s[0] for s in sorted_scores[:2]]
        assert TechnoSubgenre.PROGRESSIVE in top_2

    @pytest.mark.parametrize(
        "subgenre",
        list(_CATCH_ALL_SUBGENRES),
        ids=[s.value for s in _CATCH_ALL_SUBGENRES],
    )
    def test_ideal_features_top3_for_catchall(self, subgenre: TechnoSubgenre) -> None:
        """Catch-all subgenres with ideal features should be at least top-3
        (penalty may push them below a close competitor)."""
        features = _ideal_features_for(subgenre)
        result = _make_classifier().classify(features)
        sorted_scores = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = [s[0] for s in sorted_scores[:3]]
        assert subgenre in top_3, (
            f"{subgenre.value} not in top-3 with ideal features. Top-3: {[s.value for s in top_3]}"
        )


# ---------------------------------------------------------------------------
# Catch-all penalty
# ---------------------------------------------------------------------------


class TestCatchAllPenalty:
    """Verify the catch-all penalty reduces scores for driving and hypnotic."""

    def test_penalty_targets_are_driving_and_hypnotic(self) -> None:
        assert {
            TechnoSubgenre.DRIVING,
            TechnoSubgenre.HYPNOTIC,
        } == _CATCH_ALL_SUBGENRES

    def test_penalty_reduces_driving_score(self) -> None:
        """Driving score after penalty should be penalty * raw_score."""
        classifier = _make_classifier()
        features = _ideal_features_for(TechnoSubgenre.DRIVING)

        # Compute raw score manually for driving
        raw_score = classifier._score_subgenre(TechnoSubgenre.DRIVING, features)
        result = classifier.classify(features)
        penalized_score = result.scores[TechnoSubgenre.DRIVING]

        expected = raw_score * settings.mood_catch_all_penalty
        assert penalized_score == pytest.approx(expected, rel=1e-6), (
            f"raw={raw_score:.4f}, penalty={settings.mood_catch_all_penalty}, "
            f"expected={expected:.4f}, got={penalized_score:.4f}"
        )

    def test_penalty_reduces_hypnotic_score(self) -> None:
        classifier = _make_classifier()
        features = _ideal_features_for(TechnoSubgenre.HYPNOTIC)

        raw_score = classifier._score_subgenre(TechnoSubgenre.HYPNOTIC, features)
        result = classifier.classify(features)
        penalized_score = result.scores[TechnoSubgenre.HYPNOTIC]

        expected = raw_score * settings.mood_catch_all_penalty
        assert penalized_score == pytest.approx(expected, rel=1e-6)

    def test_non_catchall_not_penalized(self) -> None:
        """Subgenres outside catch-all set should have raw_score == final score."""
        classifier = _make_classifier()
        subgenre = TechnoSubgenre.HARD_TECHNO
        features = _ideal_features_for(subgenre)

        raw_score = classifier._score_subgenre(subgenre, features)
        result = classifier.classify(features)
        final_score = result.scores[subgenre]

        assert final_score == pytest.approx(raw_score, rel=1e-6)

    def test_custom_penalty_value(self) -> None:
        """Changing mood_catch_all_penalty setting should change the result."""
        classifier = _make_classifier()
        features = _ideal_features_for(TechnoSubgenre.DRIVING)

        with patch.object(settings, "mood_catch_all_penalty", 0.5):
            result = classifier.classify(features)

        raw_score = classifier._score_subgenre(TechnoSubgenre.DRIVING, features)
        assert result.scores[TechnoSubgenre.DRIVING] == pytest.approx(raw_score * 0.5, rel=1e-6)


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------


class TestConfidence:
    """Verify confidence = (winner - second) / winner, clamped to [0, 1]."""

    def test_confidence_formula(self) -> None:
        """Confidence should match (winner - second) / winner."""
        result = _make_classifier().classify(
            {
                "energy_mean": 0.85,
                "spectral_centroid_hz": 3500.0,
                "energy_band_low": 0.3,
                "crest_factor_db": 3.0,
                "loudness_range_lu": 3.0,
                "spectral_flux_mean": 12.0,
            }
        )
        sorted_scores = sorted(result.scores.values(), reverse=True)
        winner_score = sorted_scores[0]
        second_score = sorted_scores[1]
        expected = (winner_score - second_score) / (winner_score + 1e-10)
        assert result.confidence == pytest.approx(expected, abs=1e-6)

    def test_identical_top_scores_give_low_confidence(self) -> None:
        """When top two scores are very close, confidence should be near zero."""
        # Features that score similarly across multiple subgenres
        features = {
            "energy_mean": 0.45,
            "spectral_centroid_hz": 2000.0,
        }
        result = _make_classifier().classify(features)
        # With only 2 generic features, many subgenres score similarly
        # confidence should be relatively low
        assert result.confidence < 0.5

    def test_dominant_profile_gives_high_confidence(self) -> None:
        """Perfect match with a distinctive profile should give high confidence."""
        # ambient_dub is very distinctive: low energy, low centroid, high LRA
        features = _ideal_features_for(TechnoSubgenre.AMBIENT_DUB)
        result = _make_classifier().classify(features)
        assert result.confidence > 0.1  # at least some separation

    def test_confidence_never_negative(self) -> None:
        result = _make_classifier().classify({})
        assert result.confidence >= 0.0

    def test_confidence_never_above_1(self) -> None:
        result = _make_classifier().classify(_ideal_features_for(TechnoSubgenre.HARD_TECHNO))
        assert result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Gaussian scoring internals
# ---------------------------------------------------------------------------


class TestGaussianScoring:
    """Test the _score_subgenre Gaussian similarity logic."""

    def test_ideal_value_gives_max_similarity(self) -> None:
        """When feature equals ideal, similarity = 1.0 (Gaussian peak)."""
        classifier = _make_classifier()
        subgenre = TechnoSubgenre.HARD_TECHNO
        features = _ideal_features_for(subgenre)
        score = classifier._score_subgenre(subgenre, features)
        # All features at ideal -> each similarity = 1.0 -> score = 1.0
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_far_from_ideal_gives_low_score(self) -> None:
        """Features very far from ideal should give near-zero score."""
        classifier = _make_classifier()
        # Hard techno ideal: energy_mean=0.85, but we give 0.01
        features = {
            "energy_mean": 0.01,
            "spectral_centroid_hz": 100.0,
            "energy_band_low": 0.001,
            "crest_factor_db": 30.0,
            "loudness_range_lu": 25.0,
            "spectral_flux_mean": 0.1,
        }
        score = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features)
        assert score < 0.1

    def test_missing_features_ignored(self) -> None:
        """Features not in the dict should be skipped, not cause error."""
        classifier = _make_classifier()
        # Only provide one of many features for hard_techno
        features = {"energy_mean": 0.85}
        score = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features)
        # Should still compute a score from the one matching feature
        assert score > 0.0

    def test_score_symmetry_around_ideal(self) -> None:
        """Same distance above and below ideal should give same score."""
        classifier = _make_classifier()
        profile = SUBGENRE_PROFILES[TechnoSubgenre.HARD_TECHNO]
        _weight, ideal, tolerance = profile["energy_mean"]

        offset = tolerance * 0.5  # half-tolerance offset
        features_above = {"energy_mean": ideal + offset}
        features_below = {"energy_mean": ideal - offset}

        score_above = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features_above)
        score_below = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features_below)
        # Gaussian is symmetric, but we have other features missing.
        # The score from energy_mean alone should be the same.
        assert score_above == pytest.approx(score_below, abs=1e-6)

    def test_score_decreases_with_distance(self) -> None:
        """Score should decrease as feature moves away from ideal."""
        classifier = _make_classifier()
        profile = SUBGENRE_PROFILES[TechnoSubgenre.HARD_TECHNO]
        _weight, ideal, _tolerance = profile["energy_mean"]

        scores = []
        for offset in [0.0, 0.1, 0.2, 0.5]:
            features = {"energy_mean": ideal + offset}
            s = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features)
            scores.append(s)

        # Each successive score should be <= previous
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i - 1] + 1e-9, (
                f"Score did not decrease: offsets gave scores {scores}"
            )

    def test_no_profile_returns_zero(self) -> None:
        """A subgenre with empty profile (hypothetical) returns 0."""
        classifier = _make_classifier()
        # Temporarily patch an empty profile
        with patch.dict(SUBGENRE_PROFILES, {TechnoSubgenre.HARD_TECHNO: {}}):
            score = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, {"energy_mean": 0.85})
        assert score == 0.0

    def test_zero_weight_total_returns_zero(self) -> None:
        """If all features are missing from input, total_weight=0, score=0."""
        classifier = _make_classifier()
        # Provide features that don't match any hard_techno profile keys
        features = {"nonexistent_feature": 999.0}
        score = classifier._score_subgenre(TechnoSubgenre.HARD_TECHNO, features)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_features_dict(self) -> None:
        """Empty features should produce a valid result with all scores = 0."""
        result = _make_classifier().classify({})
        assert isinstance(result, MoodResult)
        assert result.mood in TechnoSubgenre
        for score in result.scores.values():
            assert score == 0.0

    def test_all_features_zero(self) -> None:
        """All audio features set to zero."""
        features = {
            "energy_mean": 0.0,
            "spectral_centroid_hz": 0.0,
            "spectral_flatness": 0.0,
            "spectral_flux_mean": 0.0,
            "spectral_flux_std": 0.0,
            "loudness_range_lu": 0.0,
            "crest_factor_db": 0.0,
            "energy_std": 0.0,
            "energy_slope": 0.0,
            "energy_band_low": 0.0,
            "energy_band_sub": 0.0,
            "energy_band_mid": 0.0,
            "energy_band_high_mid": 0.0,
            "energy_band_high": 0.0,
            "spectral_rolloff_85": 0.0,
        }
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)
        assert result.mood in TechnoSubgenre
        assert 0.0 <= result.confidence <= 1.0

    def test_extreme_high_values(self) -> None:
        """Extremely high feature values should not crash."""
        features = {
            "energy_mean": 100.0,
            "spectral_centroid_hz": 100000.0,
            "spectral_flatness": 100.0,
            "spectral_flux_mean": 10000.0,
            "spectral_flux_std": 10000.0,
            "loudness_range_lu": 1000.0,
            "crest_factor_db": 1000.0,
        }
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)
        assert result.mood in TechnoSubgenre
        # All scores should be very low (far from any ideal)
        for score in result.scores.values():
            assert score < 0.5

    def test_negative_feature_values(self) -> None:
        """Negative values (e.g., negative energy) should not crash."""
        features = {
            "energy_mean": -1.0,
            "spectral_centroid_hz": -500.0,
        }
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)
        assert 0.0 <= result.confidence <= 1.0

    def test_nan_feature_value(self) -> None:
        """NaN feature value should not crash the classifier."""
        features = {
            "energy_mean": float("nan"),
            "spectral_centroid_hz": 2000.0,
        }
        # NaN in Gaussian: exp(-nan) = nan, nan * weight = nan
        # The classifier should still return a result (potentially degraded)
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)

    def test_inf_feature_value(self) -> None:
        """Infinity feature value should not crash."""
        features = {
            "energy_mean": float("inf"),
            "spectral_centroid_hz": 2000.0,
        }
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)

    def test_extra_unknown_features_ignored(self) -> None:
        """Features not in any profile should be silently ignored."""
        features = {
            "unknown_feature_xyz": 42.0,
            "another_unknown": -99.0,
            "energy_mean": 0.85,
        }
        result = _make_classifier().classify(features)
        assert isinstance(result, MoodResult)
        # Should still produce meaningful scores from energy_mean
        hard_techno_score = result.scores[TechnoSubgenre.HARD_TECHNO]
        assert hard_techno_score > 0.0

    def test_single_feature_still_classifies(self) -> None:
        """A single feature should be enough to produce a valid classification."""
        result = _make_classifier().classify({"energy_mean": 0.1})
        assert isinstance(result, MoodResult)
        assert len(result.scores) == 15


# ---------------------------------------------------------------------------
# Specific subgenre discrimination tests
# ---------------------------------------------------------------------------


class TestSubgenreDiscrimination:
    """Test that key features correctly discriminate between subgenres."""

    def test_high_energy_separates_hard_from_ambient(self) -> None:
        """High energy_mean should favor hard_techno over ambient_dub."""
        result = _make_classifier().classify(_ideal_features_for(TechnoSubgenre.HARD_TECHNO))
        assert (
            result.scores[TechnoSubgenre.HARD_TECHNO] > result.scores[TechnoSubgenre.AMBIENT_DUB]
        )

    def test_low_energy_separates_ambient_from_hard(self) -> None:
        """Low energy_mean should favor ambient_dub over hard_techno."""
        result = _make_classifier().classify(_ideal_features_for(TechnoSubgenre.AMBIENT_DUB))
        assert (
            result.scores[TechnoSubgenre.AMBIENT_DUB] > result.scores[TechnoSubgenre.HARD_TECHNO]
        )

    def test_high_centroid_favors_acid(self) -> None:
        """Very high spectral centroid is characteristic of acid."""
        features = _ideal_features_for(TechnoSubgenre.ACID)
        result = _make_classifier().classify(features)
        # Acid should score higher than minimal (low centroid)
        assert result.scores[TechnoSubgenre.ACID] > result.scores[TechnoSubgenre.MINIMAL]

    def test_high_flux_std_favors_breakbeat(self) -> None:
        """High spectral_flux_std (varied dynamics) is characteristic of breakbeat."""
        features = _ideal_features_for(TechnoSubgenre.BREAKBEAT)
        result = _make_classifier().classify(features)
        # Breakbeat should score higher than hypnotic (low flux std)
        assert result.scores[TechnoSubgenre.BREAKBEAT] > result.scores[TechnoSubgenre.HYPNOTIC]

    def test_low_flux_std_favors_hypnotic(self) -> None:
        """Low spectral_flux_std (repetitive) is characteristic of hypnotic."""
        features = _ideal_features_for(TechnoSubgenre.HYPNOTIC)
        _make_classifier().classify(features)
        # Compare raw scores before penalty
        classifier = _make_classifier()
        raw_hypnotic = classifier._score_subgenre(TechnoSubgenre.HYPNOTIC, features)
        raw_breakbeat = classifier._score_subgenre(TechnoSubgenre.BREAKBEAT, features)
        assert raw_hypnotic > raw_breakbeat

    def test_high_energy_slope_favors_progressive(self) -> None:
        """Progressive has high weight on energy_slope."""
        features = _ideal_features_for(TechnoSubgenre.PROGRESSIVE)
        classifier = _make_classifier()
        score = classifier._score_subgenre(TechnoSubgenre.PROGRESSIVE, features)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_wide_loudness_range_favors_dub_techno(self) -> None:
        """Dub techno has high weight on loudness_range_lu."""
        features = _ideal_features_for(TechnoSubgenre.DUB_TECHNO)
        classifier = _make_classifier()
        score = classifier._score_subgenre(TechnoSubgenre.DUB_TECHNO, features)
        assert score == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Profile completeness and weight sanity
# ---------------------------------------------------------------------------


class TestProfileSanity:
    """Verify that profiles are well-formed and consistent."""

    @pytest.mark.parametrize(
        "subgenre",
        list(TechnoSubgenre),
        ids=[s.value for s in TechnoSubgenre],
    )
    def test_profile_has_at_least_4_features(self, subgenre: TechnoSubgenre) -> None:
        """Each profile should have at least 4 features for discrimination."""
        profile = SUBGENRE_PROFILES[subgenre]
        assert len(profile) >= 4, f"{subgenre.value} has only {len(profile)} features in profile"

    @pytest.mark.parametrize(
        "subgenre",
        list(TechnoSubgenre),
        ids=[s.value for s in TechnoSubgenre],
    )
    def test_all_weights_positive(self, subgenre: TechnoSubgenre) -> None:
        """All weights in profiles must be positive."""
        profile = SUBGENRE_PROFILES[subgenre]
        for feature_name, (weight, _ideal, _tol) in profile.items():
            assert weight > 0, f"{subgenre.value}.{feature_name}: weight={weight} must be > 0"

    @pytest.mark.parametrize(
        "subgenre",
        list(TechnoSubgenre),
        ids=[s.value for s in TechnoSubgenre],
    )
    def test_all_tolerances_positive(self, subgenre: TechnoSubgenre) -> None:
        """All tolerances must be positive (prevents division by zero)."""
        profile = SUBGENRE_PROFILES[subgenre]
        for feature_name, (_weight, _ideal, tolerance) in profile.items():
            assert tolerance > 0, (
                f"{subgenre.value}.{feature_name}: tolerance={tolerance} must be > 0"
            )

    def test_catch_all_penalty_setting_between_0_and_1(self) -> None:
        """The catch-all penalty should be in (0, 1) range."""
        assert 0.0 < settings.mood_catch_all_penalty < 1.0


# ---------------------------------------------------------------------------
# Classifier is stateless
# ---------------------------------------------------------------------------


class TestClassifierStateless:
    """Verify classifier does not accumulate state between calls."""

    def test_repeated_calls_same_result(self) -> None:
        classifier = _make_classifier()
        features = _ideal_features_for(TechnoSubgenre.MINIMAL)
        result1 = classifier.classify(features)
        result2 = classifier.classify(features)
        assert result1.mood == result2.mood
        assert result1.confidence == pytest.approx(result2.confidence)
        for subgenre in TechnoSubgenre:
            assert result1.scores[subgenre] == pytest.approx(result2.scores[subgenre], abs=1e-10)

    def test_different_features_different_results(self) -> None:
        classifier = _make_classifier()
        ambient = _ideal_features_for(TechnoSubgenre.AMBIENT_DUB)
        hard = _ideal_features_for(TechnoSubgenre.HARD_TECHNO)
        r1 = classifier.classify(ambient)
        r2 = classifier.classify(hard)
        assert r1.mood != r2.mood

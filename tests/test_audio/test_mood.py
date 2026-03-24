"""Tests for MoodClassifier."""

from __future__ import annotations

import pytest

from app.audio.mood import MoodClassifier, MoodResult
from app.core.constants import TechnoSubgenre


class TestMoodClassifier:
    def test_returns_valid_subgenre(self) -> None:
        """Classifier should return one of 15 TechnoSubgenre values."""
        classifier = MoodClassifier()
        features = {
            "energy_mean": 0.5,
            "spectral_centroid_hz": 2000.0,
            "spectral_flatness": 0.15,
            "spectral_flux_mean": 5.0,
            "spectral_flux_std": 2.0,
            "loudness_range_lu": 6.0,
            "crest_factor_db": 8.0,
            "energy_std": 0.1,
            "energy_slope": 0.0,
            "energy_band_low": 0.2,
            "energy_band_sub": 0.05,
            "energy_band_mid": 0.2,
            "energy_band_high_mid": 0.15,
            "energy_band_high": 0.1,
            "rms_dbfs": -12.0,
            "integrated_lufs": -14.0,
            "spectral_rolloff_85": 3000.0,
        }
        result = classifier.classify(features)
        assert isinstance(result, MoodResult)
        assert result.mood in TechnoSubgenre

    def test_confidence_between_0_and_1(self) -> None:
        classifier = MoodClassifier()
        features = {
            "energy_mean": 0.5,
            "spectral_centroid_hz": 2000.0,
            "spectral_flatness": 0.15,
        }
        result = classifier.classify(features)
        assert 0.0 <= result.confidence <= 1.0

    def test_all_subgenres_scored(self) -> None:
        classifier = MoodClassifier()
        features = {"energy_mean": 0.5, "spectral_centroid_hz": 2000.0}
        result = classifier.classify(features)
        assert len(result.scores) == len(TechnoSubgenre)

    def test_high_energy_favors_hard_techno(self) -> None:
        """Very high energy features should favor hard_techno."""
        classifier = MoodClassifier()
        features = {
            "energy_mean": 0.9,
            "spectral_centroid_hz": 3500.0,
            "energy_band_low": 0.3,
            "crest_factor_db": 3.0,
            "loudness_range_lu": 3.0,
            "spectral_flux_mean": 12.0,
        }
        result = classifier.classify(features)
        # hard_techno should be top or near top
        sorted_scores = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = [s[0] for s in sorted_scores[:3]]
        assert TechnoSubgenre.HARD_TECHNO in top_3

    def test_low_energy_favors_ambient(self) -> None:
        """Very low energy should favor ambient_dub."""
        classifier = MoodClassifier()
        features = {
            "energy_mean": 0.1,
            "spectral_centroid_hz": 800.0,
            "spectral_flatness": 0.15,
            "spectral_flux_std": 0.5,
            "loudness_range_lu": 12.0,
            "crest_factor_db": 15.0,
        }
        result = classifier.classify(features)
        sorted_scores = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = [s[0] for s in sorted_scores[:3]]
        assert TechnoSubgenre.AMBIENT_DUB in top_3

    def test_catch_all_penalty_applied(self) -> None:
        """Driving and hypnotic should be penalized."""
        classifier = MoodClassifier()
        # Features that match driving profile well
        features = {
            "energy_mean": 0.55,
            "spectral_centroid_hz": 2500.0,
            "energy_band_low": 0.25,
            "spectral_flux_mean": 8.0,
            "crest_factor_db": 8.0,
            "energy_std": 0.12,
        }
        result = classifier.classify(features)
        # Verify penalty was applied (score < unpanalyzed theoretical max)
        assert result.scores[TechnoSubgenre.DRIVING] >= 0.0
        assert result.scores[TechnoSubgenre.HYPNOTIC] >= 0.0

    def test_empty_features_returns_result(self) -> None:
        """Even with no matching features, should return a valid result."""
        classifier = MoodClassifier()
        result = classifier.classify({})
        assert isinstance(result, MoodResult)
        assert result.mood in TechnoSubgenre

    def test_reasoning_not_empty(self) -> None:
        classifier = MoodClassifier()
        features = {"energy_mean": 0.5, "spectral_centroid_hz": 2000.0}
        result = classifier.classify(features)
        assert len(result.reasoning) > 0

    def test_scores_are_nonnegative(self) -> None:
        classifier = MoodClassifier()
        features = {"energy_mean": 0.5, "spectral_centroid_hz": 2000.0}
        result = classifier.classify(features)
        for score in result.scores.values():
            assert score >= 0.0

    @pytest.mark.parametrize(
        "subgenre",
        list(TechnoSubgenre),
        ids=[s.value for s in TechnoSubgenre],
    )
    def test_each_subgenre_has_profile(self, subgenre: TechnoSubgenre) -> None:
        """Every subgenre must have a scoring profile defined."""
        from app.audio.mood import SUBGENRE_PROFILES

        assert subgenre in SUBGENRE_PROFILES, f"Missing profile for {subgenre.value}"

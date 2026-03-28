"""Tests for classification module — profiles + classifier."""

from __future__ import annotations

import pytest

from app.audio.classification import MoodClassifier, MoodResult
from app.audio.classification.profiles import ALL_PROFILES, FeatureTarget
from app.core.constants import TechnoSubgenre


class TestSubgenreProfile:
    def test_frozen(self) -> None:
        profile = ALL_PROFILES[0]
        with pytest.raises(AttributeError):
            profile.subgenre = TechnoSubgenre.ACID  # type: ignore[misc]

    def test_all_15_profiles(self) -> None:
        assert len(ALL_PROFILES) == 15

    def test_all_subgenres_covered(self) -> None:
        covered = {p.subgenre for p in ALL_PROFILES}
        assert covered == set(TechnoSubgenre)

    def test_feature_target_frozen(self) -> None:
        ft = FeatureTarget(weight=1.0, ideal=0.5, tolerance=0.1)
        with pytest.raises(AttributeError):
            ft.weight = 2.0  # type: ignore[misc]


class TestMoodResultTopMatches:
    def test_top_matches_present(self) -> None:
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        assert hasattr(result, "top_matches")
        assert len(result.top_matches) == 3

    def test_top_matches_ordered(self) -> None:
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        scores = [score for _, score in result.top_matches]
        assert scores == sorted(scores, reverse=True)


class TestMoodClassifierWithProfiles:
    def test_injected_profiles(self) -> None:
        """Classifier with subset of profiles should work."""
        subset = ALL_PROFILES[:3]
        classifier = MoodClassifier(profiles=subset)
        result = classifier.classify({"energy_mean": 0.5})
        assert isinstance(result, MoodResult)

    def test_backward_compat_default(self) -> None:
        """Default classifier uses all 15 profiles."""
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        assert len(result.scores) == 15


def test_all_profiles_include_p2_features() -> None:
    """All 15 profiles should include at least danceability and dissonance targets."""
    from app.audio.classification.profiles import ALL_PROFILES

    for profile in ALL_PROFILES:
        assert "danceability" in profile.features, f"{profile.subgenre} missing danceability"
        assert "dissonance_mean" in profile.features, f"{profile.subgenre} missing dissonance_mean"

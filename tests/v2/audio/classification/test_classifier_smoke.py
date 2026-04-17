"""Smoke tests for v2 mood classifier (Task 12 port parity)."""

from __future__ import annotations

from app.v2.audio.classification import (
    ALL_PROFILES,
    MoodClassifier,
    MoodResult,
    SubgenreProfile,
)
from app.v2.shared.constants import TechnoSubgenre


def test_profiles_cover_15_subgenres() -> None:
    assert len(ALL_PROFILES) == 15
    covered = {p.subgenre for p in ALL_PROFILES}
    assert covered == set(TechnoSubgenre)


def test_classifier_returns_valid_subgenre() -> None:
    clf = MoodClassifier()
    # Energetic hard-techno-ish features
    features = {
        "bpm": 145.0,
        "energy_lufs": -8.0,
        "energy_mean": 0.8,
        "spectral_centroid_hz": 3500.0,
        "spectral_flatness": 0.2,
        "hp_ratio": 0.5,
        "kick_prominence": 0.4,
        "loudness_range_lu": 4.0,
        "spectral_flux_std": 0.3,
        "onset_rate": 4.0,
    }
    result = clf.classify(features)
    assert isinstance(result, MoodResult)
    assert result.mood in set(TechnoSubgenre)
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.scores) == 15
    assert len(result.top_matches) == 3
    assert result.reasoning


def test_classifier_ambient_features() -> None:
    clf = MoodClassifier()
    features = {
        "bpm": 122.0,
        "energy_lufs": -18.0,
        "energy_mean": 0.1,
        "spectral_centroid_hz": 1200.0,
        "spectral_flatness": 0.1,
        "hp_ratio": 6.0,  # very harmonic
        "kick_prominence": 0.05,
        "loudness_range_lu": 15.0,
    }
    result = clf.classify(features)
    # ambient-ish should score higher than peak_time-ish
    assert result.scores[TechnoSubgenre.AMBIENT_DUB] > result.scores[TechnoSubgenre.PEAK_TIME]


def test_custom_profile_injection() -> None:
    profiles: list[SubgenreProfile] = list(ALL_PROFILES)
    clf = MoodClassifier(profiles=profiles[:5])
    res = clf.classify({"bpm": 130.0, "energy_lufs": -10.0})
    assert len(res.scores) == 5

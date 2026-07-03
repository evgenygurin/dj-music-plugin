"""Canonical Beatport metadata mapping."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.beatport.canonical import (
    beatport_key_code,
    canonical_mood,
    canonical_mood_result,
    canonical_updates,
    stored_genre_updates,
)


@pytest.mark.parametrize(
    ("camelot", "expected"),
    [("1A", 0), ("5A", 8), ("8B", 15), ("12B", 23), ("bad", None), (None, None)],
)
def test_beatport_key_code(camelot: str | None, expected: int | None) -> None:
    assert beatport_key_code(camelot) == expected


def test_peak_time_family_uses_audio_classifier_only_as_tie_breaker() -> None:
    assert (
        canonical_mood(
            genre="Techno (Peak Time / Driving)",
            sub_genre=None,
            bpm=136,
            energy_mean=0.7,
            audio_mood="industrial",
        )
        == "industrial"
    )
    assert (
        canonical_mood(
            genre="Techno (Peak Time / Driving)",
            sub_genre=None,
            bpm=136,
            energy_mean=0.7,
            audio_mood="acid",
        )
        == "peak_time"
    )


def test_raw_hypnotic_family_never_keeps_unrelated_audio_mood() -> None:
    assert (
        canonical_mood(
            genre="Techno (Raw / Deep / Hypnotic)",
            sub_genre=None,
            bpm=132,
            energy_mean=0.5,
            audio_mood="peak_time",
        )
        == "hypnotic"
    )


@pytest.mark.parametrize(
    ("sub_genre", "expected"),
    [
        ("Peak Time", "peak_time"),
        ("Driving", "driving"),
        ("Melodic Techno", "melodic_deep"),
        ("Deep Tech", "minimal"),
        ("Psy-Techno", "driving"),
        ("Neo Rave", "hard_techno"),
        ("Deep / Hypnotic", "hypnotic"),
    ],
)
def test_live_beatport_subgenres_are_mapped(sub_genre: str, expected: str) -> None:
    assert (
        canonical_mood(
            genre="Other",
            sub_genre=sub_genre,
            bpm=135,
            energy_mean=0.6,
            audio_mood=None,
        )
        == expected
    )


def test_mapping_confidence_distinguishes_exact_and_derived() -> None:
    exact = canonical_mood_result(
        genre="Techno (Peak Time / Driving)",
        sub_genre="Peak Time",
        bpm=136,
        energy_mean=0.6,
        audio_mood=None,
    )
    derived = canonical_mood_result(
        genre="Techno (Peak Time / Driving)",
        sub_genre=None,
        bpm=136,
        energy_mean=0.6,
        audio_mood="acid",
    )
    assert exact is not None and exact.confidence == 1.0
    assert derived is not None and derived.confidence == 0.65


def test_high_confidence_replaces_canonical_values_and_preserves_audio() -> None:
    current = SimpleNamespace(
        bpm=135.4,
        bpm_confidence=0.71,
        key_code=14,
        key_confidence=0.62,
        mood="acid",
        mood_confidence=0.42,
        audio_bpm=None,
        audio_bpm_confidence=None,
        audio_key_code=None,
        audio_key_confidence=None,
        audio_mood=None,
        audio_mood_confidence=None,
        energy_mean=0.7,
    )
    match = {
        "matched": True,
        "confidence": "high",
        "beatport_id": 42,
        "genre": "Techno (Peak Time / Driving)",
        "sub_genre": None,
        "bpm": 136,
        "key": "C Minor",
        "camelot": "5A",
        "length_ms": 360000,
        "isrc": "GB-ABC-12-12345",
        "release": "Release",
        "label": "Label",
    }

    values = canonical_updates(match, current=current)

    assert values["audio_bpm"] == 135.4
    assert values["audio_bpm_confidence"] == 0.71
    assert values["audio_key_code"] == 14
    assert values["audio_key_confidence"] == 0.62
    assert values["audio_mood"] == "acid"
    assert values["bpm"] == 136.0
    assert values["bpm_confidence"] == 1.0
    assert values["key_code"] == 8
    assert values["key_confidence"] == 1.0
    assert values["mood"] == "peak_time"
    assert values["mood_confidence"] == 0.65
    assert values["bpm_source"] == "beatport"
    assert values["key_source"] == "beatport"
    assert values["mood_source"] == "beatport"
    assert values["beatport_isrc"] == "GB-ABC-12-12345"


def test_high_confidence_keeps_audio_bpm_when_beatport_tempo_disagrees() -> None:
    current = SimpleNamespace(
        bpm=128.45,
        bpm_confidence=0.91,
        key_code=1,
        key_confidence=0.72,
        mood="detroit",
        mood_confidence=0.4,
        audio_bpm=None,
        audio_bpm_confidence=None,
        audio_key_code=None,
        audio_key_confidence=None,
        audio_mood=None,
        audio_mood_confidence=None,
        energy_mean=0.5,
    )

    values = canonical_updates(
        {
            "matched": True,
            "confidence": "high",
            "beatport_id": 5934029,
            "genre": "Techno (Peak Time / Driving)",
            "bpm": 161,
            "key": "A Minor",
            "camelot": "8A",
            "isrc": "DER721400026",
        },
        current=current,
    )

    assert values["beatport_bpm"] == 161
    assert "bpm" not in values
    assert "bpm_confidence" not in values
    assert "bpm_source" not in values
    assert values["key_code"] == 14
    assert values["key_source"] == "beatport"


def test_medium_confidence_persists_metadata_without_replacing_canonical() -> None:
    current = SimpleNamespace(
        bpm=128.4,
        bpm_confidence=0.71,
        key_code=14,
        key_confidence=0.62,
        mood="acid",
        mood_confidence=0.42,
        audio_bpm=None,
        audio_bpm_confidence=None,
        audio_key_code=None,
        audio_key_confidence=None,
        audio_mood=None,
        audio_mood_confidence=None,
    )
    values = canonical_updates(
        {
            "matched": True,
            "confidence": "medium",
            "beatport_id": 42,
            "genre": "Hard Techno",
            "bpm": 150,
            "camelot": "5A",
        },
        current=current,
    )

    assert values["beatport_bpm"] == 150
    assert "bpm" not in values
    assert "key_code" not in values
    assert "mood" not in values


def test_stored_genre_updates_promotes_verified_genre() -> None:
    values = stored_genre_updates(
        SimpleNamespace(
            bpm=136.0,
            beatport_bpm=None,
            energy_mean=0.7,
            mood="acid",
            mood_confidence=0.3,
            mood_source="audio",
            audio_mood=None,
            audio_mood_confidence=None,
            beatport_genre="Techno (Peak Time / Driving)",
            beatport_sub_genre="Peak Time",
            beatport_confidence="high",
        )
    )
    assert values == {
        "audio_mood": "acid",
        "audio_mood_confidence": 0.3,
        "mood": "peak_time",
        "mood_confidence": 1.0,
        "mood_source": "beatport",
    }

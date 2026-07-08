"""Audit iter 40 (T-38): ``TrackFeaturesView`` exposed 11 of the 47+
columns persisted on ``track_audio_features_computed``. Callers
could not project P1/P2 enrichment fields (``danceability``,
``dissonance_mean``, ``tonnetz_vector``,
``spectral_complexity_mean``, …) nor any of the loudness / spectral
/ energy-band columns through ``entity_get(track_features, id,
fields=[...])``. Live confirmation:

    entity_get(track_features, 146, fields=["danceability"])
    -> "unknown field name(s) in fields: ['danceability']"

The pipeline writes them, the scorer reads them, but tooling was
blind. This is the same drift class as v1.2.36/T-37 but on a
much larger surface.

Now ~45 fields are projectable. Heavy vectors stay as JSON strings
(``mfcc_vector``, ``tonnetz_vector``,
``tempogram_ratio_vector``, ``beat_loudness_band_ratio``,
``phrase_boundaries_ms``).

Filter side: 12 new lookup classes for the canonical
"clipping audit" / "low-confidence key" / "atonal track" /
"variable-tempo flag" queries.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_features import TrackFeaturesFilter, TrackFeaturesView


class TestTrackFeaturesViewExposesP1P2Enrichment:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("danceability", 0.8),
            ("dynamic_complexity", 4.5),
            ("dissonance_mean", 0.3),
            ("spectral_complexity_mean", 12.5),
            ("pitch_salience_mean", 0.4),
            ("bpm_histogram_first_peak_weight", 0.7),
            ("bpm_histogram_second_peak_bpm", 64.0),
            ("bpm_histogram_second_peak_weight", 0.2),
            ("dominant_phrase_bars", 16),
            ("first_downbeat_ms", 250.0),
        ],
    )
    def test_scalar_fields_round_trip(self, field: str, value: float | int) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, field: value})
        assert getattr(view, field) == value

    @pytest.mark.parametrize(
        "field,value",
        [
            ("tonnetz_vector", "[1.0, 2.0, 3.0]"),
            ("tempogram_ratio_vector", "[0.5, 1.0, 0.3]"),
            ("beat_loudness_band_ratio", "[0.1, 0.2, 0.3, 0.4]"),
            ("phrase_boundaries_ms", "[0, 32000, 64000]"),
            ("mfcc_vector", "[" + ", ".join(["0.1"] * 13) + "]"),
        ],
    )
    def test_json_vector_fields_kept_as_strings(self, field: str, value: str) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, field: value})
        # Heavy vectors stay strings — caller does ``json.loads`` if they want.
        assert getattr(view, field) == value
        assert isinstance(getattr(view, field), str)


class TestTrackFeaturesViewExposesLoudness:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("short_term_lufs_mean", -10.5),
            ("momentary_max", -3.0),
            ("rms_dbfs", -12.0),
            ("true_peak_db", -0.3),
            ("crest_factor_db", 8.5),
            ("loudness_range_lu", 6.0),
        ],
    )
    def test_loudness_fields_round_trip(self, field: str, value: float) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, field: value})
        assert getattr(view, field) == value


class TestTrackFeaturesViewExposesEnergyBands:
    @pytest.mark.parametrize(
        "field",
        [
            "energy_max",
            "energy_std",
            "energy_slope",
            "energy_sub",
            "energy_low",
            "energy_lowmid",
            "energy_mid",
            "energy_highmid",
            "energy_high",
            "energy_sub_ratio",
            "energy_low_ratio",
            "energy_lowmid_ratio",
            "energy_mid_ratio",
            "energy_highmid_ratio",
            "energy_high_ratio",
        ],
    )
    def test_energy_field_round_trips(self, field: str) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, field: 0.42})
        assert getattr(view, field) == 0.42


class TestTrackFeaturesViewExposesSpectralAndKey:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("spectral_rolloff_85", 4500.0),
            ("spectral_rolloff_95", 8000.0),
            ("spectral_flatness", 0.05),
            ("spectral_flux_mean", 0.3),
            ("spectral_flux_std", 0.1),
            ("spectral_slope", -0.5),
            ("spectral_contrast", 12.0),
            ("key_confidence", 0.85),
            ("hnr_db", 9.0),
            ("chroma_entropy", 0.7),
        ],
    )
    def test_field_round_trips(self, field: str, value: float) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, field: value})
        assert getattr(view, field) == value

    def test_atonality_round_trips(self) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, "atonality": True})
        assert view.atonality is True

    def test_camelot_computed_from_key_code(self) -> None:
        view = TrackFeaturesView.model_validate({"track_id": 1, "key_code": 8})
        assert view.camelot == "5A"

    def test_beatport_camelot_wins_when_present(self) -> None:
        view = TrackFeaturesView.model_validate(
            {"track_id": 1, "key_code": 8, "beatport_camelot": "6A"}
        )
        assert view.camelot == "6A"


class TestTrackFeaturesFilterNewLookups:
    @pytest.mark.parametrize(
        "key,value",
        [
            ("true_peak_db__gte", -1.0),
            ("true_peak_db__lte", 0.0),
            ("key_confidence__gte", 0.7),
            ("danceability__gte", 0.5),
            ("dissonance_mean__lte", 0.3),
            ("bpm_confidence__gte", 0.5),
            ("bpm_stability__gte", 0.8),
            ("onset_rate__gte", 1.5),
            ("pulse_clarity__gte", 0.4),
        ],
    )
    def test_scalar_lookup(self, key: str, value: float) -> None:
        TrackFeaturesFilter.model_validate({key: value})

    def test_atonality_eq(self) -> None:
        TrackFeaturesFilter.model_validate({"atonality__eq": True})

    def test_variable_tempo_eq(self) -> None:
        TrackFeaturesFilter.model_validate({"variable_tempo__eq": False})


class TestRejectsUnknownStill:
    def test_filter_typo_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeaturesFilter.model_validate({"danceability__contains": 0.5})

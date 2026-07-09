"""Tests for scattering components (scalar path parity)."""

from __future__ import annotations

from app.domain.transition.scoring.components.bass import BassComponent
from app.domain.transition.scoring.components.drums import DrumsComponent
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent
from app.domain.transition.scoring.components.vocals import VocalsComponent
from app.shared.features import TrackFeatures


def _acid_a() -> TrackFeatures:
    return TrackFeatures(
        bpm=138.0,
        bpm_stability=0.95,
        key_code=4,
        integrated_lufs=-9.0,
        spectral_centroid_hz=2800.0,
        chroma_entropy=0.45,
        pitch_salience_mean=0.55,
        onset_rate=6.0,
        kick_prominence=0.80,
        hnr_db=-14.0,
        dissonance_mean=0.28,
        mfcc_vector=[8.0, -3.0, 1.5, 1.0, -0.3, 0.2, 0.1, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.08, 0.04, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.12, 0.18, 0.10, 0.20, 0.22, 0.18],
        beat_loudness_band_ratio=[0.85, 0.55, 0.35, 0.25, 0.15, 0.05],
    )


def _acid_b() -> TrackFeatures:
    return TrackFeatures(
        bpm=138.5,
        bpm_stability=0.93,
        key_code=4,
        integrated_lufs=-8.5,
        spectral_centroid_hz=2900.0,
        chroma_entropy=0.42,
        pitch_salience_mean=0.52,
        onset_rate=5.8,
        kick_prominence=0.78,
        hnr_db=-13.0,
        dissonance_mean=0.30,
        mfcc_vector=[7.5, -2.8, 1.3, 0.9, -0.25, 0.18, 0.09, 0.04, 0.02, 0.01, 0.0, 0.0, 0.0],
        tonnetz_vector=[0.07, 0.03, 0.02, 0.01, 0.0, 0.0],
        energy_bands=[0.11, 0.17, 0.09, 0.19, 0.21, 0.23],
        beat_loudness_band_ratio=[0.83, 0.53, 0.33, 0.23, 0.13, 0.05],
    )


class TestDrumsComponent:
    def test_scalar_range(self) -> None:
        c = DrumsComponent()
        s = c.score(_acid_a(), _acid_b())
        assert 0.0 <= s <= 1.0

    def test_missing_bpm_is_neutral(self) -> None:
        c = DrumsComponent()
        a = TrackFeatures()
        b = TrackFeatures()
        s = c.score(a, b)
        assert 0.0 <= s <= 1.0

    def test_name_and_weight(self) -> None:
        c = DrumsComponent()
        assert c.name == "drums"
        assert c.default_weight == 0.20


class TestBassComponent:
    def test_scalar_range(self) -> None:
        c = BassComponent()
        s = c.score(_acid_a(), _acid_b())
        assert 0.0 <= s <= 1.0

    def test_missing_key_is_neutral(self) -> None:
        c = BassComponent()
        a = TrackFeatures()
        b = TrackFeatures()
        s = c.score(a, b)
        assert 0.0 <= s <= 1.0

    def test_name_and_weight(self) -> None:
        c = BassComponent()
        assert c.name == "bass"
        assert c.default_weight == 0.15


class TestHarmonicsComponent:
    def test_scalar_range(self) -> None:
        c = HarmonicsComponent()
        s = c.score(_acid_a(), _acid_b())
        assert 0.0 <= s <= 1.0

    def test_missing_key_is_neutral(self) -> None:
        c = HarmonicsComponent()
        a = TrackFeatures()
        b = TrackFeatures()
        s = c.score(a, b)
        assert 0.0 <= s <= 1.0

    def test_name_and_weight(self) -> None:
        c = HarmonicsComponent()
        assert c.name == "harmonics"
        assert c.default_weight == 0.15


class TestVocalsComponent:
    def test_scalar_range(self) -> None:
        c = VocalsComponent()
        s = c.score(_acid_a(), _acid_b())
        assert 0.0 <= s <= 1.0

    def test_missing_centroid_is_neutral(self) -> None:
        c = VocalsComponent()
        a = TrackFeatures()
        b = TrackFeatures()
        s = c.score(a, b)
        assert 0.0 <= s <= 1.0

    def test_name_and_weight(self) -> None:
        c = VocalsComponent()
        assert c.name == "vocals"
        assert c.default_weight == 0.15

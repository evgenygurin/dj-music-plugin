"""TrackFeatures.from_db duck-typed row mapping."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.transition.features import TrackFeatures


@dataclass
class _FakeRow:
    """Duck-typed surrogate for TrackAudioFeaturesComputed ORM row."""

    bpm: float | None = 128.0
    bpm_confidence: float | None = 0.9
    bpm_stability: float | None = 0.85
    variable_tempo: bool | None = False
    key_code: int | None = 5
    key_confidence: float | None = 0.8
    atonality: bool | None = False
    integrated_lufs: float | None = -8.5
    short_term_lufs_mean: float | None = -9.0
    loudness_range_lu: float | None = 6.0
    crest_factor_db: float | None = 10.0
    energy_mean: float | None = 0.2
    energy_slope: float | None = 0.01
    energy_sub: float | None = 0.1
    energy_low: float | None = 0.15
    energy_lowmid: float | None = 0.2
    energy_mid: float | None = 0.25
    energy_highmid: float | None = 0.18
    energy_high: float | None = 0.12
    spectral_centroid_hz: float | None = 3000.0
    spectral_rolloff_85: float | None = 5000.0
    spectral_rolloff_95: float | None = 7000.0
    spectral_flatness: float | None = 0.3
    spectral_flux_std: float | None = 0.1
    spectral_slope: float | None = -20.0
    mfcc_vector: str | None = "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
    tonnetz_vector: str | None = None
    beat_loudness_band_ratio: str | None = None
    tempogram_ratio_vector: str | None = None
    hp_ratio: float | None = 2.0
    onset_rate: float | None = 5.0
    pulse_clarity: float | None = 0.1
    kick_prominence: float | None = 0.5
    chroma_entropy: float | None = 0.6
    hnr_db: float | None = 10.0
    dynamic_complexity: float | None = 2.0
    mood: str | None = "driving"
    first_downbeat_ms: float | None = 12.0
    true_peak_db: float | None = -0.5


def test_from_db_populates_primary_fields() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert feat.bpm == 128.0
    assert feat.key_code == 5
    assert feat.integrated_lufs == -8.5
    assert feat.energy_mean == 0.2
    assert feat.mood == "driving"


def test_from_db_parses_mfcc_json_string() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert isinstance(feat.mfcc_vector, list)
    assert len(feat.mfcc_vector) == 13


def test_from_db_assembles_energy_bands_from_six_columns() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert feat.energy_bands is not None
    assert len(feat.energy_bands) == 6
    assert feat.energy_bands[0] == 0.1
    assert feat.energy_bands[5] == 0.12


def test_from_db_drops_energy_bands_when_any_missing() -> None:
    row = _FakeRow(energy_mid=None)
    feat = TrackFeatures.from_db(row)
    assert feat.energy_bands is None


def test_from_db_handles_missing_json_fields() -> None:
    row = _FakeRow(mfcc_vector=None, tonnetz_vector=None)
    feat = TrackFeatures.from_db(row)
    assert feat.mfcc_vector is None
    assert feat.tonnetz_vector is None


def test_from_db_exposes_true_peak_db_for_audit_rules() -> None:
    """Regression: ``ClippingRiskRule`` reads ``features.true_peak_db``;
    without the mapping audit raised AttributeError on every analyzed
    track (Codex PR #113 P1 finding)."""
    feat = TrackFeatures.from_db(_FakeRow(true_peak_db=-0.3))
    assert feat.true_peak_db == -0.3

    # And: feeding TrackFeatures straight into the audit chain must not
    # throw — the exact failure mode Codex identified.
    from app.domain.audit.rules import DEFAULT_AUDIT_RULES, run_audit_rules

    issues = run_audit_rules(DEFAULT_AUDIT_RULES, track_id=1, title="T", features=feat)
    # Default row data passes all thresholds — key assertion is that no
    # AttributeError fired, not the issue count.
    assert isinstance(issues, list)

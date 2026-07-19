"""StemFeatures entity schemas (L6 per-stem analysis)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StemFeaturesView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    stem_name: str

    analysis_level: int | None = None

    # Tempo
    bpm: float | None = None
    bpm_confidence: float | None = None
    bpm_stability: float | None = None
    variable_tempo: bool | None = None

    # Loudness
    integrated_lufs: float | None = None
    short_term_lufs_mean: float | None = None
    momentary_max: float | None = None
    rms_dbfs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    loudness_range_lu: float | None = None

    # Energy — scalars + 6 band absolutes + 6 band ratios
    energy_mean: float | None = None
    energy_max: float | None = None
    energy_std: float | None = None
    energy_slope: float | None = None
    energy_sub: float | None = None
    energy_low: float | None = None
    energy_lowmid: float | None = None
    energy_mid: float | None = None
    energy_highmid: float | None = None
    energy_high: float | None = None
    energy_sub_ratio: float | None = None
    energy_low_ratio: float | None = None
    energy_lowmid_ratio: float | None = None
    energy_mid_ratio: float | None = None
    energy_highmid_ratio: float | None = None
    energy_high_ratio: float | None = None

    # Spectral
    spectral_centroid_hz: float | None = None
    spectral_rolloff_85: float | None = None
    spectral_rolloff_95: float | None = None
    spectral_flatness: float | None = None
    spectral_flux_mean: float | None = None
    spectral_flux_std: float | None = None
    spectral_slope: float | None = None
    spectral_contrast: float | None = None

    # Key / harmonic
    key_code: int | None = None
    key_confidence: float | None = None
    atonality: bool | None = None
    hnr_db: float | None = None
    chroma_entropy: float | None = None

    # Rhythm
    mfcc_vector: str | None = None
    hp_ratio: float | None = None
    onset_rate: float | None = None
    pulse_clarity: float | None = None
    kick_prominence: float | None = None

    # P1 enrichment
    danceability: float | None = None
    dynamic_complexity: float | None = None
    dissonance_mean: float | None = None
    tonnetz_vector: str | None = None
    tempogram_ratio_vector: str | None = None
    beat_loudness_band_ratio: str | None = None

    # P2 enrichment
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None
    bpm_histogram_first_peak_weight: float | None = None
    bpm_histogram_second_peak_bpm: float | None = None
    bpm_histogram_second_peak_weight: float | None = None
    dominant_phrase_bars: int | None = None
    phrase_boundaries_ms: str | None = None

    # Beatgrid phase
    first_downbeat_ms: float | None = None

    # L6-only
    chords_strength: float | None = None
    chords_changes_rate: float | None = None
    hpcp_entropy: float | None = None
    hpcp_crest: float | None = None
    inharmonicity: float | None = None
    meter: str | None = None
    click_detected: bool | None = None
    saturation_detected: bool | None = None
    drum_bands: dict[str, Any] | None = None


class StemFeaturesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    stem_name__eq: str | None = None
    stem_name__in: list[str] | None = None

    bpm__eq: float | None = None
    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__range: list[float] | None = None

    key_code__eq: int | None = None
    key_code__in: list[int] | None = None
    key_code__range: list[int] | None = None

    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None

    energy_mean__gte: float | None = None
    energy_mean__lte: float | None = None

    spectral_centroid_hz__gte: float | None = None
    spectral_centroid_hz__lte: float | None = None

    kick_prominence__gte: float | None = None
    kick_prominence__lte: float | None = None
    onset_rate__gte: float | None = None
    onset_rate__lte: float | None = None
    pulse_clarity__gte: float | None = None
    pulse_clarity__lte: float | None = None
    hp_ratio__gte: float | None = None
    hp_ratio__lte: float | None = None

    hnr_db__gte: float | None = None
    hnr_db__lte: float | None = None
    dissonance_mean__gte: float | None = None
    dissonance_mean__lte: float | None = None

    inharmonicity__gte: float | None = None
    inharmonicity__lte: float | None = None
    chords_strength__gte: float | None = None
    chords_strength__lte: float | None = None

    saturation_detected__eq: bool | None = None
    click_detected__eq: bool | None = None

    analysis_level__eq: int | None = None
    analysis_level__gte: int | None = None


class StemFeaturesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    stem_name: str


class StemFeaturesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

"""Audio feature schemas — mirrors TrackFeatures dataclass for Pydantic interop."""

from __future__ import annotations

from pydantic import ConfigDict

from dj_music.schemas.base import BaseEntity


class TrackFeatures(BaseEntity):
    """Minimal feature set needed for transition scoring.

    Field names intentionally match app/entities/audio/features.py so that
    existing from_db() logic and transition scorer code can work with either
    the dataclass or this Pydantic model.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    # Core scoring fields
    bpm: float | None = None
    key_code: int | None = None
    integrated_lufs: float | None = None
    spectral_centroid_hz: float | None = None
    spectral_flatness: float | None = None
    energy_mean: float | None = None
    onset_rate: float | None = None
    kick_prominence: float | None = None
    hnr_db: float | None = None
    chroma_entropy: float | None = None
    mfcc_vector: list[float] | None = None
    energy_bands: list[float] | None = None

    # P1 features
    dissonance_mean: float | None = None
    danceability: float | None = None
    tonnetz_vector: list[float] | None = None
    beat_loudness_band_ratio: list[float] | None = None

    # P2 features
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None

    # Previously unused in scoring
    bpm_stability: float | None = None
    spectral_contrast: float | None = None

    # P3 enrichment: BPM
    bpm_confidence: float | None = None
    variable_tempo: bool | None = None
    bpm_histogram_first_peak_weight: float | None = None
    bpm_histogram_second_peak_bpm: float | None = None

    # P3 enrichment: Harmonic
    atonality: bool | None = None
    key_confidence: float | None = None

    # P3 enrichment: Energy
    short_term_lufs_mean: float | None = None
    loudness_range_lu: float | None = None
    crest_factor_db: float | None = None
    energy_slope: float | None = None

    # P3 enrichment: Spectral
    spectral_rolloff_85: float | None = None
    spectral_rolloff_95: float | None = None
    spectral_slope: float | None = None
    spectral_flux_std: float | None = None

    # P3 enrichment: Groove
    pulse_clarity: float | None = None
    hp_ratio: float | None = None
    tempogram_ratio_vector: list[float] | None = None

    # P3 enrichment: Timbral
    dynamic_complexity: float | None = None

    # Beatgrid phase
    first_downbeat_ms: float | None = None

    # Mood classification
    mood: str | None = None

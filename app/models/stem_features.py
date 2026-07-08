"""Per-stem deep analysis features (L6)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StemFeatures(Base, TimestampMixin):
    __tablename__ = "stem_features"
    __table_args__ = (
        CheckConstraint("bpm IS NULL OR bpm BETWEEN 20 AND 300", name="ck_sf_bpm"),
        CheckConstraint("key_code IS NULL OR key_code BETWEEN 0 AND 23", name="ck_sf_key_code"),
        CheckConstraint("analysis_level BETWEEN 0 AND 6", name="ck_sf_analysis_level"),
        UniqueConstraint("track_id", "stem_name", name="uq_sf_track_stem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16))

    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_extraction_runs.id"), nullable=True
    )
    analysis_level: Mapped[int] = mapped_column(default=6, server_default="6")

    bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_confidence: Mapped[float | None] = mapped_column(nullable=True)
    bpm_stability: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool | None] = mapped_column(nullable=True)

    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True)
    short_term_lufs_mean: Mapped[float | None] = mapped_column(nullable=True)
    momentary_max: Mapped[float | None] = mapped_column(nullable=True)
    rms_dbfs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_db: Mapped[float | None] = mapped_column(nullable=True)
    crest_factor_db: Mapped[float | None] = mapped_column(nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(nullable=True)

    energy_mean: Mapped[float | None] = mapped_column(nullable=True)
    energy_max: Mapped[float | None] = mapped_column(nullable=True)
    energy_std: Mapped[float | None] = mapped_column(nullable=True)
    energy_slope: Mapped[float | None] = mapped_column(nullable=True)
    energy_sub: Mapped[float | None] = mapped_column(nullable=True)
    energy_low: Mapped[float | None] = mapped_column(nullable=True)
    energy_lowmid: Mapped[float | None] = mapped_column(nullable=True)
    energy_mid: Mapped[float | None] = mapped_column(nullable=True)
    energy_highmid: Mapped[float | None] = mapped_column(nullable=True)
    energy_high: Mapped[float | None] = mapped_column(nullable=True)
    energy_sub_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_low_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_lowmid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_mid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_highmid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_high_ratio: Mapped[float | None] = mapped_column(nullable=True)

    spectral_centroid_hz: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_85: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_95: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flatness: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_mean: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_std: Mapped[float | None] = mapped_column(nullable=True)
    spectral_slope: Mapped[float | None] = mapped_column(nullable=True)
    spectral_contrast: Mapped[float | None] = mapped_column(nullable=True)

    key_code: Mapped[int | None] = mapped_column(nullable=True)
    key_confidence: Mapped[float | None] = mapped_column(nullable=True)
    atonality: Mapped[bool | None] = mapped_column(nullable=True)
    hnr_db: Mapped[float | None] = mapped_column(nullable=True)
    chroma_entropy: Mapped[float | None] = mapped_column(nullable=True)

    mfcc_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hp_ratio: Mapped[float | None] = mapped_column(nullable=True)
    onset_rate: Mapped[float | None] = mapped_column(nullable=True)
    pulse_clarity: Mapped[float | None] = mapped_column(nullable=True)
    kick_prominence: Mapped[float | None] = mapped_column(nullable=True)

    danceability: Mapped[float | None] = mapped_column(nullable=True)
    dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
    dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
    tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    first_downbeat_ms: Mapped[float | None] = mapped_column(nullable=True)

    # L6-only
    chords_strength: Mapped[float | None] = mapped_column(nullable=True)
    chords_changes_rate: Mapped[float | None] = mapped_column(nullable=True)
    hpcp_entropy: Mapped[float | None] = mapped_column(nullable=True)
    hpcp_crest: Mapped[float | None] = mapped_column(nullable=True)
    inharmonicity: Mapped[float | None] = mapped_column(nullable=True)
    meter: Mapped[str | None] = mapped_column(String(16), nullable=True)
    click_detected: Mapped[bool | None] = mapped_column(nullable=True)
    saturation_detected: Mapped[bool | None] = mapped_column(nullable=True)

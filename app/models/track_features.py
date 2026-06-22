"""Track audio features + sections + timeseries + extraction runs.

Port of legacy ``app/db/models/audio.py``. 66-column flat schema
preserved verbatim. Indexes on bpm / integrated_lufs / key_code / mood
for fast candidate filtering.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FeatureExtractionRun(Base, TimestampMixin):
    __tablename__ = "feature_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_fer_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    pipeline_name: Mapped[str] = mapped_column(String(100))
    pipeline_version: Mapped[str] = mapped_column(String(50))
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_features: Mapped[TrackAudioFeaturesComputed | None] = relationship(
        back_populates="pipeline_run"
    )


class TrackAudioFeaturesComputed(Base, TimestampMixin):
    __tablename__ = "track_audio_features_computed"
    __table_args__ = (
        CheckConstraint("bpm IS NULL OR bpm BETWEEN 20 AND 300", name="ck_features_bpm"),
        CheckConstraint(
            "key_code IS NULL OR key_code BETWEEN 0 AND 23", name="ck_features_key_code"
        ),
        CheckConstraint("analysis_level BETWEEN 0 AND 5", name="ck_features_analysis_level"),
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_extraction_runs.id"), nullable=True, index=True
    )
    analysis_level: Mapped[int] = mapped_column(default=0, server_default="0")

    # Tempo (4)
    bpm: Mapped[float | None] = mapped_column(nullable=True, index=True)
    bpm_confidence: Mapped[float | None] = mapped_column(nullable=True)
    bpm_stability: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool | None] = mapped_column(nullable=True)

    # Loudness (7)
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True, index=True)
    short_term_lufs_mean: Mapped[float | None] = mapped_column(nullable=True)
    momentary_max: Mapped[float | None] = mapped_column(nullable=True)
    rms_dbfs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_db: Mapped[float | None] = mapped_column(nullable=True)
    crest_factor_db: Mapped[float | None] = mapped_column(nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(nullable=True)

    # Energy (16)
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

    # Spectral (8)
    spectral_centroid_hz: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_85: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_95: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flatness: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_mean: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_std: Mapped[float | None] = mapped_column(nullable=True)
    spectral_slope: Mapped[float | None] = mapped_column(nullable=True)
    spectral_contrast: Mapped[float | None] = mapped_column(nullable=True)

    # Key (5)
    key_code: Mapped[int | None] = mapped_column(nullable=True, index=True)
    key_confidence: Mapped[float | None] = mapped_column(nullable=True)
    atonality: Mapped[bool | None] = mapped_column(nullable=True)
    hnr_db: Mapped[float | None] = mapped_column(nullable=True)
    chroma_entropy: Mapped[float | None] = mapped_column(nullable=True)

    # Rhythm (5)
    mfcc_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hp_ratio: Mapped[float | None] = mapped_column(nullable=True)
    onset_rate: Mapped[float | None] = mapped_column(nullable=True)
    pulse_clarity: Mapped[float | None] = mapped_column(nullable=True)
    kick_prominence: Mapped[float | None] = mapped_column(nullable=True)

    # P1 (6)
    danceability: Mapped[float | None] = mapped_column(nullable=True)
    dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
    dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
    tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # P2 (7)
    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    first_downbeat_ms: Mapped[float | None] = mapped_column(nullable=True)

    # Classification
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    mood_confidence: Mapped[float | None] = mapped_column(nullable=True)

    pipeline_run: Mapped[FeatureExtractionRun | None] = relationship(
        back_populates="computed_features"
    )

    @classmethod
    def filter_features(cls, features: dict) -> dict:  # type: ignore[type-arg]
        """Filter pipeline dict to only columns that exist on this model."""
        known = {c.name for c in cls.__table__.columns}
        return {k: v for k, v in features.items() if k in known}


class TrackSection(Base, TimestampMixin):
    __tablename__ = "track_sections"
    __table_args__ = (
        CheckConstraint("section_type BETWEEN 0 AND 11", name="ck_section_type_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    section_type: Mapped[int] = mapped_column()
    start_ms: Mapped[int] = mapped_column()
    end_ms: Mapped[int] = mapped_column()
    # Prod is nullable (no NULLs today, but the constraint isn't enforced).
    energy: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)


class TimeseriesReference(Base, TimestampMixin):
    """Per-track on-disk timeseries pointers (energy / chroma / spectral / beats).

    Synced with prod 2026-05-07. Prod columns are ``feature_set_name`` and
    ``data_type``; the prior ORM exposed ``feature_set`` and ``dtype`` so
    every SELECT through SQLAlchemy would have failed against Supabase
    (in-memory SQLite tests passed because they create the schema from
    the ORM). The audio module (``app/audio/timeseries.py``) already
    emits dicts with the prod column names.
    """

    __tablename__ = "timeseries_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    feature_set_name: Mapped[str] = mapped_column(String(50))
    storage_uri: Mapped[str] = mapped_column(String(500))
    frame_count: Mapped[int] = mapped_column()
    hop_length: Mapped[int] = mapped_column()
    sample_rate: Mapped[int] = mapped_column()
    data_type: Mapped[str] = mapped_column(String(20))
    shape: Mapped[str] = mapped_column(String(100))

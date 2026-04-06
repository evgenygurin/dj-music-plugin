"""Audio analysis models (REQUIREMENTS §2.2, §2.8)."""

from typing import Any, ClassVar

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FeatureExtractionRun(Base, TimestampMixin):
    """A pipeline run that produces audio features for a track."""

    __tablename__ = "feature_extraction_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    pipeline_name: Mapped[str] = mapped_column(String(100))
    pipeline_version: Mapped[str] = mapped_column(String(50))
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    computed_features: Mapped["TrackAudioFeaturesComputed | None"] = relationship(
        back_populates="pipeline_run",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_fer_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"FeatureExtractionRun(id={self.id}, track_id={self.track_id}, "
            f"pipeline={self.pipeline_name!r}, status={self.status!r})"
        )


class TrackAudioFeaturesComputed(Base, TimestampMixin):
    """53 numerical audio feature descriptors extracted from analysis."""

    __tablename__ = "track_audio_features_computed"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True, unique=True
    )
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_extraction_runs.id"), nullable=True, index=True
    )
    analysis_level: Mapped[int] = mapped_column(
        default=0, server_default="0", doc="0=none, 2=L1+L2, 3=L3"
    )

    # --- Tempo (4 fields) ---
    bpm: Mapped[float | None] = mapped_column(nullable=True, index=True)
    bpm_confidence: Mapped[float | None] = mapped_column(nullable=True)
    bpm_stability: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool | None] = mapped_column(nullable=True)

    # --- Loudness (7 fields) ---
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True, index=True)
    short_term_lufs_mean: Mapped[float | None] = mapped_column(nullable=True)
    momentary_max: Mapped[float | None] = mapped_column(nullable=True)
    rms_dbfs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_db: Mapped[float | None] = mapped_column(nullable=True)
    crest_factor_db: Mapped[float | None] = mapped_column(nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(nullable=True)

    # --- Energy (13 fields) ---
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

    # --- Spectral (8 fields) ---
    spectral_centroid_hz: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_85: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_95: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flatness: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_mean: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_std: Mapped[float | None] = mapped_column(nullable=True)
    spectral_slope: Mapped[float | None] = mapped_column(nullable=True)
    spectral_contrast: Mapped[float | None] = mapped_column(nullable=True)

    # --- Key (5 fields) ---
    key_code: Mapped[int | None] = mapped_column(nullable=True, index=True)
    key_confidence: Mapped[float | None] = mapped_column(nullable=True)
    atonality: Mapped[bool | None] = mapped_column(nullable=True)
    hnr_db: Mapped[float | None] = mapped_column(nullable=True)
    chroma_entropy: Mapped[float | None] = mapped_column(nullable=True)

    # --- Rhythm (5 fields) ---
    mfcc_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hp_ratio: Mapped[float | None] = mapped_column(nullable=True)
    onset_rate: Mapped[float | None] = mapped_column(nullable=True)
    pulse_clarity: Mapped[float | None] = mapped_column(nullable=True)
    kick_prominence: Mapped[float | None] = mapped_column(nullable=True)

    # --- P1 New Features (6 fields) ---
    danceability: Mapped[float | None] = mapped_column(nullable=True)
    dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
    dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
    tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- P2 New Features (7 fields) ---
    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # --- Classification ---
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    mood_confidence: Mapped[float | None] = mapped_column(nullable=True)

    # relationships
    pipeline_run: Mapped["FeatureExtractionRun | None"] = relationship(
        back_populates="computed_features",
    )

    # ── Convenience methods ─────────────────────────────

    _CLASSIFIER_FIELDS: ClassVar[tuple[str, ...]] = (
        "energy_mean",
        "energy_max",
        "energy_std",
        "energy_slope",
        "spectral_centroid_hz",
        "spectral_rolloff_85",
        "spectral_rolloff_95",
        "spectral_flatness",
        "spectral_flux_mean",
        "spectral_flux_std",
        "spectral_contrast",
        "integrated_lufs",
        "short_term_lufs_mean",
        "momentary_max",
        "rms_dbfs",
        "true_peak_db",
        "crest_factor_db",
        "loudness_range_lu",
        "hp_ratio",
        "onset_rate",
        "pulse_clarity",
        "kick_prominence",
        "bpm",
        "bpm_confidence",
        "bpm_stability",
        "key_code",
        "key_confidence",
        "atonality",
        "hnr_db",
        "danceability",
        "dissonance_mean",
        "dynamic_complexity",
        "pitch_salience_mean",
        "spectral_complexity_mean",
        "bpm_histogram_first_peak_weight",
        "spectral_slope",
        "dominant_phrase_bars",
    )

    def to_classifier_dict(self) -> dict[str, Any]:
        """Convert features to dict suitable for MoodClassifier. Single source of truth."""
        return {field: getattr(self, field) for field in self._CLASSIFIER_FIELDS}

    @classmethod
    def filter_features(cls, features: dict[str, Any]) -> dict[str, Any]:
        """Filter pipeline output to only columns that exist on this model.

        Pipeline analyzers may produce extra keys that don't have DB columns.
        Also maps pipeline output names to DB column names where they differ.
        Serializes list values for VARCHAR vector columns to JSON strings.
        """
        import json

        valid = {c.name for c in cls.__table__.columns}
        valid -= {"track_id", "pipeline_run_id", "created_at", "updated_at"}

        # Columns that store JSON-encoded lists in VARCHAR
        vector_columns = {
            "mfcc_vector",
            "tonnetz_vector",
            "tempogram_ratio_vector",
            "beat_loudness_band_ratio",
            "phrase_boundaries_ms",
        }

        # Map pipeline keys → DB column names
        result: dict[str, Any] = {}
        for k, v in features.items():
            if k == "mfcc_mean" and "mfcc_vector" in valid:
                # Serialize MFCC list to JSON string for VARCHAR column
                result["mfcc_vector"] = json.dumps(v) if isinstance(v, list) else v
            elif k in valid:
                # Auto-serialize lists for VARCHAR vector columns
                if k in vector_columns and isinstance(v, list):
                    result[k] = json.dumps(v)
                else:
                    result[k] = v

        return result

    __table_args__ = (
        CheckConstraint("bpm IS NULL OR (bpm >= 20 AND bpm <= 300)", name="ck_tafc_bpm"),
        CheckConstraint(
            "bpm_confidence IS NULL OR (bpm_confidence >= 0 AND bpm_confidence <= 1)",
            name="ck_tafc_bpm_confidence",
        ),
        CheckConstraint(
            "bpm_stability IS NULL OR (bpm_stability >= 0 AND bpm_stability <= 1)",
            name="ck_tafc_bpm_stability",
        ),
        CheckConstraint(
            "energy_mean IS NULL OR (energy_mean >= 0 AND energy_mean <= 1)",
            name="ck_tafc_energy_mean",
        ),
        CheckConstraint(
            "key_code IS NULL OR (key_code >= 0 AND key_code <= 23)",
            name="ck_tafc_key_code",
        ),
        CheckConstraint(
            "key_confidence IS NULL OR (key_confidence >= 0 AND key_confidence <= 1)",
            name="ck_tafc_key_confidence",
        ),
    )

    def __repr__(self) -> str:
        return f"TrackAudioFeaturesComputed(track_id={self.track_id}, bpm={self.bpm})"


class TrackSection(Base, TimestampMixin):
    """A structural section within a track (intro, drop, outro, etc.)."""

    __tablename__ = "track_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    section_type: Mapped[int] = mapped_column()
    start_ms: Mapped[int] = mapped_column()
    end_ms: Mapped[int] = mapped_column()
    energy: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("section_type >= 0 AND section_type <= 11", name="ck_ts_section_type"),
        CheckConstraint("energy IS NULL OR (energy >= 0 AND energy <= 1)", name="ck_ts_energy"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ts_confidence",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"TrackSection(id={self.id}, track_id={self.track_id}, "
            f"type={self.section_type}, {self.start_ms}-{self.end_ms}ms)"
        )


class Embedding(Base, TimestampMixin):
    """Vector embedding representation of a track."""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    embedding_type: Mapped[str] = mapped_column(String(50))
    dimensions: Mapped[int] = mapped_column()
    vector_data: Mapped[bytes] = mapped_column(LargeBinary)

    __table_args__ = (
        UniqueConstraint("track_id", "embedding_type", name="uq_embedding_track_type"),
    )

    def __repr__(self) -> str:
        return (
            f"Embedding(id={self.id}, track_id={self.track_id}, "
            f"type={self.embedding_type!r}, dims={self.dimensions})"
        )


class TimeseriesReference(Base, TimestampMixin):
    """Pointer to frame-level feature data stored on disk."""

    __tablename__ = "timeseries_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    feature_set_name: Mapped[str] = mapped_column(String(100))
    storage_uri: Mapped[str] = mapped_column(String(1000))
    frame_count: Mapped[int] = mapped_column()
    hop_length: Mapped[int] = mapped_column()
    sample_rate: Mapped[int] = mapped_column()
    data_type: Mapped[str] = mapped_column(String(20))
    shape: Mapped[str] = mapped_column(String(100), comment="JSON-like shape descriptor")

    def __repr__(self) -> str:
        return (
            f"TimeseriesReference(id={self.id}, track_id={self.track_id}, "
            f"feature={self.feature_set_name!r})"
        )

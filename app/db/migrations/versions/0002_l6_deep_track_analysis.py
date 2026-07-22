"""add L6 deep track analysis tables

Revision ID: 0002
Revises: f3702c8a41cd
Create Date: 2026-07-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "f3702c8a41cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── stem_features ────────────────────────────────────
    op.create_table(
        "stem_features",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stem_name", sa.String(length=16), nullable=False),
        sa.Column(
            "pipeline_run_id",
            sa.Integer(),
            sa.ForeignKey("feature_extraction_runs.id"),
            nullable=True,
        ),
        sa.Column("analysis_level", sa.Integer(), server_default="6", nullable=False),
        # — Tempo —
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("bpm_confidence", sa.Float(), nullable=True),
        sa.Column("bpm_stability", sa.Float(), nullable=True),
        sa.Column("variable_tempo", sa.Boolean(), nullable=True),
        # — Loudness —
        sa.Column("integrated_lufs", sa.Float(), nullable=True),
        sa.Column("short_term_lufs_mean", sa.Float(), nullable=True),
        sa.Column("momentary_max", sa.Float(), nullable=True),
        sa.Column("rms_dbfs", sa.Float(), nullable=True),
        sa.Column("true_peak_db", sa.Float(), nullable=True),
        sa.Column("crest_factor_db", sa.Float(), nullable=True),
        sa.Column("loudness_range_lu", sa.Float(), nullable=True),
        # — Energy —
        sa.Column("energy_mean", sa.Float(), nullable=True),
        sa.Column("energy_max", sa.Float(), nullable=True),
        sa.Column("energy_std", sa.Float(), nullable=True),
        sa.Column("energy_slope", sa.Float(), nullable=True),
        sa.Column("energy_sub", sa.Float(), nullable=True),
        sa.Column("energy_low", sa.Float(), nullable=True),
        sa.Column("energy_lowmid", sa.Float(), nullable=True),
        sa.Column("energy_mid", sa.Float(), nullable=True),
        sa.Column("energy_highmid", sa.Float(), nullable=True),
        sa.Column("energy_high", sa.Float(), nullable=True),
        sa.Column("energy_sub_ratio", sa.Float(), nullable=True),
        sa.Column("energy_low_ratio", sa.Float(), nullable=True),
        sa.Column("energy_lowmid_ratio", sa.Float(), nullable=True),
        sa.Column("energy_mid_ratio", sa.Float(), nullable=True),
        sa.Column("energy_highmid_ratio", sa.Float(), nullable=True),
        sa.Column("energy_high_ratio", sa.Float(), nullable=True),
        # — Spectral —
        sa.Column("spectral_centroid_hz", sa.Float(), nullable=True),
        sa.Column("spectral_rolloff_85", sa.Float(), nullable=True),
        sa.Column("spectral_rolloff_95", sa.Float(), nullable=True),
        sa.Column("spectral_flatness", sa.Float(), nullable=True),
        sa.Column("spectral_flux_mean", sa.Float(), nullable=True),
        sa.Column("spectral_flux_std", sa.Float(), nullable=True),
        sa.Column("spectral_slope", sa.Float(), nullable=True),
        sa.Column("spectral_contrast", sa.Float(), nullable=True),
        # — Key —
        sa.Column("key_code", sa.Integer(), nullable=True),
        sa.Column("key_confidence", sa.Float(), nullable=True),
        sa.Column("atonality", sa.Boolean(), nullable=True),
        sa.Column("hnr_db", sa.Float(), nullable=True),
        sa.Column("chroma_entropy", sa.Float(), nullable=True),
        # — Rhythm —
        sa.Column("mfcc_vector", sa.String(length=500), nullable=True),
        sa.Column("hp_ratio", sa.Float(), nullable=True),
        sa.Column("onset_rate", sa.Float(), nullable=True),
        sa.Column("pulse_clarity", sa.Float(), nullable=True),
        sa.Column("kick_prominence", sa.Float(), nullable=True),
        # — P1 Essentia —
        sa.Column("danceability", sa.Float(), nullable=True),
        sa.Column("dynamic_complexity", sa.Float(), nullable=True),
        sa.Column("dissonance_mean", sa.Float(), nullable=True),
        sa.Column("tonnetz_vector", sa.String(length=500), nullable=True),
        sa.Column("tempogram_ratio_vector", sa.String(length=500), nullable=True),
        sa.Column("beat_loudness_band_ratio", sa.String(length=500), nullable=True),
        # — P2 Essentia —
        sa.Column("spectral_complexity_mean", sa.Float(), nullable=True),
        sa.Column("pitch_salience_mean", sa.Float(), nullable=True),
        sa.Column("bpm_histogram_first_peak_weight", sa.Float(), nullable=True),
        sa.Column("bpm_histogram_second_peak_bpm", sa.Float(), nullable=True),
        sa.Column("bpm_histogram_second_peak_weight", sa.Float(), nullable=True),
        sa.Column("phrase_boundaries_ms", sa.String(length=2000), nullable=True),
        sa.Column("dominant_phrase_bars", sa.SmallInteger(), nullable=True),
        sa.Column("first_downbeat_ms", sa.Float(), nullable=True),
        # — L6-only —
        sa.Column("chords_strength", sa.Float(), nullable=True),
        sa.Column("chords_changes_rate", sa.Float(), nullable=True),
        sa.Column("hpcp_entropy", sa.Float(), nullable=True),
        sa.Column("hpcp_crest", sa.Float(), nullable=True),
        sa.Column("inharmonicity", sa.Float(), nullable=True),
        sa.Column("meter", sa.String(length=16), nullable=True),
        sa.Column("click_detected", sa.Boolean(), nullable=True),
        sa.Column("saturation_detected", sa.Boolean(), nullable=True),
        # — timestamps —
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_id", "stem_name", name="uq_sf_track_stem"),
    )
    op.create_index("idx_stem_features_track", "stem_features", ["track_id"])

    # ── track_embeddings ─────────────────────────────────
    op.create_table(
        "track_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stem_name", sa.String(length=16), server_default="original", nullable=False),
        sa.Column("embedding_type", sa.String(length=32), nullable=False),
        sa.Column("embedding", Vector(256), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "track_id", "stem_name", "embedding_type", name="uq_te_track_stem_type"
        ),
    )
    op.create_index(
        "idx_track_embeddings_hnsw",
        "track_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── cross_similarity ─────────────────────────────────
    op.create_table(
        "cross_similarity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "track_a_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "track_b_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stem_name", sa.String(length=16), server_default="original", nullable=False),
        sa.Column("matrix_shape", sa.String(length=50), nullable=True),
        sa.Column("best_match_offset_ms", sa.Float(), nullable=True),
        sa.Column("best_match_score", sa.Float(), nullable=True),
        sa.Column("alignment_path", JSONB, nullable=True),
        sa.Column("segment_matches", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_a_id", "track_b_id", "stem_name", name="uq_cs_pair_stem"),
    )
    op.create_index("idx_cross_similarity_a", "cross_similarity", ["track_a_id"])
    op.create_index("idx_cross_similarity_b", "cross_similarity", ["track_b_id"])

    # ── track_sections extensions ─────────────────────────
    op.add_column("track_sections", sa.Column("lufs", sa.Float(), nullable=True))
    op.add_column("track_sections", sa.Column("spectral_centroid", sa.Float(), nullable=True))
    op.add_column("track_sections", sa.Column("stem_energy", JSONB, nullable=True))

    # ── analysis_level CHECK update ───────────────────────
    op.drop_constraint("ck_features_analysis_level", "track_audio_features_computed")
    op.create_check_constraint(
        "ck_features_analysis_level",
        "track_audio_features_computed",
        sa.text("analysis_level BETWEEN 0 AND 6"),
    )


def downgrade() -> None:
    op.drop_table("cross_similarity")
    op.drop_table("track_embeddings")
    op.drop_table("stem_features")
    op.drop_column("track_sections", "lufs")
    op.drop_column("track_sections", "spectral_centroid")
    op.drop_column("track_sections", "stem_energy")
    op.drop_constraint("ck_features_analysis_level", "track_audio_features_computed")
    op.create_check_constraint(
        "ck_features_analysis_level",
        "track_audio_features_computed",
        sa.text("analysis_level BETWEEN 0 AND 5"),
    )

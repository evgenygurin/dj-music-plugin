"""add track_affinity track_feedback scoring_profiles

Revision ID: 97a8c9a67f13
Revises: a525818436cb
Create Date: 2026-04-11 22:17:10.283426

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97a8c9a67f13"
down_revision: str | None = "a525818436cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # track_affinity
    op.create_table(
        "track_affinity",
        sa.Column("id", sa.Integer(), primary_key=True),
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
        sa.Column("play_count", sa.Integer(), server_default="0"),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("like_count", sa.Integer(), server_default="0"),
        sa.Column("ban_count", sa.Integer(), server_default="0"),
        sa.Column("skip_count", sa.Integer(), server_default="0"),
        sa.Column("net_sentiment", sa.Float(), server_default="0"),
        sa.Column("last_played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("track_a_id", "track_b_id", name="uq_track_affinity_pair"),
    )
    op.create_index("idx_track_affinity_a", "track_affinity", ["track_a_id"])
    op.create_index("idx_track_affinity_b", "track_affinity", ["track_b_id"])
    op.create_index("idx_track_affinity_sentiment", "track_affinity", ["net_sentiment"])

    # track_feedback
    op.create_table(
        "track_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rating", sa.Integer(), server_default="3"),
        sa.Column("status", sa.String(20), server_default="'active'"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("play_count", sa.Integer(), server_default="0"),
        sa.Column("skip_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_track_feedback_rating"),
        sa.CheckConstraint(
            "status IN ('active', 'liked', 'banned', 'archived')", name="ck_track_feedback_status"
        ),
    )
    op.create_index("idx_track_feedback_track", "track_feedback", ["track_id"], unique=True)

    # scoring_profiles
    op.create_table(
        "scoring_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("bpm_weight", sa.Float(), server_default="0.20"),
        sa.Column("harmonic_weight", sa.Float(), server_default="0.12"),
        sa.Column("energy_weight", sa.Float(), server_default="0.18"),
        sa.Column("spectral_weight", sa.Float(), server_default="0.20"),
        sa.Column("groove_weight", sa.Float(), server_default="0.15"),
        sa.Column("timbral_weight", sa.Float(), server_default="0.15"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("bpm_weight >= 0 AND bpm_weight <= 1", name="ck_scoring_bpm"),
        sa.CheckConstraint(
            "harmonic_weight >= 0 AND harmonic_weight <= 1", name="ck_scoring_harmonic"
        ),
        sa.CheckConstraint("energy_weight >= 0 AND energy_weight <= 1", name="ck_scoring_energy"),
        sa.CheckConstraint(
            "spectral_weight >= 0 AND spectral_weight <= 1", name="ck_scoring_spectral"
        ),
        sa.CheckConstraint("groove_weight >= 0 AND groove_weight <= 1", name="ck_scoring_groove"),
        sa.CheckConstraint(
            "timbral_weight >= 0 AND timbral_weight <= 1", name="ck_scoring_timbral"
        ),
    )


def downgrade() -> None:
    op.drop_table("scoring_profiles")
    op.drop_index("idx_track_feedback_track")
    op.drop_table("track_feedback")
    op.drop_index("idx_track_affinity_sentiment")
    op.drop_index("idx_track_affinity_b")
    op.drop_index("idx_track_affinity_a")
    op.drop_table("track_affinity")

"""add transition_history table

Revision ID: a525818436cb
Revises: f3a9b1c2d4e5
Create Date: 2026-04-11 13:30:03.198206

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a525818436cb"
down_revision: str | None = "f4a1b2c3d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transition_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "from_track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("bpm_score", sa.Float(), nullable=True),
        sa.Column("harmonic_score", sa.Float(), nullable=True),
        sa.Column("energy_score", sa.Float(), nullable=True),
        sa.Column("spectral_score", sa.Float(), nullable=True),
        sa.Column("groove_score", sa.Float(), nullable=True),
        sa.Column("timbral_score", sa.Float(), nullable=True),
        sa.Column("style", sa.String(30), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("tempo_match_ratio", sa.Float(), nullable=True),
        sa.Column("user_reaction", sa.String(20), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "from_track_id", "to_track_id", "session_id", name="uq_transition_history_pair_session"
        ),
        sa.CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
            name="ck_transition_history_score",
        ),
        sa.CheckConstraint(
            "user_reaction IS NULL OR user_reaction IN ('like', 'ban', 'skip', 'listened')",
            name="ck_transition_history_reaction",
        ),
    )
    op.create_index("idx_transition_history_from", "transition_history", ["from_track_id"])
    op.create_index("idx_transition_history_to", "transition_history", ["to_track_id"])
    op.create_index("idx_transition_history_score", "transition_history", ["overall_score"])


def downgrade() -> None:
    op.drop_index("idx_transition_history_score")
    op.drop_index("idx_transition_history_to")
    op.drop_index("idx_transition_history_from")
    op.drop_table("transition_history")

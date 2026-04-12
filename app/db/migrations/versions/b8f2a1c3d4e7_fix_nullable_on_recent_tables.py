"""fix nullable on recent tables (transition_history, track_affinity, track_feedback, scoring_profiles)

Revision ID: b8f2a1c3d4e7
Revises: 97a8c9a67f13
Create Date: 2026-04-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f2a1c3d4e7"
down_revision: str | None = "97a8c9a67f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use batch_alter_table for SQLite compatibility (ALTER COLUMN not supported).
    # On PostgreSQL these become plain ALTER COLUMN ... SET NOT NULL.

    with op.batch_alter_table("scoring_profiles") as batch:
        for col in (
            "bpm_weight",
            "harmonic_weight",
            "energy_weight",
            "spectral_weight",
            "groove_weight",
            "timbral_weight",
        ):
            batch.alter_column(col, existing_type=sa.Float(), nullable=False)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    with op.batch_alter_table("track_affinity") as batch:
        for col in ("play_count", "like_count", "ban_count", "skip_count"):
            batch.alter_column(col, existing_type=sa.Integer(), nullable=False)
        batch.alter_column("net_sentiment", existing_type=sa.Float(), nullable=False)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    with op.batch_alter_table("track_feedback") as batch:
        batch.alter_column("rating", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("status", existing_type=sa.String(20), nullable=False)
        for col in ("play_count", "skip_count"):
            batch.alter_column(col, existing_type=sa.Integer(), nullable=False)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    with op.batch_alter_table("transition_history") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("scoring_profiles") as batch:
        for col in (
            "bpm_weight",
            "harmonic_weight",
            "energy_weight",
            "spectral_weight",
            "groove_weight",
            "timbral_weight",
        ):
            batch.alter_column(col, existing_type=sa.Float(), nullable=True)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=True)

    with op.batch_alter_table("track_affinity") as batch:
        for col in ("play_count", "like_count", "ban_count", "skip_count"):
            batch.alter_column(col, existing_type=sa.Integer(), nullable=True)
        batch.alter_column("net_sentiment", existing_type=sa.Float(), nullable=True)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=True)

    with op.batch_alter_table("track_feedback") as batch:
        batch.alter_column("rating", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("status", existing_type=sa.String(20), nullable=True)
        for col in ("play_count", "skip_count"):
            batch.alter_column(col, existing_type=sa.Integer(), nullable=True)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=True)

    with op.batch_alter_table("transition_history") as batch:
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=True)

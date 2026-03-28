"""Add P2 analyzer columns.

Revision ID: b5e7f234a891
Revises: a46fe524044f
Create Date: 2026-03-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5e7f234a891"
down_revision: str | None = "a46fe524044f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.add_column(sa.Column("spectral_complexity_mean", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pitch_salience_mean", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("bpm_histogram_first_peak_weight", sa.Float(), nullable=True)
        )
        batch_op.add_column(sa.Column("bpm_histogram_second_peak_bpm", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("bpm_histogram_second_peak_weight", sa.Float(), nullable=True)
        )
        batch_op.add_column(sa.Column("phrase_boundaries_ms", sa.String(2000), nullable=True))
        batch_op.add_column(sa.Column("dominant_phrase_bars", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.drop_column("dominant_phrase_bars")
        batch_op.drop_column("phrase_boundaries_ms")
        batch_op.drop_column("bpm_histogram_second_peak_weight")
        batch_op.drop_column("bpm_histogram_second_peak_bpm")
        batch_op.drop_column("bpm_histogram_first_peak_weight")
        batch_op.drop_column("pitch_salience_mean")
        batch_op.drop_column("spectral_complexity_mean")

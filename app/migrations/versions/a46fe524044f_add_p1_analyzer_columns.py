"""Add P1 analyzer columns.

Revision ID: a46fe524044f
Revises: 90b8916fe80b
Create Date: 2026-03-28 22:40:57.285598

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a46fe524044f"
down_revision: str | None = "90b8916fe80b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.add_column(sa.Column("danceability", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dynamic_complexity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dissonance_mean", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("tonnetz_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("tempogram_ratio_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("beat_loudness_band_ratio", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.drop_column("beat_loudness_band_ratio")
        batch_op.drop_column("tempogram_ratio_vector")
        batch_op.drop_column("tonnetz_vector")
        batch_op.drop_column("dissonance_mean")
        batch_op.drop_column("dynamic_complexity")
        batch_op.drop_column("danceability")

"""add first_downbeat_ms to features

Stores the first downbeat position (ms from track start) directly
in track_audio_features_computed, enabling crossfade phase alignment
without requiring a dj_library_item / dj_beatgrid row.

Revision ID: f4a1b2c3d5e6
Revises: f3a9b1c2d4e5
Create Date: 2026-04-10 19:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a1b2c3d5e6"
down_revision: str | None = "f3a9b1c2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add first_downbeat_ms column to track_audio_features_computed."""
    with op.batch_alter_table("track_audio_features_computed") as batch:
        batch.add_column(sa.Column("first_downbeat_ms", sa.Float(), nullable=True))


def downgrade() -> None:
    """Drop first_downbeat_ms column."""
    with op.batch_alter_table("track_audio_features_computed") as batch:
        batch.drop_column("first_downbeat_ms")

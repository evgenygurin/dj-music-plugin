"""add fx_type, drop transition_type

fx_type stores NeuralMixCrossfaderFX values (7 Neural Mix presets).
transition_type (legacy 14-value style enum) removed from model and table.

Revision ID: a1b2c3d4e5f6
Revises: f4a1b2c3d5e6
Create Date: 2026-04-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f4a1b2c3d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add fx_type column, drop legacy transition_type column."""
    op.add_column("transitions", sa.Column("fx_type", sa.String(length=30), nullable=True))
    op.drop_column("transitions", "transition_type")


def downgrade() -> None:
    """Restore transition_type column, drop fx_type column."""
    op.add_column("transitions", sa.Column("transition_type", sa.String(length=30), nullable=True))
    op.drop_column("transitions", "fx_type")

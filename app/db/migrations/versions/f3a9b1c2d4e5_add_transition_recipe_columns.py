"""add transition recipe columns

Three nullable columns on transitions table: transition_type (style name),
transition_bars (recommended mix length), transition_recipe_json (full
style recommendation payload from app/transition/style.py).

Revision ID: f3a9b1c2d4e5
Revises: e7c1f482a3b9
Create Date: 2026-04-10 15:35:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9b1c2d4e5"
down_revision: str | None = "e7c1f482a3b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add transition_type, transition_bars, transition_recipe_json columns."""
    with op.batch_alter_table("transitions") as batch:
        batch.add_column(sa.Column("transition_type", sa.String(30), nullable=True))
        batch.add_column(sa.Column("transition_bars", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("transition_recipe_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop transition recipe columns."""
    with op.batch_alter_table("transitions") as batch:
        batch.drop_column("transition_recipe_json")
        batch.drop_column("transition_bars")
        batch.drop_column("transition_type")

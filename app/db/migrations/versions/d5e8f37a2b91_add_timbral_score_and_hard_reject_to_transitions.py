"""add timbral_score + hard_reject + reject_reason to transitions

BUG-2 / BUG-3: TransitionScorer emits 6 components (bpm, harmonic,
energy, spectral, groove, **timbral**) but only 5 were persisted. The
``hard_reject`` flag and ``reject_reason`` text produced by the scorer
were also thrown away, so cached score lookups could not tell "low
quality" from "explicit hard reject". This migration adds the missing
columns to ``transitions`` and sets their CHECK constraint for the
score value.

Revision ID: d5e8f37a2b91
Revises: c4f8a9b2d1e3
Create Date: 2026-04-07 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e8f37a2b91"
down_revision: str | None = "c4f8a9b2d1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``timbral_score``, ``hard_reject`` and ``reject_reason`` columns."""
    with op.batch_alter_table("transitions") as batch:
        batch.add_column(sa.Column("timbral_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("hard_reject", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("reject_reason", sa.String(length=255), nullable=True))
        batch.create_check_constraint(
            "ck_transitions_timbral_score",
            "timbral_score IS NULL OR (timbral_score >= 0 AND timbral_score <= 1)",
        )


def downgrade() -> None:
    """Drop the three columns in reverse order."""
    with op.batch_alter_table("transitions") as batch:
        batch.drop_constraint("ck_transitions_timbral_score", type_="check")
        batch.drop_column("reject_reason")
        batch.drop_column("hard_reject")
        batch.drop_column("timbral_score")

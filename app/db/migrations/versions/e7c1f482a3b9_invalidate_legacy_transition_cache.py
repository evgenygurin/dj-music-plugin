"""invalidate stale 5-component transition cache rows

BUG-10: rows persisted before BUG-2 fix lack ``timbral_score``,
``hard_reject`` and ``reject_reason``. They were scored with the old
5-component formula and a different weight set, so leaving them in
the cache produces a confusing mix of "old" and "new" overall scores
to the caller. This migration removes them so that the next call to
``score_pair`` recomputes them with the canonical 6-component scorer.

The blast radius is small (cached scores are derivable on demand) and
the alternative — silently mixing formulas — is worse than a single
recompute.

Revision ID: e7c1f482a3b9
Revises: d5e8f37a2b91
Create Date: 2026-04-07 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c1f482a3b9"
down_revision: str | None = "d5e8f37a2b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop transition rows produced by the legacy 5-component scorer."""
    op.execute(sa.text("DELETE FROM transitions WHERE timbral_score IS NULL"))


def downgrade() -> None:
    """No-op: deleted rows are recreated on the next ``score_pair`` call."""

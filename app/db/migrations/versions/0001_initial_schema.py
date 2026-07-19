"""initial schema (stamped placeholder)

Revision ID: f3702c8a41cd
Revises: None
Create Date: 2026-07-09 (placeholder)
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "f3702c8a41cd"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

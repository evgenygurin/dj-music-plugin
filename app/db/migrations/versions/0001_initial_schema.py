"""initial schema (stamped placeholder)

Revision ID: f3702c8a41cd
Revises: None
Create Date: 2026-07-09 (placeholder)
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "f3702c8a41cd"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

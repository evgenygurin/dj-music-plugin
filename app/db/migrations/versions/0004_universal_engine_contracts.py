"""additive universal-engine contract persistence

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.JSON:
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("source_hash", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("analyzer_versions", _json(), nullable=False),
        sa.Column("model_versions", _json(), nullable=False),
        sa.Column("payload", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_analysis_snapshots_source_hash", "analysis_snapshots", ["source_hash"])
    op.create_table(
        "transition_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_identity", sa.String(64), nullable=False, unique=True),
        sa.Column("source_identity", sa.String(64), nullable=False),
        sa.Column("target_identity", sa.String(64), nullable=False),
        sa.Column("config_identity", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("plan", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_transition_plans_pair", "transition_plans", ["source_identity", "target_identity"]
    )
    op.create_table(
        "set_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity", sa.String(64), nullable=False, unique=True),
        sa.Column("config_identity", sa.String(64), nullable=False),
        sa.Column("plan", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "execution_manifests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "shadow_comparisons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comparison_identity", sa.String(64), nullable=False, unique=True),
        sa.Column("execution_identity", sa.String(64), nullable=False),
        sa.Column("comparison", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_shadow_comparisons_execution", "shadow_comparisons", ["execution_identity"]
    )


def downgrade() -> None:
    op.drop_index("ix_shadow_comparisons_execution", table_name="shadow_comparisons")
    op.drop_table("shadow_comparisons")
    op.drop_table("execution_manifests")
    op.drop_table("set_plans")
    op.drop_table("transition_plans")
    op.drop_index("ix_analysis_snapshots_source_hash", table_name="analysis_snapshots")
    op.drop_table("analysis_snapshots")

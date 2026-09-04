"""SQLAlchemy persistence adapter for universal-engine contracts."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

_METADATA = sa.MetaData()
_ANALYSIS = sa.Table(
    "analysis_snapshots",
    _METADATA,
    sa.Column("identity_hash", sa.String(64), primary_key=True),
    sa.Column("source_hash", sa.String(128), nullable=False),
    sa.Column("schema_version", sa.String(32), nullable=False),
    sa.Column("analyzer_versions", sa.JSON(), nullable=False),
    sa.Column("model_versions", sa.JSON(), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
)
_TRANSITIONS = sa.Table(
    "transition_plans",
    _METADATA,
    sa.Column("execution_identity", sa.String(64), primary_key=True),
    sa.Column("source_identity", sa.String(64), nullable=False),
    sa.Column("target_identity", sa.String(64), nullable=False),
    sa.Column("config_identity", sa.String(64), nullable=False),
    sa.Column("engine_version", sa.String(64), nullable=False),
    sa.Column("plan", sa.JSON(), nullable=False),
)
_SETS = sa.Table(
    "set_plans",
    _METADATA,
    sa.Column("identity", sa.String(64), primary_key=True),
    sa.Column("config_identity", sa.String(64), nullable=False),
    sa.Column("plan", sa.JSON(), nullable=False),
)
_MANIFESTS = sa.Table(
    "execution_manifests",
    _METADATA,
    sa.Column("identity", sa.String(64), primary_key=True),
    sa.Column("manifest", sa.JSON(), nullable=False),
)
_SHADOW = sa.Table(
    "shadow_comparisons",
    _METADATA,
    sa.Column("comparison_identity", sa.String(64), primary_key=True),
    sa.Column("execution_identity", sa.String(64), nullable=False),
    sa.Column("comparison", sa.JSON(), nullable=False),
)


class EngineContractStore:
    """Persist immutable engine artifacts by their deterministic identity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_analysis_snapshot(
        self,
        identity_hash: str,
        source_hash: str,
        schema_version: str,
        analyzer_versions: dict[str, Any],
        model_versions: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        await self._upsert(
            _ANALYSIS,
            "identity_hash",
            identity_hash,
            source_hash=source_hash,
            schema_version=schema_version,
            analyzer_versions=analyzer_versions,
            model_versions=model_versions,
            payload=payload,
        )

    async def get_analysis_snapshot(self, identity_hash: str) -> dict[str, Any] | None:
        return await self._get(_ANALYSIS, "identity_hash", identity_hash)

    async def save_transition_plan(
        self,
        execution_identity: str,
        source_identity: str,
        target_identity: str,
        config_identity: str,
        engine_version: str,
        plan: dict[str, Any],
    ) -> None:
        await self._upsert(
            _TRANSITIONS,
            "execution_identity",
            execution_identity,
            source_identity=source_identity,
            target_identity=target_identity,
            config_identity=config_identity,
            engine_version=engine_version,
            plan=plan,
        )

    async def get_transition_plan(self, execution_identity: str) -> dict[str, Any] | None:
        return await self._get(_TRANSITIONS, "execution_identity", execution_identity)

    async def save_set_plan(
        self, identity: str, config_identity: str, plan: dict[str, Any]
    ) -> None:
        await self._upsert(_SETS, "identity", identity, config_identity=config_identity, plan=plan)

    async def get_set_plan(self, identity: str) -> dict[str, Any] | None:
        return await self._get(_SETS, "identity", identity)

    async def save_execution_manifest(self, identity: str, manifest: dict[str, Any]) -> None:
        await self._upsert(_MANIFESTS, "identity", identity, manifest=manifest)

    async def get_execution_manifest(self, identity: str) -> dict[str, Any] | None:
        return await self._get(_MANIFESTS, "identity", identity)

    async def save_shadow_comparison(
        self, comparison_identity: str, execution_identity: str, comparison: dict[str, Any]
    ) -> None:
        await self._upsert(
            _SHADOW,
            "comparison_identity",
            comparison_identity,
            execution_identity=execution_identity,
            comparison=comparison,
        )

    async def get_shadow_comparison(self, comparison_identity: str) -> dict[str, Any] | None:
        return await self._get(_SHADOW, "comparison_identity", comparison_identity)

    async def _get(self, table: sa.Table, key_column: str, identity: str) -> dict[str, Any] | None:
        key = table.c[key_column]
        result = await self._session.execute(sa.select(table).where(key == identity))
        row = result.mappings().first()
        return dict(row) if row is not None else None

    async def _upsert(
        self,
        table: sa.Table,
        key_column: str,
        identity: str,
        **values: Any,
    ) -> None:
        key = table.c[key_column]
        result = await self._session.execute(sa.select(key).where(key == identity))
        if result.first() is None:
            await self._session.execute(table.insert().values({key_column: identity, **values}))
        else:
            await self._session.execute(table.update().where(key == identity).values(**values))
        await self._session.flush()

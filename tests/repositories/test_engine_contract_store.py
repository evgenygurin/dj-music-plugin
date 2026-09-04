from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.engine_contracts import EngineContractStore


async def _create_tables(session: AsyncSession) -> None:
    await session.execute(
        text("""
        CREATE TABLE analysis_snapshots (
            identity_hash VARCHAR(64) PRIMARY KEY,
            source_hash VARCHAR(128) NOT NULL,
            schema_version VARCHAR(32) NOT NULL,
            analyzer_versions JSON NOT NULL,
            model_versions JSON NOT NULL,
            payload JSON NOT NULL
        )
    """)
    )
    await session.execute(
        text("""
        CREATE TABLE transition_plans (
            execution_identity VARCHAR(64) PRIMARY KEY,
            source_identity VARCHAR(64) NOT NULL,
            target_identity VARCHAR(64) NOT NULL,
            config_identity VARCHAR(64) NOT NULL,
            engine_version VARCHAR(64) NOT NULL,
            plan JSON NOT NULL
        )
    """)
    )
    await session.execute(
        text("""
        CREATE TABLE set_plans (
            identity VARCHAR(64) PRIMARY KEY,
            config_identity VARCHAR(64) NOT NULL,
            plan JSON NOT NULL
        )
    """)
    )
    await session.execute(
        text("""
        CREATE TABLE execution_manifests (
            identity VARCHAR(64) PRIMARY KEY,
            manifest JSON NOT NULL
        )
    """)
    )
    await session.commit()


async def test_store_round_trips_all_contracts(session: AsyncSession) -> None:
    await _create_tables(session)
    store = EngineContractStore(session)

    await store.save_analysis_snapshot(
        "a", "source", "1", {"tempo": "1"}, {"model": "1"}, {"x": 1}
    )
    await store.save_transition_plan("t", "a", "b", "c", "e", {"bars": 8})
    await store.save_set_plan("s", "c", {"tracks": [1, 2]})
    await store.save_execution_manifest("m", {"seed": 7})

    assert (await store.get_analysis_snapshot("a"))["payload"] == {"x": 1}
    assert (await store.get_transition_plan("t"))["plan"] == {"bars": 8}
    assert (await store.get_set_plan("s"))["plan"] == {"tracks": [1, 2]}
    assert (await store.get_execution_manifest("m"))["manifest"] == {"seed": 7}


async def test_store_is_idempotent_on_identity(session: AsyncSession) -> None:
    await _create_tables(session)
    store = EngineContractStore(session)

    await store.save_set_plan("same", "c1", {"tracks": [1]})
    await store.save_set_plan("same", "c2", {"tracks": [2]})

    row = await store.get_set_plan("same")
    assert row["config_identity"] == "c2"
    assert row["plan"] == {"tracks": [2]}


async def test_store_round_trips_shadow_comparison_and_is_idempotent(
    session: AsyncSession,
) -> None:
    await _create_tables(session)
    await session.execute(
        text("""
        CREATE TABLE shadow_comparisons (
            comparison_identity VARCHAR(64) PRIMARY KEY,
            execution_identity VARCHAR(64) NOT NULL,
            comparison JSON NOT NULL
        )
    """)
    )
    await session.commit()
    store = EngineContractStore(session)

    payload = {"score_delta": 0.125, "recipe_parity": False}
    await store.save_shadow_comparison("shadow-id", "execution-id", payload)
    await store.save_shadow_comparison("shadow-id", "execution-id-2", {"score_delta": 0.25})

    row = await store.get_shadow_comparison("shadow-id")
    assert row["execution_identity"] == "execution-id-2"
    assert row["comparison"] == {"score_delta": 0.25}

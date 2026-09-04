from pathlib import Path

MIGRATION = Path(__file__).parents[2] / "app/db/migrations/versions/0004_universal_engine_contracts.py"


def test_universal_engine_migration_is_additive() -> None:
    text = MIGRATION.read_text()
    for table in ("analysis_snapshots", "transition_plans", "set_plans", "execution_manifests"):
        assert f'"{table}"' in text
    assert 'op.drop_table("tracks")' not in text
    assert "down_revision: str | None = \"0003\"" in text

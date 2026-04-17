"""Sanity: migration module imports + lists 15+2 tables (15 unique + labels pair)."""

from __future__ import annotations

import importlib
import pathlib


def test_migration_imports() -> None:
    path = next(pathlib.Path("app/db/migrations/versions").glob("*p2_drop_dead*.py"))
    module_name = f"app.db.migrations.versions.{path.stem}"
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert hasattr(mod, "DEAD_TABLES")
    assert len(mod.DEAD_TABLES) == 17  # 15 unique + labels + track_labels counted
    assert "spotify_metadata" in mod.DEAD_TABLES
    assert "app_exports" in mod.DEAD_TABLES

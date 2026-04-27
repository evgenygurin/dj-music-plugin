"""Audit iter 34 (T-32): every entity's ``sortable_fields`` must
correspond to a real column on the SQLAlchemy model.

Iter 34 caught ``track`` rejecting sort by ``created_at`` and
``audio_file`` rejecting sort by ``track_id`` even though both
columns clearly exist on the underlying tables. The sortable_fields
allowlist had been hand-curated and never updated as columns were
added.

This test walks every registered entity and asserts every name in
``sortable_fields`` is a real attribute on the model. Future drift
fails CI immediately. The reverse direction (every model column
must be sortable) is intentionally NOT enforced - JSON columns,
internal bookkeeping, etc. should stay opt-in.
"""

from __future__ import annotations

import pytest

from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry


def _all_entity_names() -> list[str]:
    EntityRegistry.clear()
    register_default_entities()
    names = sorted(EntityRegistry._registry.keys())
    EntityRegistry.clear()
    return names


@pytest.fixture(autouse=True)
def _registered() -> None:
    EntityRegistry.clear()
    register_default_entities()
    yield
    EntityRegistry.clear()


@pytest.mark.parametrize("entity", _all_entity_names())
def test_every_sortable_field_is_a_real_model_column(entity: str) -> None:
    cfg = EntityRegistry.get(entity)
    missing: list[str] = []
    for field in cfg.sortable_fields:
        if not hasattr(cfg.model, field):
            missing.append(field)
    assert not missing, (
        f"{entity}.sortable_fields lists names not present on {cfg.model.__name__}: {missing}"
    )

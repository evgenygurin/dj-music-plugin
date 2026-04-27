"""Audit iter 32: regression guard against ``filterable_fields`` drift.

Each ``EntityConfig`` advertises ``filterable_fields`` (a summary
mapping consumed by ``schema://entities/{entity}``) AND a
``filter_schema`` (Pydantic class with the actual lookup field set).
The two are hand-curated, so they drift apart - v1.2.8 caught
``track_features`` / ``track_feedback`` out of sync; iter 32 caught
``transition_history`` similarly stale.

This test walks every registered entity and asserts that every
``__<lookup>`` field declared on the filter schema appears in the
``filterable_fields`` summary. Drift now fails CI.

Direction is one-way: ``filter_schema`` is the source of truth (it's
what the dispatcher actually validates against). ``filterable_fields``
is the human-readable summary; it's allowed to be a SUBSET as long as
every lookup it advertises is real, but iter 32 chooses to enforce
parity to prevent accidental hide-from-introspection.
"""

from __future__ import annotations

import pytest

from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry


def _all_entity_names() -> list[str]:
    """Collect entity names with the registry populated.

    Called at parametrize-collection time, so we register here. The
    autouse fixture clears + re-registers per test for isolation.
    """
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


def _lookups_from_filter_schema(filter_schema: type) -> set[tuple[str, str]]:
    """Extract ``(field, op)`` pairs from a Pydantic Filter class."""
    pairs: set[tuple[str, str]] = set()
    for name in filter_schema.model_fields:
        if "__" in name:
            field, op = name.rsplit("__", 1)
            pairs.add((field, op))
        else:
            # Bare field (e.g. ``has_features`` magic) - count as ``eq``.
            pairs.add((name, "eq"))
    return pairs


def _lookups_from_filterable_fields(
    filterable_fields: dict[str, tuple[str, ...]],
) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for field, ops in filterable_fields.items():
        for op in ops:
            pairs.add((field, op))
    return pairs


@pytest.mark.parametrize("entity", _all_entity_names())
def test_filterable_fields_match_filter_schema(entity: str) -> None:
    cfg = EntityRegistry.get(entity)
    schema_pairs = _lookups_from_filter_schema(cfg.filter_schema)
    summary_pairs = _lookups_from_filterable_fields(dict(cfg.filterable_fields))
    # Every (field, op) declared on the filter schema must be advertised
    # by ``filterable_fields`` so introspection clients see the real
    # contract. Bare-field magics (``has_features``) get tagged "eq".
    missing_in_summary = schema_pairs - summary_pairs
    # Allow a small set of "internal-only" lookups that aren't worth
    # advertising on the summary - none right now, but future
    # entries can be added here.
    allowed_missing: set[tuple[str, str]] = set()
    real_missing = missing_in_summary - allowed_missing
    assert not real_missing, (
        f"{entity}.filterable_fields out of sync with filter_schema. "
        f"Missing from summary: {sorted(real_missing)}"
    )

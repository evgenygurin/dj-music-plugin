"""Audit iter 26 (T-26): ``entity_update(set, {template_name: 'bogus'})``
silently accepted the bogus template name. ``entity_create`` already
validates this (v1.2.16); update path was missing the same check.

Schema validation alone can't catch it because schemas can't import
``app.domain``; the dispatcher mirrors the v1.2.16 create-side
validation here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry
from app.shared.errors import ValidationError


@pytest.fixture(autouse=True)
def _registered() -> None:
    EntityRegistry.clear()
    register_default_entities()
    yield
    EntityRegistry.clear()


@pytest.mark.asyncio
async def test_update_set_template_name_validated() -> None:
    """Calling the dispatcher with a bogus template_name must raise
    ValidationError before reaching the repo."""
    from app.tools.entity.update import entity_update

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.update = AsyncMock()

    with pytest.raises(ValidationError, match=r"unknown template_name 'bogus_xyz'"):
        await entity_update(
            entity="set",
            id=1,
            data={"template_name": "bogus_xyz"},
            uow=uow,
            registry=MagicMock(),
            pipeline=MagicMock(),
            scorer=MagicMock(),
        )
    uow.sets.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_set_known_template_name_accepted() -> None:
    """Sanity: a registered template name passes through to the repo."""
    from app.tools.entity.update import entity_update

    # MagicMock treats ``name=`` as the mock's identity, not as an
    # attribute - configure the SetView fields explicitly.
    fake_row = MagicMock()
    fake_row.id = 1
    fake_row.name = "X"
    fake_row.description = None
    fake_row.target_duration_ms = None
    fake_row.target_bpm_min = None
    fake_row.target_bpm_max = None
    fake_row.template_name = "classic_60"
    fake_row.source_playlist_id = None
    fake_row.version_count = None
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.update = AsyncMock(return_value=fake_row)
    # Audit iter 49 (T-47): the update dispatcher now runs view_enricher,
    # which on the set entity calls ``uow.sets.version_count(id)``.
    uow.sets.version_count = AsyncMock(return_value=0)

    result = await entity_update(
        entity="set",
        id=1,
        data={"template_name": "classic_60"},
        uow=uow,
        registry=MagicMock(),
        pipeline=MagicMock(),
        scorer=MagicMock(),
    )
    assert result.data["template_name"] == "classic_60"

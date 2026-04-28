"""Audit iter 58 (T-56): ``local://sets/{id}/versions/compare/{a}/{b}``
had three issues:

1. Same-version compare (``a == b``) returned a trivial
   ``delta=0, changed_positions=[]`` row — not a comparison.
2. Cross-set ids leaked a misleading ``set_version not found: 3``
   when version 3 existed but in a different set.
3. ``zip(items_a, items_b, strict=False)`` silently dropped tail
   positions when versions had different lengths.

Live confirmation:

    /sets/5/versions/compare/6/6 -> {"delta":0,"changed_positions":[]}  ← trivial
    /sets/5/versions/compare/3/7 -> "set_version not found: 3"          ← misleading
    (zip-truncate) -> tail differences silently dropped

Now:
- Same-version → ValidationError with explicit message
- Cross-set    → NotFoundError mentions the actual set mismatch
- Different lengths → tail positions counted as changed
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.set import set_versions_compare
from app.shared.errors import NotFoundError, ValidationError


def _ver(version_id: int, set_id: int, quality: float = 0.5) -> MagicMock:
    v = MagicMock()
    v.id = version_id
    v.set_id = set_id
    v.quality_score = quality
    return v


def _item(track_id: int, sort_index: int) -> MagicMock:
    item = MagicMock()
    item.track_id = track_id
    item.sort_index = sort_index
    return item


@pytest.mark.asyncio
async def test_same_version_rejected() -> None:
    uow = MagicMock()
    uow.set_versions = MagicMock()
    uow.set_versions.get = AsyncMock(return_value=_ver(6, 5))
    with pytest.raises(ValidationError, match=r"two distinct version ids"):
        await set_versions_compare(id=5, a=6, b=6, uow=uow)


@pytest.mark.asyncio
async def test_cross_set_id_surfaces_actual_set() -> None:
    """Version 3 exists but in set 4 — error names the mismatch."""
    uow = MagicMock()
    uow.set_versions = MagicMock()
    # Version 3 lives in set 4; caller asked /sets/5/versions/compare/3/7.
    uow.set_versions.get = AsyncMock(side_effect=[_ver(3, 4), _ver(7, 5)])
    with pytest.raises(NotFoundError, match=r"belongs to set 4, not 5"):
        await set_versions_compare(id=5, a=3, b=7, uow=uow)


@pytest.mark.asyncio
async def test_unknown_version_still_clean_not_found() -> None:
    uow = MagicMock()
    uow.set_versions = MagicMock()
    uow.set_versions.get = AsyncMock(side_effect=[None, _ver(7, 5)])
    with pytest.raises(NotFoundError, match=r"set_version not found: 99999"):
        await set_versions_compare(id=5, a=99999, b=7, uow=uow)


@pytest.mark.asyncio
async def test_different_length_versions_count_tail_differences() -> None:
    """Version A: [101, 102]; Version B: [101, 102, 103, 104].
    Old code (zip strict=False) → changed=[]. New code → changed=[3, 4]."""
    uow = MagicMock()
    uow.set_versions = MagicMock()
    uow.set_versions.get = AsyncMock(side_effect=[_ver(6, 5, 0.5), _ver(7, 5, 0.7)])
    items_a = [_item(101, 0), _item(102, 1)]
    items_b = [_item(101, 0), _item(102, 1), _item(103, 2), _item(104, 3)]
    uow.set_versions.get_items = AsyncMock(side_effect=[items_a, items_b])

    payload_str = await set_versions_compare(id=5, a=6, b=7, uow=uow)
    payload = json.loads(payload_str)
    assert payload["changed_positions"] == [3, 4]


@pytest.mark.asyncio
async def test_distinct_versions_same_set_runs_normally() -> None:
    uow = MagicMock()
    uow.set_versions = MagicMock()
    uow.set_versions.get = AsyncMock(side_effect=[_ver(6, 5, 0.5), _ver(7, 5, 0.7)])
    items_a = [_item(101, 0), _item(102, 1), _item(103, 2)]
    items_b = [_item(101, 0), _item(999, 1), _item(103, 2)]  # pos 2 differs
    uow.set_versions.get_items = AsyncMock(side_effect=[items_a, items_b])

    payload_str = await set_versions_compare(id=5, a=6, b=7, uow=uow)
    payload = json.loads(payload_str)
    assert payload["changed_positions"] == [2]
    assert payload["delta"] == pytest.approx(0.2)

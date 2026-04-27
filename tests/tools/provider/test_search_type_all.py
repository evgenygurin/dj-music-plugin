"""Audit iter 20 (T-21): ``provider_search(type='all')`` silently
returned empty regardless of the query because the parser read
``raw.get('results')`` while YM returns a sectioned shape
``{tracks: {...}, albums: {...}, artists: {...}, playlists: {...}}``.

Now ``type='all'`` aggregates items across every section and tags
each item with ``_section`` so callers can disambiguate which
section each row came from.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.provider.search import provider_search


def _registry_with(adapter: object) -> object:
    registry = MagicMock()
    registry.get = MagicMock(return_value=adapter)
    return registry


@pytest.mark.asyncio
async def test_search_type_all_aggregates_across_sections() -> None:
    adapter = MagicMock()
    adapter.search = AsyncMock(
        return_value={
            "tracks": {
                "results": [{"id": "t1", "title": "T1"}, {"id": "t2", "title": "T2"}],
                "total": 100,
            },
            "albums": {
                "results": [{"id": "a1", "title": "A1"}],
                "total": 50,
            },
            "artists": {
                "results": [{"id": "ar1", "name": "Ar1"}],
                "total": 25,
            },
            "playlists": {"results": [], "total": 0},
        }
    )
    result = await provider_search(
        provider="yandex",
        query="techno",
        type="all",
        limit=10,
        registry=_registry_with(adapter),
    )
    # Aggregate item count
    assert len(result.items) == 4  # 2 + 1 + 1 + 0
    assert result.total == 175  # 100 + 50 + 25 + 0
    # Each item is tagged with its section
    sections = {item.get("_section") for item in result.items}
    assert sections == {"tracks", "albums", "artists"}


@pytest.mark.asyncio
async def test_search_type_tracks_unchanged() -> None:
    """Sanity: type='tracks' still picks the single section."""
    adapter = MagicMock()
    adapter.search = AsyncMock(
        return_value={
            "tracks": {
                "results": [{"id": "t1", "title": "T1"}],
                "total": 100,
            }
        }
    )
    result = await provider_search(
        provider="yandex",
        query="techno",
        type="tracks",
        limit=10,
        registry=_registry_with(adapter),
    )
    assert len(result.items) == 1
    assert result.total == 100


@pytest.mark.asyncio
async def test_search_type_all_empty_response() -> None:
    """Empty sections produce empty result, not crash."""
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value={})
    result = await provider_search(
        provider="yandex",
        query="x",
        type="all",
        limit=10,
        registry=_registry_with(adapter),
    )
    assert result.items == []
    assert result.total == 0

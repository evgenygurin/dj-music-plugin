"""Tests for EntityResolver with elicitation."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.entity_resolver import EntityMatch, EntityResolver, parse_entity_ref


@dataclass
class MockTrack:
    """Mock track entity for testing."""

    id: int
    title: str
    ym_id: str | None = None


class MockElicitResult:
    """Mock ElicitResult for testing."""

    def __init__(self, action: str, data=None):
        self.action = action
        self.data = data


@pytest.fixture
def mock_ctx():
    """Create mock FastMCP context."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.elicit = AsyncMock()
    return ctx


@pytest.fixture
def sample_tracks():
    """Sample track data."""
    return [
        MockTrack(id=1, title="Aphex Twin - Windowlicker", ym_id="ym123"),
        MockTrack(id=2, title="Aphex Twin - Come To Daddy", ym_id="ym456"),
        MockTrack(id=3, title="Aphex Twin - Alberto Balsalm", ym_id="ym789"),
        MockTrack(id=4, title="Autechre - Eutow", ym_id=None),
    ]


@pytest.fixture
def resolver(sample_tracks):
    """Create EntityResolver with mock data."""

    async def get_by_id(track_id: int):
        for t in sample_tracks:
            if t.id == track_id:
                return t
        return None

    async def get_by_ym_id(ym_id: str):
        for t in sample_tracks:
            if t.ym_id == ym_id:
                return t
        return None

    async def search_by_query(query: str):
        matches = []
        query_lower = query.lower()
        for t in sample_tracks:
            if query_lower in t.title.lower():
                # Simple relevance scoring based on position
                score = 1.0 if t.title.lower().startswith(query_lower) else 0.7
                matches.append(EntityMatch(entity=t, score=score, match_field="title"))
        return matches

    return EntityResolver(
        get_by_id=get_by_id,
        get_by_ym_id=get_by_ym_id,
        search_by_query=search_by_query,
        get_display_name=lambda t: t.title,
    )


def test_parse_entity_ref_int_id():
    """Test parsing integer ID."""
    ref = parse_entity_ref(42)
    assert ref.type == "id"
    assert ref.value == 42


@pytest.mark.asyncio
async def test_resolve_by_exact_id(resolver):
    """Test resolving by exact numeric ID."""
    result = await resolver.resolve(1)

    assert result is not None
    assert result.entity.id == 1
    assert result.confidence == 1.0
    assert result.resolution_method == "exact_id"

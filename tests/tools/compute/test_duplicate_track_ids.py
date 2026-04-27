"""Audit iter 3: ``transition_score_pool`` and ``sequence_optimize``
disagreed on duplicate ``track_ids`` semantics.

Live MCP probe with ``track_ids=[146, 146, 147]``:

* ``transition_score_pool`` returned 4 directional pairs - duplicates
  treated as distinct slots in a multiset.
* ``sequence_optimize`` silently deduped to 2 unique tracks and
  returned a 2-track order - the caller had no way to know their
  third "track" was dropped.

Two compute tools that should share input semantics returned different
shapes for the same call. Tighten both to reject duplicates explicitly
- DJ sets don't have the same track in the pool twice in practice,
and silent dedupe loses information either way.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError
from app.tools.compute.score_pool import transition_score_pool
from app.tools.compute.sequence_optimize import sequence_optimize


def _mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    return uow


@pytest.mark.asyncio
async def test_transition_score_pool_rejects_duplicate_track_ids() -> None:
    with pytest.raises(ValidationError, match=r"duplicate"):
        await transition_score_pool(
            track_ids=[146, 146, 147],
            uow=_mock_uow(),
            scorer=MagicMock(),
        )


@pytest.mark.asyncio
async def test_sequence_optimize_rejects_duplicate_track_ids() -> None:
    with pytest.raises(ValidationError, match=r"duplicate"):
        await sequence_optimize(
            track_ids=[146, 146, 147],
            algorithm="greedy",
            uow=_mock_uow(),
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )


@pytest.mark.asyncio
async def test_transition_score_pool_accepts_unique_ids() -> None:
    """Sanity: unique ids still pass through to the scorer (which we
    mock to return empty pairs)."""
    uow = _mock_uow()
    result = await transition_score_pool(
        track_ids=[146, 147, 148],
        uow=uow,
        scorer=MagicMock(score_pool=MagicMock(return_value=[])),
    )
    assert result.track_ids == [146, 147, 148]

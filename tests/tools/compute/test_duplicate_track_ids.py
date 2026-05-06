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
    """Sanity: unique ids still pass through to the scorer.

    Audit iter 44 (T-42): updated to also seed mock features for the
    ids — the prior mock returned ``{}`` and silently produced
    ``pairs=[]`` regardless of input. With the new
    ``missing_track_ids`` guard, an empty feature batch raises
    ``ValidationError`` for pools of size >= 2.
    """
    from app.shared.features import TrackFeatures

    feats = {
        146: TrackFeatures(bpm=128.0),
        147: TrackFeatures(bpm=129.0),
        148: TrackFeatures(bpm=130.0),
    }
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    # Mock the scorer to return non-rejecting score; ctx.report_progress is awaited.
    score = MagicMock(
        hard_reject=False,
        overall=0.7,
        bpm=0.9,
        harmonics=0.8,
        energy=0.7,
        bass=0.6,
        drums=0.5,
        vocals=0.4,
    )
    scorer = MagicMock()
    scorer.score = MagicMock(return_value=score)
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    result = await transition_score_pool(
        track_ids=[146, 147, 148],
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )
    assert result.track_ids == [146, 147, 148]
    assert result.missing_track_ids == []
    # 3 ids → 6 directed pairs (N*(N-1))
    assert len(result.pairs) == 6


@pytest.mark.asyncio
async def test_transition_score_pool_raises_when_no_features() -> None:
    """Audit iter 44 (T-42): empty feature batch on a non-trivial pool
    used to return ``pairs=[]`` silently — caller couldn't tell typo
    apart from "tracks aren't analysed yet"."""
    uow = _mock_uow()
    with pytest.raises(ValidationError, match=r"none of the .* track_ids"):
        await transition_score_pool(
            track_ids=[99999, 99998],
            uow=uow,
            scorer=MagicMock(),
        )


@pytest.mark.asyncio
async def test_transition_score_pool_reports_partial_missing() -> None:
    """When SOME ids have features and SOME don't, return pairs for
    the valid set + ``missing_track_ids`` for the rest."""
    from app.shared.features import TrackFeatures

    feats = {
        146: TrackFeatures(bpm=128.0),
        147: TrackFeatures(bpm=129.0),
    }
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    score = MagicMock(
        hard_reject=False,
        overall=0.7,
        bpm=0.9,
        harmonics=0.8,
        energy=0.7,
        bass=0.6,
        drums=0.5,
        vocals=0.4,
    )
    scorer = MagicMock()
    scorer.score = MagicMock(return_value=score)
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    result = await transition_score_pool(
        track_ids=[146, 147, 99999],  # last one missing
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )
    assert result.missing_track_ids == [99999]
    # 2 valid ids → 2 directed pairs (146→147, 147→146)
    assert len(result.pairs) == 2

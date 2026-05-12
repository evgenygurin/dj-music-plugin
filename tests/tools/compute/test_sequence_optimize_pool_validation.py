"""Regressions for the round-4 manual-test findings on ``sequence_optimize``.

Both checks used to be silently no-op:

* ``pinned=[id_not_in_track_ids]`` — the optimizer just ignored the
  pinning intent, so the caller got a "successful" reorder that
  silently dropped their must-include constraint.
* ``excluded`` covering the entire pool — returned ``track_order=[]``
  with ``quality_score=0``, a valid-looking response for a logically
  contradictory request.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError
from app.tools.compute.sequence_optimize import sequence_optimize


def _feat() -> MagicMock:
    f = MagicMock()
    f.bpm = 128.0
    f.energy_mean = 0.7
    return f


def _uow_with_features(track_ids: list[int]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    feats = {tid: _feat() for tid in track_ids}
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


@pytest.mark.asyncio
async def test_pinned_id_outside_pool_rejected() -> None:
    uow = _uow_with_features([1, 2, 3, 4])
    scorer = MagicMock()
    ctx = MagicMock()
    with pytest.raises(ValidationError, match="pinned track_ids not in pool"):
        await sequence_optimize(
            track_ids=[1, 2, 3, 4],
            algorithm="greedy",
            pinned=[99],
            uow=uow,
            scorer=scorer,
            ctx=ctx,
        )


@pytest.mark.asyncio
async def test_excluded_covers_entire_pool_rejected() -> None:
    uow = _uow_with_features([1, 2, 3])
    scorer = MagicMock()
    ctx = MagicMock()
    with pytest.raises(ValidationError, match=r"only \d+ track"):
        await sequence_optimize(
            track_ids=[1, 2, 3],
            algorithm="greedy",
            excluded=[1, 2, 3],
            uow=uow,
            scorer=scorer,
            ctx=ctx,
        )


@pytest.mark.asyncio
async def test_excluded_leaves_one_track_rejected() -> None:
    """Boundary: 1 surviving track is still < 2, so the optimizer has
    nothing to optimize against — reject up front instead of returning
    a single-track "result"."""
    uow = _uow_with_features([1, 2, 3])
    scorer = MagicMock()
    ctx = MagicMock()
    with pytest.raises(ValidationError, match=r"only 1 track"):
        await sequence_optimize(
            track_ids=[1, 2, 3],
            algorithm="greedy",
            excluded=[2, 3],
            uow=uow,
            scorer=scorer,
            ctx=ctx,
        )


@pytest.mark.asyncio
async def test_pinned_valid_subset_passes_orphan_guard() -> None:
    """Sanity: the new orphan guard fires BEFORE feature lookup, so we
    only need to verify it does NOT raise on a valid pinning subset.
    Anything that fails after the guard (feature schema, optimizer math
    on mocked scores) is irrelevant to this regression's contract.
    """
    uow = _uow_with_features([1, 2, 3, 4])
    scorer = MagicMock()
    score = MagicMock(overall=0.8)
    scorer.score = MagicMock(return_value=score)
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    with pytest.raises(Exception) as info:
        await sequence_optimize(
            track_ids=[1, 2, 3, 4],
            algorithm="greedy",
            pinned=[1],
            uow=uow,
            scorer=scorer,
            ctx=ctx,
        )
    # Whatever blows up downstream is fine — what matters is that the
    # orphan guard didn't reject ``pinned=[1]`` (a valid subset).
    assert "pinned track_ids not in pool" not in str(info.value)

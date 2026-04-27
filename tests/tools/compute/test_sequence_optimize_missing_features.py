"""Audit iter 48 (T-46): ``sequence_optimize`` crashed with
``'NoneType' object has no attribute 'integrated_lufs'`` when the
caller passed track_ids whose features weren't loaded. Same drift
class as T-42 on ``transition_score_pool`` — silent input went
straight to the GA / greedy fitness function and crashed
mid-computation.

Live confirmation:

    sequence_optimize(track_ids=[99999, 99998])
    -> 'NoneType' object has no attribute 'integrated_lufs'

Now:
- ALL ids missing → typed ValidationError (caller gets the missing
  id list explicitly).
- Partial pool with ≥ 2 valid ids → drop the dead ones and run the
  optimizer on the valid subset.
- Partial pool with < 2 valid ids → ValidationError (need at least
  2 to optimize).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError
from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


@pytest.mark.asyncio
async def test_all_missing_raises_validation_error() -> None:
    """Pure typo / un-analysed library → fail loud."""
    uow = _uow_with_features({})
    with pytest.raises(ValidationError, match=r"none of the .* track_ids"):
        await sequence_optimize(
            track_ids=[99999, 99998],
            algorithm="greedy",
            uow=uow,
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )


@pytest.mark.asyncio
async def test_partial_missing_drops_dead_ids() -> None:
    """``[146, 147, 99999]`` → run on ``[146, 147]`` only."""
    feats = {
        146: TrackFeatures(bpm=128.0),
        147: TrackFeatures(bpm=129.0),
    }
    uow = _uow_with_features(feats)

    captured: dict[str, object] = {}

    def fake_optimizer_builder(*, algorithm: str, scorer: object) -> object:
        result = MagicMock()
        result.track_order = [146, 147]
        result.quality_score = 0.7
        result.generations = 0

        def _optimize(**kwargs: object) -> object:
            captured.update(kwargs)
            return result

        return MagicMock(optimize=_optimize)

    out = await sequence_optimize(
        track_ids=[146, 147, 99999],
        algorithm="greedy",
        uow=uow,
        scorer=MagicMock(),
        optimizer_builder=fake_optimizer_builder,
    )
    # The optimizer received only the valid 2 ids — no None features.
    assert captured["track_ids"] == [146, 147]
    assert all(f is not None for f in captured["tracks"])  # type: ignore[union-attr]
    assert out.track_order == [146, 147]


@pytest.mark.asyncio
async def test_only_one_valid_id_raises() -> None:
    """1 valid + 1 missing → can't optimize 2-track pair → fail."""
    feats = {146: TrackFeatures(bpm=128.0)}
    uow = _uow_with_features(feats)

    with pytest.raises(ValidationError, match=r"only 1 of the 2"):
        await sequence_optimize(
            track_ids=[146, 99999],
            algorithm="greedy",
            uow=uow,
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )

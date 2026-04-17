"""TransitionPersistHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.handlers.transition_persist import transition_persist_handler
from app.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    return MagicMock(spec=Context)


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock()}
    )
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=10))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.82
    score.bpm = 0.9
    score.harmonic = 0.8
    score.energy = 0.75
    score.spectral = 0.85
    score.groove = 0.78
    score.timbral = 0.82
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_scores_and_persists_pair(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)

    assert result["from_track_id"] == 1
    assert result["to_track_id"] == 2
    assert result["overall"] == pytest.approx(0.82)
    uow.transitions.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_features_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.track_features.get_scoring_features_batch.return_value = {1: MagicMock()}
    data = {"from_track_id": 1, "to_track_id": 2}
    with pytest.raises(NotFoundError):
        await transition_persist_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_hard_reject_is_persisted_with_zero_overall(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    rejected = MagicMock()
    rejected.overall = 0.0
    rejected.hard_reject = True
    rejected.reject_reason = "bpm_diff>10"
    rejected.bpm = rejected.harmonic = rejected.energy = 0.0
    rejected.spectral = rejected.groove = rejected.timbral = 0.0
    scorer.score.return_value = rejected

    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    assert result["hard_reject"] is True
    assert result["overall"] == 0.0
    uow.transitions.upsert.assert_awaited_once()

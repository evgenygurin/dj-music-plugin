"""Regression: ``transition_persist`` must honour ``persist=False``.

``TransitionCreate.persist`` defaults to ``True`` but is overridable.
Before this fix the handler always called ``persist_transition_score``
regardless of the flag, so ``persist=False`` was a silent no-op — the
caller's intent ("compute score, return it, don't touch the
transitions table") was dropped. Same dead-parameter pattern as
``scoring_profile`` (commit f589160) and ``include_relations``
(commit a7c06ae).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.handlers.transition_persist import transition_persist_handler


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
    u.transitions = MagicMock(spec=["upsert", "get_pair", "create", "update"])
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=10))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock(
        overall=0.82,
        bpm=0.9,
        harmonics=0.8,
        energy=0.75,
        bass=0.85,
        drums=0.78,
        vocals=0.82,
        hard_reject=False,
        reject_reason=None,
    )
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_persist_false_skips_db_write(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    data = {"from_track_id": 1, "to_track_id": 2, "persist": False}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    # Score still computed and returned…
    assert result["overall"] == pytest.approx(0.82)
    # …but the upsert never fired and the response says so explicitly.
    uow.transitions.upsert.assert_not_called()
    assert result["persisted"] is False
    assert result["id"] is None


@pytest.mark.asyncio
async def test_persist_default_true_writes(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """Sanity: omitting ``persist`` still triggers the upsert (default True)."""
    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    uow.transitions.upsert.assert_awaited_once()
    assert result["persisted"] is True
    assert result["id"] == 10


@pytest.mark.asyncio
async def test_persist_true_explicit_writes(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    data = {"from_track_id": 1, "to_track_id": 2, "persist": True}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    uow.transitions.upsert.assert_awaited_once()
    assert result["persisted"] is True

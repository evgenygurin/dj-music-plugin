"""SetVersionBuildHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.server.context import Context

from app.handlers.set_version_build import set_version_build_handler
from app.shared.errors import NotFoundError, ValidationError


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def session_spy() -> MagicMock:
    s = MagicMock()
    s.flush = AsyncMock()
    return s


@pytest.fixture
def uow(session_spy: MagicMock) -> MagicMock:
    u = MagicMock()
    u.session = session_spy
    u.sets = MagicMock()
    u.sets.get = AsyncMock()
    u.set_versions = MagicMock()
    u.set_versions.create = AsyncMock(return_value=MagicMock(id=10, label="v1", quality_score=0.0))
    u.set_versions.create_items = AsyncMock(return_value=3)
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    )
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=42))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.8
    score.bpm = score.harmonic = score.energy = 0.8
    score.spectral = score.groove = score.timbral = 0.8
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_builds_version_with_items(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="Test")
    data = {
        "set_id": 5,
        "track_order": [1, 2, 3],
        "label": "v1",
        "generator_run_meta": {"algo": "ga"},
    }

    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        result = await set_version_build_handler(ctx, uow, data)

    assert result["version_id"] == 10
    assert result["item_count"] == 3
    assert result["transition_count"] == 2  # N-1 transitions for N tracks
    uow.set_versions.create_items.assert_awaited_once_with(version_id=10, track_order=[1, 2, 3])
    # transitions persisted: N-1 upserts with directed pair fields
    assert uow.transitions.upsert.await_count == 2
    pairs = [
        (c.kwargs["from_track_id"], c.kwargs["to_track_id"])
        for c in uow.transitions.upsert.await_args_list
    ]
    assert pairs == [(1, 2), (2, 3)]


@pytest.mark.asyncio
async def test_unknown_set_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = None
    data = {"set_id": 999, "track_order": [1, 2]}
    with pytest.raises(NotFoundError):
        await set_version_build_handler(ctx, uow, data)


@pytest.mark.asyncio
async def test_empty_track_order_raises_validation(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": []}
    with pytest.raises(ValidationError):
        await set_version_build_handler(ctx, uow, data)


@pytest.mark.asyncio
async def test_quality_score_averaged(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="S")
    data = {"set_id": 5, "track_order": [1, 2, 3]}

    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        result = await set_version_build_handler(ctx, uow, data)

    # 2 transitions, each overall=0.8 → avg 0.8
    assert result["quality_score"] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_builds_without_scorer_when_lifespan_missing(ctx: MagicMock, uow: MagicMock) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="S")
    data = {"set_id": 5, "track_order": [1, 2, 3]}

    with patch(
        "app.server.di.get_transition_scorer",
        AsyncMock(side_effect=RuntimeError("TransitionScorer not initialized")),
    ):
        result = await set_version_build_handler(ctx, uow, data)

    assert result["transition_count"] == 0
    assert result["quality_score"] == 0.0

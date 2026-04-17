"""SetVersionBuildHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.set_version_build import set_version_build_handler
from app.v2.shared.errors import NotFoundError, ValidationError


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.sets = MagicMock()
    u.sets.get = AsyncMock()
    u.set_versions = MagicMock()
    u.set_versions.create = AsyncMock(return_value=MagicMock(id=10, label="v1"))
    u.set_versions.add_item = AsyncMock()
    u.set_versions.update_quality = AsyncMock()
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=100))
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    )
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
    result = await set_version_build_handler(ctx, uow, data, scorer)

    assert result["version_id"] == 10
    assert result["item_count"] == 3
    assert result["transition_count"] == 2  # N-1 transitions for N tracks
    assert uow.set_versions.add_item.await_count == 3
    assert uow.transitions.upsert.await_count == 2


@pytest.mark.asyncio
async def test_unknown_set_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = None
    data = {"set_id": 999, "track_order": [1, 2]}
    with pytest.raises(NotFoundError):
        await set_version_build_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_empty_track_order_raises_validation(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": []}
    with pytest.raises(ValidationError):
        await set_version_build_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_quality_score_averaged(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": [1, 2, 3]}
    result = await set_version_build_handler(ctx, uow, data, scorer)
    # 2 transitions, each overall=0.8 → avg 0.8
    assert result["quality_score"] == pytest.approx(0.8)

"""TrackFeaturesReanalyzeHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.handlers.track_features_reanalyze import track_features_reanalyze_handler
from app.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.get = AsyncMock()
    u.track_features = MagicMock()
    u.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(analysis_level=2))
    u.track_features.upsert = AsyncMock()
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(return_value=MagicMock(file_path="/tmp/x.mp3"))
    return u


@pytest.fixture
def pipeline() -> AsyncMock:
    p = AsyncMock()
    p.analyze.return_value = MagicMock(
    )
    return p


@pytest.mark.asyncio
async def test_reanalyze_single_track(ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock) -> None:
    uow.tracks.get.return_value = MagicMock(id=1)
    data = {"track_id": 1, "level": 4}
    result = await track_features_reanalyze_handler(ctx, uow, data, pipeline)

    assert result["track_id"] == 1
    assert result["level"] == 4
    pipeline.analyze.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_track_raises(ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock) -> None:
    uow.tracks.get.return_value = None
    data = {"track_id": 999, "level": 3}
    with pytest.raises(NotFoundError):
        await track_features_reanalyze_handler(ctx, uow, data, pipeline)


@pytest.mark.asyncio
async def test_always_runs_even_when_current_gte_target(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1)
    uow.track_features.get_by_track_id.return_value = MagicMock(analysis_level=4)
    data = {"track_id": 1, "level": 3}
    await track_features_reanalyze_handler(ctx, uow, data, pipeline)
    pipeline.analyze.assert_awaited_once()

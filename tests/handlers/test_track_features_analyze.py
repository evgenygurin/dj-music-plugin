"""TrackFeaturesAnalyzeHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.handlers.track_features_analyze import track_features_analyze_handler


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    c.report_progress = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.get = AsyncMock()
    u.track_features = MagicMock()
    u.track_features.get_by_track_id = AsyncMock(return_value=None)
    u.track_features.upsert = AsyncMock()
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(return_value=MagicMock(file_path="/tmp/x.mp3"))
    return u


@pytest.fixture
def pipeline() -> AsyncMock:
    p = AsyncMock()
    p.analyze_to_level.return_value = MagicMock(
        features={"bpm": 128.0, "key_code": 5, "integrated_lufs": -9.0},
        pipeline_run_id=1,
        analysis_level=3,
        sections=[],
        errors=[],
    )
    return p


@pytest.mark.asyncio
async def test_analyzes_unseen_track(ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1], "level": 3}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["analyzed"]) == 1
    assert result["analyzed"][0]["level"] == 3
    pipeline.analyze_to_level.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_tracks_already_at_level(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.track_features.get_by_track_id.return_value = MagicMock(analysis_level=3, bpm=128.0)
    data = {"track_ids": [1], "level": 3, "force": False}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert result["analyzed"] == []
    assert len(result["skipped"]) == 1
    pipeline.analyze_to_level.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_reanalyzes_even_if_higher_level(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.track_features.get_by_track_id.return_value = MagicMock(analysis_level=4, bpm=128.0)
    data = {"track_ids": [1], "level": 3, "force": True}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["analyzed"]) == 1
    pipeline.analyze_to_level.assert_awaited_once()


@pytest.mark.asyncio
async def test_records_error_on_missing_audio_file(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_by_track_id.return_value = None
    data = {"track_ids": [1], "level": 3}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["errors"]) == 1
    assert "audio file" in result["errors"][0]["error"].lower()

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.timeline import build_timeline_overlay


class _Reader:
    def __init__(self, uow: MagicMock) -> None:
        self.uow = uow

    async def get_track_sections(self, track_id: int):
        return await self.uow.track_features.get_track_sections(track_id)

    async def get_beatgrids(self, track_id: int):
        return await self.uow.audio_files.get_beatgrids(track_id)

    async def get_by_track_id(self, track_id: int):
        return await self.uow.track_features.get_by_track_id(track_id)


def _reader() -> MagicMock:
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(return_value=[])
    uow.audio_files.get_beatgrids = AsyncMock(return_value=[])
    uow.track_features.get_by_track_id = AsyncMock(return_value=None)
    return _Reader(uow)


@pytest.mark.asyncio
async def test_build_timeline():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {"section_type": 0, "start_ms": 0, "end_ms": 32000, "energy": 0.3},
            {"section_type": 2, "start_ms": 32000, "end_ms": 96000, "energy": 0.8},
        ]
    )
    uow.audio_files.get_beatgrids = AsyncMock(
        return_value=[MagicMock(canonical=True, first_downbeat_ms=1000.0)]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=135.0))

    result = await build_timeline_overlay(_Reader(uow), [1])
    assert result["tracks"][0]["track_id"] == 1
    assert result["tracks"][0]["first_downbeat_ms"] == 1000.0
    assert result["tracks"][0]["bpm"] == 135.0
    assert len(result["tracks"][0]["sections"]) == 2


@pytest.mark.asyncio
async def test_build_timeline_no_beatgrid():
    reader = _reader()
    result = await build_timeline_overlay(reader, [1])
    assert result["tracks"][0]["first_downbeat_ms"] == 0.0


@pytest.mark.asyncio
async def test_build_timeline_no_features():
    result = await build_timeline_overlay(_reader(), [1])
    assert result["tracks"][0]["bpm"] is None

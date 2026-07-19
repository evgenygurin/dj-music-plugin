from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.loop_finder import find_loops


@pytest.mark.asyncio
async def test_find_loops():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {
                "section_type": 2,
                "start_ms": 32000,
                "end_ms": 64000,
                "energy": 0.8,
                "stem_energy": {"vocals": 0.05, "drums": 0.9},
            },
            {
                "section_type": 3,
                "start_ms": 64000,
                "end_ms": 96000,
                "energy": 0.3,
                "stem_energy": {"vocals": 0.6, "drums": 0.1},
            },
        ]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=128.0))

    result = await find_loops(uow, 1, min_bars=4)
    assert len(result["loops"]) >= 1
    assert result["loops"][0]["loopable"] is True
    assert result["track_id"] == 1
    assert result["bpm"] == 128.0


@pytest.mark.asyncio
async def test_find_loops_exclude_vocals():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {
                "section_type": 2,
                "start_ms": 32000,
                "end_ms": 64000,
                "energy": 0.8,
                "stem_energy": {"vocals": 0.8, "drums": 0.5},
            },
        ]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=120.0))

    result = await find_loops(uow, 1, min_bars=4)
    assert len(result["loops"]) == 0


@pytest.mark.asyncio
async def test_find_loops_bar_range():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {
                "section_type": 2,
                "start_ms": 0,
                "end_ms": 4000,
                "energy": 0.8,
                "stem_energy": {"vocals": 0.05},
            },
            {
                "section_type": 3,
                "start_ms": 4000,
                "end_ms": 32000,
                "energy": 0.9,
                "stem_energy": {"vocals": 0.1},
            },
        ]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=128.0))

    result = await find_loops(uow, 1, min_bars=4, max_bars=16)
    loops = result["loops"]
    assert len(loops) > 0
    for loop in loops:
        assert loop["bars"] >= 4.0
        assert loop["bars"] <= 16.0


@pytest.mark.asyncio
async def test_find_loops_default_bpm():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {
                "section_type": 2,
                "start_ms": 32000,
                "end_ms": 64000,
                "energy": 0.8,
                "stem_energy": {"vocals": 0.05},
            },
        ]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=None)

    result = await find_loops(uow, 1, min_bars=4)
    assert result["bpm"] == 120.0
    assert len(result["loops"]) >= 1


@pytest.mark.asyncio
async def test_find_loops_energy_stability_threshold():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[
            {
                "section_type": 4,
                "start_ms": 32000,
                "end_ms": 64000,
                "energy": 0.3,
                "stem_energy": {"vocals": 0.1},
            },
        ]
    )
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=128.0))

    result = await find_loops(uow, 1, min_bars=4, min_energy_stability=0.5)
    assert len(result["loops"]) == 0

    result2 = await find_loops(uow, 1, min_bars=4, min_energy_stability=0.2)
    assert len(result2["loops"]) == 1

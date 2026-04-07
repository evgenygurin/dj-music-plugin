"""Tests for ym_playlists get_tracks pagination.

Regression for ОШИБКА #1 in ``docs/reports/mcp-tools-test-2026-04-07.md``:
``get_tracks`` had no ``limit``/``offset`` parameters and returned every
track in a 1377-track playlist (~106 KB), exceeding MCP token limits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.ym.models import YMTrack


def _make_tracks(n: int) -> list[YMTrack]:
    return [YMTrack(id=str(i), title=f"Track {i}") for i in range(n)]


@pytest.mark.asyncio
async def test_get_tracks_paginates_with_default_limit() -> None:
    """Default limit must cap output for large playlists."""
    from app.mcp.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    ym_mock.get_playlist_tracks = AsyncMock(return_value=_make_tracks(1377))

    result = await ym_playlists(action="get_tracks", kind=1280, ym=ym_mock)

    assert result["count"] <= 100, (
        f"ОШИБКА #1: default limit must cap output, got {result['count']}"
    )
    assert result["total"] == 1377
    assert result["has_more"] is True
    assert result["offset"] == 0
    assert len(result["track_ids"]) == result["count"]
    assert len(result["tracks"]) == result["count"]


@pytest.mark.asyncio
async def test_get_tracks_explicit_limit_and_offset() -> None:
    """``limit`` and ``offset`` must select a window."""
    from app.mcp.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    ym_mock.get_playlist_tracks = AsyncMock(return_value=_make_tracks(100))

    result = await ym_playlists(
        action="get_tracks",
        kind=1280,
        limit=20,
        offset=40,
        ym=ym_mock,
    )

    assert result["count"] == 20
    assert result["total"] == 100
    assert result["offset"] == 40
    assert result["has_more"] is True
    assert result["track_ids"][0] == "40"
    assert result["track_ids"][-1] == "59"


@pytest.mark.asyncio
async def test_get_tracks_offset_past_end_returns_empty() -> None:
    """Offset beyond total must return empty without errors."""
    from app.mcp.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    ym_mock.get_playlist_tracks = AsyncMock(return_value=_make_tracks(50))

    result = await ym_playlists(
        action="get_tracks",
        kind=1280,
        limit=20,
        offset=100,
        ym=ym_mock,
    )

    assert result["count"] == 0
    assert result["total"] == 50
    assert result["has_more"] is False
    assert result["track_ids"] == []


@pytest.mark.asyncio
async def test_get_tracks_small_playlist_no_pagination() -> None:
    """Small playlists should be returned in full."""
    from app.mcp.tools.yandex.playlists import ym_playlists

    ym_mock = AsyncMock()
    ym_mock.get_playlist_tracks = AsyncMock(return_value=_make_tracks(15))

    result = await ym_playlists(action="get_tracks", kind=1280, ym=ym_mock)

    assert result["count"] == 15
    assert result["total"] == 15
    assert result["has_more"] is False

"""playlist_sync tool metadata tests.

Integration tests via Client(mcp).call_tool() require Phase 5 composition.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.tools.sync import playlist_sync as _mod


def test_tool_module_has_expected_symbols() -> None:
    assert hasattr(_mod, "playlist_sync")
    assert hasattr(_mod, "ConflictResolution")


def test_tool_importable() -> None:
    assert _mod.playlist_sync is not None


@pytest.mark.asyncio
async def test_diff_direction_does_not_double_count_overlap() -> None:
    """Regression: diff direction must only emit ``remote_only`` for IDs that
    don't already exist locally, otherwise overlap is double-counted (once as
    ``local_only`` and once as ``remote_only``).
    """
    # Local playlist has tracks 1 and 2; provider IDs map "a" → 1, "b" → 2.
    item1 = MagicMock()
    item1.track_id = 1
    item2 = MagicMock()
    item2.track_id = 2

    pl = MagicMock()
    pl.platform_ids = '{"yandex": "remote-1"}'
    pl.items = [item1, item2]

    uow = MagicMock()
    uow.playlists = MagicMock()
    uow.playlists.get = AsyncMock(return_value=pl)

    uow.tracks = MagicMock()

    async def _get_provider_id(tid: int, source: str) -> str | None:
        return {1: "a", 2: "b"}.get(tid)

    uow.tracks.get_provider_id = AsyncMock(side_effect=_get_provider_id)
    uow.tracks.batch_get_by_provider_ids = AsyncMock(return_value={})

    provider = AsyncMock()
    provider.read.return_value = {
        "tracks": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "revision": 1,
    }

    registry = MagicMock()
    registry.get.return_value = provider

    ctx = MagicMock(spec=Context)

    result = await _mod.playlist_sync(
        playlist_id=42,
        direction="diff",
        source="yandex",
        uow=uow,
        registry=registry,
        ctx=ctx,
    )

    # Only "c" is remote-only (not in local). "a" and "b" are in both sides
    # — they must NOT show up as remote_only.
    remote_only = [a for a in result.applied if a.get("op") == "remote_only"]
    assert len(remote_only) == 1
    assert remote_only[0]["ext_id"] == "c"

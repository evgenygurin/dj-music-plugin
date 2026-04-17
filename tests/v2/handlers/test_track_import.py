"""TrackImportHandler unit tests (mocked provider + in-mem UoW)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.track_import import track_import_handler


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    c.report_progress = AsyncMock()
    return c


@pytest.fixture
def provider() -> AsyncMock:
    p = AsyncMock()
    p.read.return_value = {
        "id": "12345",
        "title": "Techno Track",
        "artists": [{"id": "a1", "name": "Artist"}],
        "durationMs": 300_000,
        "albums": [{"id": "b1", "title": "Album", "genre": "techno"}],
        "coverUri": "avatars.yandex.net/%%.jpg",
        "explicit": False,
    }
    return p


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.batch_get_by_provider_ids = AsyncMock(return_value={})
    u.tracks.create = AsyncMock(return_value=MagicMock(id=1, title="Techno Track"))
    u.tracks.get = AsyncMock(return_value=MagicMock(id=1, title="Techno Track"))
    u.provider_metadata = MagicMock()
    u.provider_metadata.upsert_yandex = AsyncMock()
    u.provider_metadata.upsert_external_id = AsyncMock()
    u.playlists = MagicMock()
    u.playlists.add_track = AsyncMock()
    return u


@pytest.fixture
def registry(provider: AsyncMock) -> MagicMock:
    r = MagicMock()
    r.get.return_value = provider
    r.default.return_value = provider
    return r


@pytest.mark.asyncio
async def test_import_single_track_from_yandex(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, provider: AsyncMock
) -> None:
    data = {"source": "yandex", "external_ids": ["12345"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert "imported" in result
    assert len(result["imported"]) == 1
    assert result["imported"][0]["external_id"] == "12345"
    provider.read.assert_awaited()
    uow.tracks.create.assert_awaited_once()
    uow.provider_metadata.upsert_yandex.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_skips_existing_by_provider_id(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    existing = MagicMock(id=99, title="Old")
    uow.tracks.batch_get_by_provider_ids.return_value = {"12345": existing}
    data = {"source": "yandex", "external_ids": ["12345"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert result["imported"] == []
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["local_id"] == 99
    uow.tracks.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_adds_to_playlist_when_given(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    data = {"source": "yandex", "external_ids": ["12345"], "playlist_id": 7}
    await track_import_handler(ctx, uow, data, registry)

    uow.playlists.add_track.assert_awaited_once_with(playlist_id=7, track_id=1)


@pytest.mark.asyncio
async def test_import_reports_progress(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    data = {"source": "yandex", "external_ids": ["1", "2", "3"]}
    # First call returns one track metadata, subsequent calls return same template
    await track_import_handler(ctx, uow, data, registry)
    assert ctx.report_progress.await_count >= 1


@pytest.mark.asyncio
async def test_import_id_mapping_includes_all_refs(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    existing = MagicMock(id=99, title="Old")
    uow.tracks.batch_get_by_provider_ids.return_value = {"aaa": existing}
    data = {"source": "yandex", "external_ids": ["aaa", "bbb"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert result["id_mapping"]["aaa"] == 99
    assert result["id_mapping"]["bbb"] == 1

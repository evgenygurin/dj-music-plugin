"""AudioFileDownloadHandler tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.handlers.audio_file_download import audio_file_download_handler


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
    u.provider_metadata = MagicMock()
    u.provider_metadata.get_external_id = AsyncMock(return_value="12345")
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(return_value=None)
    u.audio_files.create = AsyncMock(return_value=MagicMock(id=100))
    return u


@pytest.fixture
def registry(tmp_path: Path) -> MagicMock:
    r = MagicMock()
    provider = AsyncMock()
    target = tmp_path / "12345.mp3"
    target.write_bytes(b"\x00" * 1024)
    provider.download_audio.return_value = target
    r.get.return_value = provider
    return r


@pytest.mark.asyncio
async def test_download_single_track(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1], "source": "yandex", "target_dir": str(tmp_path)}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert len(result["downloaded"]) == 1
    assert result["downloaded"][0]["track_id"] == 1
    uow.audio_files.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_existing_library_item(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_by_track_id.return_value = MagicMock(id=99)
    data = {"track_ids": [1], "source": "yandex", "skip_existing": True}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["downloaded"] == []
    assert len(result["skipped"]) == 1
    registry.get.return_value.download_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_records_error_when_provider_fails(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    registry.get.return_value.download_audio.side_effect = RuntimeError("404")
    data = {"track_ids": [1], "source": "yandex", "target_dir": str(tmp_path)}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["downloaded"] == []
    assert len(result["errors"]) == 1
    assert "404" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_reports_progress_per_track(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1, 2, 3], "source": "yandex", "target_dir": str(tmp_path)}
    await audio_file_download_handler(ctx, uow, data, registry)
    assert ctx.report_progress.await_count == 3

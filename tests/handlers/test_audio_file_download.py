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
    u.tracks.get_provider_id = AsyncMock(return_value="12345")
    u.audio_files = MagicMock()
    u.audio_files.get_for_track = AsyncMock(return_value=None)
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


def test_provider_protocol_download_audio_accepts_dest_kwarg() -> None:
    """Regression: the ``Provider.download_audio`` signature MUST accept a
    ``dest`` keyword argument so the handler's call site type-checks (mypy
    [call-arg] error) and so concrete adapters like YandexAdapter that
    consume ``dest`` are protocol-compatible.
    """
    import inspect

    from app.registry.provider import Provider

    sig = inspect.signature(Provider.download_audio)
    assert "dest" in sig.parameters, (
        "Provider.download_audio must accept a 'dest' keyword for handler "
        "callers that pre-compute the target filename."
    )


@pytest.mark.asyncio
async def test_handler_passes_dest_kwarg_to_provider(
    ctx: MagicMock, uow: MagicMock, tmp_path: Path
) -> None:
    """Runtime regression: the handler must actually forward ``dest`` to the
    provider so concrete adapters can honour the caller's filename choice.
    """
    target = tmp_path / "out.mp3"
    target.write_bytes(b"\x00" * 1024)

    provider = AsyncMock()
    provider.download_audio.return_value = target

    registry = MagicMock()
    registry.get.return_value = provider
    uow.tracks.get.return_value = MagicMock(id=1, title="X")

    data = {"track_ids": [1], "source": "yandex", "target_dir": str(tmp_path)}
    await audio_file_download_handler(ctx, uow, data, registry)

    call = provider.download_audio.await_args
    assert "dest" in call.kwargs, "handler must forward a 'dest' kwarg"


@pytest.mark.asyncio
async def test_skips_existing_library_item(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    on_disk = tmp_path / "existing.mp3"
    on_disk.write_bytes(b"\x00" * 1024)
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_for_track.return_value = MagicMock(id=99, file_path=str(on_disk))
    data = {"track_ids": [1], "source": "yandex", "skip_existing": True}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["downloaded"] == []
    assert len(result["skipped"]) == 1
    registry.get.return_value.download_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_row_with_missing_file_is_redownloaded(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    """Regression: /tmp cleanup deletes MP3s while dj_library_items rows
    survive. ``skip_existing`` used to trust the row alone and skip, leaving
    L5 reanalyze to fail with "audio file not found". A row whose file is
    gone must be re-downloaded and updated in place (no duplicate row).
    """
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_for_track.return_value = MagicMock(
        id=99, file_path=str(tmp_path / "vanished.mp3")
    )
    uow.audio_files.update = AsyncMock(return_value=MagicMock(id=99))
    data = {"track_ids": [1], "source": "yandex", "skip_existing": True}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["skipped"] == []
    assert len(result["downloaded"]) == 1
    assert result["downloaded"][0]["library_item_id"] == 99
    assert result["downloaded"][0]["refreshed_stale_row"] is True
    registry.get.return_value.download_audio.assert_awaited_once()
    uow.audio_files.update.assert_awaited_once()
    uow.audio_files.create.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_accepts_single_track_id_form(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    """``AudioFileCreate`` schema offers ``track_id`` (single) OR ``track_ids``
    (batch). Regression: the handler used to hard-fail with KeyError on
    ``data["track_ids"]`` when a caller passed ``track_id`` per the schema.
    """
    uow.tracks.get.return_value = MagicMock(id=42, title="Single")
    data = {"track_id": 42, "source": "yandex", "target_dir": str(tmp_path)}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert len(result["downloaded"]) == 1
    assert result["downloaded"][0]["track_id"] == 42


@pytest.mark.asyncio
async def test_raises_when_no_track_id_provided(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    """Empty payload now produces a clear ValueError instead of a confusing
    ``KeyError: 'track_ids'`` from a missing handler key access.
    """
    data = {"source": "yandex", "target_dir": str(tmp_path)}
    with pytest.raises(ValueError, match="track_id"):
        await audio_file_download_handler(ctx, uow, data, registry)


@pytest.mark.asyncio
async def test_source_defaults_to_yandex(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    """``source`` is optional now (default ``"yandex"``) — matches schema."""
    uow.tracks.get.return_value = MagicMock(id=7, title="NoSource")
    data = {"track_ids": [7], "target_dir": str(tmp_path)}
    await audio_file_download_handler(ctx, uow, data, registry)
    registry.get.assert_called_with("yandex")

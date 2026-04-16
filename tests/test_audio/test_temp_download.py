from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_temp_download_creates_and_cleans():
    """Temp download should create file, yield path, then delete."""
    from app.audio.temp_download import temp_download_track

    mock_provider = AsyncMock()

    async def fake_download(track_id, dest_path):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"fake mp3 data")
        return 13

    mock_provider.download_track = AsyncMock(side_effect=fake_download)

    saved_path = None
    async with temp_download_track(mock_provider, "12345") as tmp_path:
        saved_path = tmp_path
        assert isinstance(tmp_path, Path)
        assert "12345" in str(tmp_path)
        assert tmp_path.exists()
        assert tmp_path.read_bytes() == b"fake mp3 data"

    assert not saved_path.exists()
    assert not saved_path.parent.exists()


@pytest.mark.asyncio
async def test_temp_download_cleans_on_error():
    """Temp file cleaned up even if analysis raises."""
    from app.audio.temp_download import temp_download_track

    mock_provider = AsyncMock()

    async def fake_download(track_id, dest_path):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"fake mp3 data")
        return 13

    mock_provider.download_track = AsyncMock(side_effect=fake_download)

    saved_path = None
    with pytest.raises(ValueError):
        async with temp_download_track(mock_provider, "99999") as tmp_path:
            saved_path = tmp_path
            assert tmp_path.exists()
            raise ValueError("analysis failed")

    assert not saved_path.exists()


@pytest.mark.asyncio
async def test_temp_download_calls_provider():
    """Should call provider.download_track with (track_id, dest_path)."""
    from app.audio.temp_download import temp_download_track

    mock_provider = AsyncMock()

    async def fake_download(track_id, dest_path):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"x")
        return 1

    mock_provider.download_track = AsyncMock(side_effect=fake_download)

    async with temp_download_track(mock_provider, "54321"):
        pass

    mock_provider.download_track.assert_called_once()
    call_args = mock_provider.download_track.call_args
    assert call_args[0][0] == "54321"
    assert "54321.mp3" in str(call_args[0][1])

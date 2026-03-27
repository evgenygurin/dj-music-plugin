from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_temp_download_creates_and_cleans():
    """Temp download should create file, yield path, then delete."""
    from app.audio.temp_download import temp_download_track

    mock_client = AsyncMock()

    async def fake_download(track_id, dest_path, bitrate):
        # Simulate writing a file
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"fake mp3 data")
        return 13

    mock_client.download_track = AsyncMock(side_effect=fake_download)

    saved_path = None
    async with temp_download_track(mock_client, "12345") as tmp_path:
        saved_path = tmp_path
        assert isinstance(tmp_path, Path)
        assert "12345" in str(tmp_path)
        assert tmp_path.exists()
        assert tmp_path.read_bytes() == b"fake mp3 data"

    # After context exit, file should be deleted
    assert not saved_path.exists()
    assert not saved_path.parent.exists()  # temp dir also cleaned


@pytest.mark.asyncio
async def test_temp_download_cleans_on_error():
    """Temp file cleaned up even if analysis raises."""
    from app.audio.temp_download import temp_download_track

    mock_client = AsyncMock()

    async def fake_download(track_id, dest_path, bitrate):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"fake mp3 data")
        return 13

    mock_client.download_track = AsyncMock(side_effect=fake_download)

    saved_path = None
    with pytest.raises(ValueError):
        async with temp_download_track(mock_client, "99999") as tmp_path:
            saved_path = tmp_path
            assert tmp_path.exists()
            raise ValueError("analysis failed")

    assert not saved_path.exists()


@pytest.mark.asyncio
async def test_temp_download_calls_client():
    """Should call client.download_track with correct args."""
    from app.audio.temp_download import temp_download_track

    mock_client = AsyncMock()

    async def fake_download(track_id, dest_path, bitrate):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"x")
        return 1

    mock_client.download_track = AsyncMock(side_effect=fake_download)

    async with temp_download_track(mock_client, "54321", prefer_bitrate=192):
        pass

    mock_client.download_track.assert_called_once()
    call_args = mock_client.download_track.call_args
    assert call_args[0][0] == "54321"  # track_id
    assert call_args[0][2] == 192  # bitrate

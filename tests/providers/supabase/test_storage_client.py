from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.providers.supabase.storage_client import SupabaseStorageClient


@pytest.mark.asyncio
async def test_upload_calls_supabase_storage() -> None:
    mock_storage = MagicMock()
    mock_storage.from_.return_value.upload.return_value = None

    with patch(
        "app.providers.supabase.storage_client.create_client",
        return_value=MagicMock(storage=mock_storage),
    ):
        client = SupabaseStorageClient(url="http://test", key="test_key")
        await client.upload("test-bucket", "track/1/energy.npz", b"fake_npz_bytes")

    mock_storage.from_.assert_called_once_with("test-bucket")
    mock_storage.from_.return_value.upload.assert_called_once()


@pytest.mark.asyncio
async def test_download_returns_bytes() -> None:
    mock_storage = MagicMock()
    mock_storage.from_.return_value.download.return_value = b"downloaded"

    with patch(
        "app.providers.supabase.storage_client.create_client",
        return_value=MagicMock(storage=mock_storage),
    ):
        client = SupabaseStorageClient(url="http://test", key="test_key")
        result = await client.download("test-bucket", "track/1/energy.npz")

    assert result == b"downloaded"


@pytest.mark.asyncio
async def test_client_unavailable_without_url_and_key() -> None:
    client = SupabaseStorageClient(url="", key="")

    assert client.available is False
    assert await client.download("test-bucket", "track/1/energy.npz") == b""
    assert await client.upload("test-bucket", "track/1/energy.npz", b"fake") is None

"""SunoAdapter tests — Provider protocol conformance, no network."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.providers.suno.adapter import SunoAdapter
from app.registry.provider import Provider
from app.shared.errors import ValidationError


@pytest.fixture
def mock_client(tmp_path: Path) -> AsyncMock:
    client = AsyncMock()
    client.create_generation.return_value = {
        "task": {"taskId": "gen-1", "status": "queued"},
    }
    client.get_generation.return_value = {
        "id": "gen-1",
        "status": "completed",
        "clips": [{"audio_url": "https://cdn.example/gen-1.mp3"}],
    }
    client.cancel_generation.return_value = {"id": "gen-1", "status": "cancelled"}

    async def _download(generation_id: str, dest: Path, audio_url: str | None = None) -> Path:
        _ = generation_id, audio_url
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mp3")
        return dest

    client.download_generation.side_effect = _download
    return client


def test_adapter_satisfies_protocol(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client)
    assert isinstance(adapter, Provider)
    assert adapter.name == "suno"
    assert "generation" in adapter.entities_supported
    assert adapter.operations_supported["generation"] == ("create", "cancel", "download")


async def test_create_generation_normalizes_id_and_request(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client, default_model="suno-vx")
    out = await adapter.write(
        "generation",
        "create",
        {
            "prompt": "hypnotic techno intro bed, no vocals",
            "title": "intro",
            "tags": ["hypnotic techno", "dj-tool"],
            "duration_s": 60,
            "bpm": 134,
        },
    )
    assert out["generation_id"] == "gen-1"
    assert out["status"] == "queued"
    assert out["request"]["bpm"] == 134
    mock_client.create_generation.assert_awaited_once()
    payload = mock_client.create_generation.await_args.args[0]
    assert payload["mv"] == "suno-vx"
    assert payload["gpt_description_prompt"].startswith("hypnotic")
    # v2-web requires a non-empty prompt (an empty string reads as missing)
    assert payload["prompt"].startswith("hypnotic")
    assert payload["tags"] == "hypnotic techno, dj-tool"
    assert payload["make_instrumental"] is False


async def test_create_generation_generic_payload_mode(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client, default_model="suno-vx", payload_mode="generic")
    await adapter.write(
        "generation",
        "create",
        {
            "prompt": "hypnotic techno intro bed, no vocals",
            "title": "intro",
            "tags": ["hypnotic techno", "dj-tool"],
        },
    )
    payload = mock_client.create_generation.await_args.args[0]
    assert payload["model"] == "suno-vx"
    assert payload["prompt"].startswith("hypnotic")


async def test_create_generation_requires_prompt(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client)
    with pytest.raises(ValidationError, match="prompt"):
        await adapter.write("generation", "create", {})


def test_extract_clip_ids_prefers_pollable_clip_ids() -> None:
    # create returns a batch id + a clips array whose ids are the pollable ones
    raw = {
        "id": "batch-123",
        "status": "running",
        "clips": [
            {"id": "clip-a", "status": "submitted"},
            {"id": "clip-b", "status": "submitted"},
        ],
    }
    out = SunoAdapter._normalize_generation(raw)
    assert out["batch_id"] == "batch-123"
    assert out["clip_ids"] == ["clip-a", "clip-b"]
    # generation_id must be pollable (first clip), NOT the batch id
    assert out["generation_id"] == "clip-a"
    assert out["status"] == "running"  # top-level status wins over clip status


async def test_read_generation_normalizes_audio_url(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client)
    out = await adapter.read("generation", "gen-1", {})
    assert out["generation_id"] == "gen-1"
    assert out["ready"] is True
    assert out["audio_url"] == "https://cdn.example/gen-1.mp3"


async def test_read_account_merges_capabilities_and_balance(mock_client: AsyncMock) -> None:
    mock_client.get_account.return_value = {
        "total_credits_left": 42,
        "monthly_limit": 500,
        "monthly_usage": 8,
        "subscription_type": "pro",
        "is_active": True,
        "models": [
            {"external_key": "chirp-auk-turbo", "can_use": True},
            {"external_key": "chirp-fenix", "can_use": False},
        ],
    }
    adapter = SunoAdapter(client=mock_client)
    out = await adapter.read("account", None, {})
    assert out["provider"] == "suno"
    assert out["credits_left"] == 42
    assert out["subscription_type"] == "pro"
    assert out["usable_models"] == ["chirp-auk-turbo"]
    assert out["operations_supported"]["generation"] == ["create", "cancel", "download"]


async def test_read_account_degrades_when_billing_unavailable(mock_client: AsyncMock) -> None:
    from app.providers.suno.client_errors import APIError

    mock_client.get_account.side_effect = APIError("404: Not found")
    adapter = SunoAdapter(client=mock_client)
    out = await adapter.read("account", None, {})
    assert out["provider"] == "suno"
    assert "credits_left" not in out  # graceful degradation to capabilities-only


async def test_read_account_propagates_auth_error(mock_client: AsyncMock) -> None:
    from app.providers.suno.client_errors import AuthFailedError

    mock_client.get_account.side_effect = AuthFailedError("auth failed: 401")
    adapter = SunoAdapter(client=mock_client)
    with pytest.raises(AuthFailedError):
        await adapter.read("account", None, {})


async def test_download_generation_returns_local_file(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    adapter = SunoAdapter(client=mock_client)
    out = await adapter.write(
        "generation",
        "download",
        {"generation_id": "gen-1", "target_dir": str(tmp_path), "title": "intro"},
    )
    assert out["generation_id"] == "gen-1"
    assert Path(out["file_path"]).exists()
    assert out["file_size"] == 3


async def test_cancel_generation(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client)
    out = await adapter.write("generation", "cancel", {"generation_id": "gen-1"})
    assert out["status"] == "cancelled"


async def test_search_is_unsupported(mock_client: AsyncMock) -> None:
    adapter = SunoAdapter(client=mock_client)
    with pytest.raises(ValidationError, match="does not support catalog search"):
        await adapter.search("techno")


async def test_download_audio_delegates_to_generation_download(
    tmp_path: Path,
    mock_client: AsyncMock,
) -> None:
    adapter = SunoAdapter(client=mock_client, download_dir=tmp_path)
    path = await adapter.download_audio("gen-1")
    assert path.exists()
    assert path.name == "gen-1.mp3"

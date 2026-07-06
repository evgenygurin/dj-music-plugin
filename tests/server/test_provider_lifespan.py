"""provider_lifespan wires YandexAdapter into ProviderRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.registry.provider import ProviderRegistry
from app.server.lifespan import build_suno_adapter, provider_lifespan


@pytest.mark.asyncio
async def test_provider_lifespan_registers_yandex(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config as _cfg  # noqa: F401

    fake_settings = MagicMock()
    fake_settings.yandex.token = "stub"
    fake_settings.yandex.user_id = "42"
    fake_settings.yandex.base_url = "https://api.music.yandex.net"
    fake_settings.yandex.rate_limit_delay = 0.0
    fake_settings.yandex.download_dir = "/tmp"

    monkeypatch.setattr("app.server.lifespan.get_settings", lambda: fake_settings)

    async with provider_lifespan(MagicMock()) as ctx:
        registry: ProviderRegistry = ctx["provider_registry"]
        assert "yandex" in registry.names()
        adapter = registry.get("yandex")
        assert adapter.name == "yandex"


@pytest.mark.asyncio
async def test_provider_lifespan_closes_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_settings = MagicMock()
    fake_settings.yandex.token = "stub"
    fake_settings.yandex.user_id = "42"
    fake_settings.yandex.base_url = "https://api.music.yandex.net"
    fake_settings.yandex.rate_limit_delay = 0.0
    fake_settings.yandex.download_dir = "/tmp"

    monkeypatch.setattr("app.server.lifespan.get_settings", lambda: fake_settings)

    async with provider_lifespan(MagicMock()) as ctx:
        registry: ProviderRegistry = ctx["provider_registry"]
    # After exit, all adapters should be closed
    assert registry.names() == []


def test_build_suno_adapter_disabled_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "DJ_SUNO_API_KEY",
        "DJ_SUNO_BASE_URL",
        "DJ_SUNO_COOKIE_HEADER",
        "DJ_SUNO_CLIENT_TOKEN",
        "DJ_SUNO_DEVICE_ID",
        "DJ_SUNO_BEARER_TOKEN",
        "DJ_SUNO_STORAGE_STATE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    assert build_suno_adapter() is None


@pytest.mark.asyncio
async def test_build_suno_adapter_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DJ_SUNO_AUTH_MODE", "api_key")
    monkeypatch.setenv("DJ_SUNO_API_KEY", "token")
    monkeypatch.setenv("DJ_SUNO_BASE_URL", "https://suno.example")
    monkeypatch.setenv("DJ_SUNO_MODEL", "suno-vx")
    adapter = build_suno_adapter()
    assert adapter is not None
    assert adapter.name == "suno"
    await adapter.close()


@pytest.mark.asyncio
async def test_build_suno_adapter_from_sunoapi_key_without_base_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DJ_SUNO_AUTH_MODE", "api_key")
    monkeypatch.setenv("DJ_SUNO_API_KEY", "token")
    monkeypatch.delenv("DJ_SUNO_BASE_URL", raising=False)
    monkeypatch.delenv("DJ_SUNO_PAYLOAD_MODE", raising=False)
    adapter = build_suno_adapter()
    assert adapter is not None
    assert adapter.name == "suno"
    assert adapter._payload_mode == "sunoapi"
    await adapter.close()


@pytest.mark.asyncio
async def test_build_suno_adapter_from_session_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DJ_SUNO_AUTH_MODE", "session")
    monkeypatch.setenv("DJ_SUNO_COOKIE_HEADER", "__client=client-token; suno_device_id=device-1")
    monkeypatch.setenv("DJ_SUNO_BEARER_TOKEN", "jwt-token")
    adapter = build_suno_adapter()
    assert adapter is not None
    assert adapter.name == "suno"
    await adapter.close()


def test_build_suno_adapter_disabled_with_incomplete_session_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DJ_SUNO_AUTH_MODE", "session")
    monkeypatch.setenv("DJ_SUNO_BEARER_TOKEN", "jwt-token")
    monkeypatch.delenv("DJ_SUNO_DEVICE_ID", raising=False)
    monkeypatch.delenv("DJ_SUNO_COOKIE_HEADER", raising=False)
    assert build_suno_adapter() is None

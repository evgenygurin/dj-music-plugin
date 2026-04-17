"""provider_lifespan wires YandexAdapter into ProviderRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.registry.provider import ProviderRegistry
from app.server.lifespan import provider_lifespan


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

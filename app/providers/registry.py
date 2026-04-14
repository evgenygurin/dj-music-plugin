"""Provider registry — runtime container for active MusicProvider instances.

Created once during lifespan, injected via DI.
"""

from __future__ import annotations

from app.core.constants import Provider
from app.providers.protocol import MusicProvider


class ProviderRegistry:
    """Maps Provider enum to live MusicProvider instances."""

    def __init__(self) -> None:
        self._providers: dict[Provider, MusicProvider] = {}
        self._default: Provider | None = None

    def register(self, provider: MusicProvider, *, default: bool = False) -> None:
        self._providers[provider.provider] = provider
        if default or self._default is None:
            self._default = provider.provider

    def get(self, provider: Provider) -> MusicProvider:
        try:
            return self._providers[provider]
        except KeyError:
            available = ", ".join(p.value for p in self._providers)
            msg = f"Provider {provider.value!r} not registered. Available: {available}"
            raise KeyError(msg) from None

    @property
    def default(self) -> MusicProvider:
        if self._default is None:
            msg = "No providers registered"
            raise RuntimeError(msg)
        return self._providers[self._default]

    @property
    def default_provider(self) -> Provider:
        if self._default is None:
            msg = "No providers registered"
            raise RuntimeError(msg)
        return self._default

    def __contains__(self, provider: Provider) -> bool:
        return provider in self._providers

    def __len__(self) -> int:
        return len(self._providers)

    async def close_all(self) -> None:
        for p in self._providers.values():
            await p.close()
        self._providers.clear()

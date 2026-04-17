"""Provider Protocol + ProviderRegistry.

Per blueprint §6. A Provider represents an external music platform (Yandex
Music, Spotify, Beatport, SoundCloud). All have the same surface via the
``Provider`` protocol; the generic ``provider_read`` / ``provider_write`` /
``provider_search`` tools dispatch via ``ProviderRegistry``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.v2.shared.errors import NotFoundError


@runtime_checkable
class Provider(Protocol):
    """Universal interface for an external music platform."""

    name: str

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        """Read an entity by id or list with params. Entity-specific semantics per adapter."""

    async def write(self, entity: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Write operation (playlist add/remove, like/unlike, create/rename/delete)."""

    async def search(self, query: str, type: str, limit: int) -> dict[str, Any]:
        """Search catalog. ``type`` is one of 'tracks' / 'albums' / 'artists' / 'playlists'."""

    async def download_audio(self, track_id: str) -> Path:
        """Download audio, return local file path."""

    async def close(self) -> None:
        """Release network resources."""


class ProviderRegistry:
    """Container for registered Provider adapters, with optional default."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._default: str | None = None

    def register(self, provider: Provider, *, default: bool = False) -> None:
        """Register a Provider. Raises ``ValueError`` on duplicate name."""
        if provider.name in self._providers:
            raise ValueError(f"provider {provider.name!r} already registered")
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name

    def get(self, name: str) -> Provider:
        """Return adapter by name. Raises ``NotFoundError`` if unknown."""
        p = self._providers.get(name)
        if p is None:
            raise NotFoundError("provider", name)
        return p

    def default(self) -> Provider:
        """Return the default provider. Raises ``NotFoundError`` if none set."""
        if self._default is None:
            raise NotFoundError("provider", "default")
        return self._providers[self._default]

    def names(self) -> list[str]:
        """Return registered provider names, sorted."""
        return sorted(self._providers.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    async def close_all(self) -> None:
        """Close every provider and empty the registry."""
        for p in list(self._providers.values()):
            await p.close()
        self._providers.clear()
        self._default = None

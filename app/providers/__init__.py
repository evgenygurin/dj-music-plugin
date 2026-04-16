"""Music provider abstraction layer.

Defines the universal MusicProvider protocol and provider-agnostic models.
Platform-specific clients (YM, Soundcloud, Beatport, etc.) live under
``app/clients/<name>/`` and expose an adapter implementing this protocol.
"""

from app.providers.models import (
    ProviderAlbum,
    ProviderArtist,
    ProviderPlaylist,
    ProviderSearchResults,
    ProviderTrack,
)
from app.providers.protocol import MusicProvider
from app.providers.registry import ProviderRegistry

__all__ = [
    "MusicProvider",
    "ProviderAlbum",
    "ProviderArtist",
    "ProviderPlaylist",
    "ProviderRegistry",
    "ProviderSearchResults",
    "ProviderTrack",
]

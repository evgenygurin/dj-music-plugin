---
description: MusicProvider protocol and registry — multi-platform music integration
globs:
  - app/providers/**/*.py
  - app/clients/**/*.py
---

# MusicProvider

Universal interface for music platform clients. Services and tools NEVER import concrete clients — always depend on `MusicProvider` protocol or `ProviderRegistry`.

## Protocol (`app/providers/protocol.py`)

`@runtime_checkable` Protocol with 15+ async methods:

```python
from app.providers.protocol import MusicProvider
from app.providers.models import ProviderTrack, ProviderPlaylist, ProviderSearchResults, ProviderAlbum
```

Method groups: `search`, `get_tracks/get_similar/download_track/get_download_info`,
`get_album/get_artist_tracks`, `get_playlist/create_playlist/add_tracks_to_playlist/...`,
`get_liked_ids/add_likes/remove_likes/get_disliked_ids`, `close`.

## ProviderRegistry (`app/providers/registry.py`)

Created in `provider_lifespan`, injected via DI: `registry: ProviderRegistry = Depends(get_provider_registry)`.

```python
registry.register(adapter, default=True)   # once in lifespan
provider = registry.default                # default MusicProvider
provider = registry.get(Provider.YM)       # by Provider enum
Provider.YM in registry                    # membership check
```

## Adding a New Provider

1. Implement `MusicProvider` protocol in `app/clients/<platform>/adapter.py`
2. Add enum value to `app/core/constants.py:Provider`
3. Register in `provider_lifespan` in `app/bootstrap/lifespans.py`
4. `registry.close_all()` calls `adapter.close()` on shutdown — implement `async def close(self)`

## Models (`app/providers/models.py`)

- `ProviderTrack` — universal track (id, title, artists, album_id, duration_ms)
- `ProviderPlaylist` — universal playlist (id, title, track_count, visibility)
- `ProviderAlbum` — universal album
- `ProviderSearchResults` — wrapper with `tracks: list[ProviderTrack]`, `total`, `page`

## Gotchas

- `ym_client` key in lifespan context preserved for backward compat — use `provider_registry` in new code
- YM-specific operations (playlist diff array format, HMAC lyrics) stay in `app/clients/ym/` — not in protocol
- `ProviderRegistry.close_all()` clears `_providers` dict — providers are gone after shutdown
- `provider.provider` property returns `Provider` enum — used as the registry key
- Current implementation: YM only. `default` always returns the YM adapter unless another is registered

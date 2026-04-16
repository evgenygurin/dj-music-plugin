# Phase 2 Design: Service Layer Refactoring

## Context

Provider-agnostic refactoring of the DJ Music Plugin. This is Phase 2 of 4 — medium risk. Renames internal service fields, extracts YM business logic into the YM adapter, and removes YM-specific dict keys from service responses. No public MCP tool names change (Phase 3).

Branch: `refactor/provider-agnostic-naming`

Parent prompt: `docs/superpowers/specs/2026-04-16-provider-agnostic-refactoring-prompt.md`
Phase 1 design: `docs/superpowers/specs/2026-04-16-phase1-schemas-repos-filters-design.md`

---

## Scope

~15 files across four sub-tasks:

1. `YandexMusicAdapter` — absorb YM-specific formatting and enrichment
2. `SyncService` — constructor rename, private method refactor, delete dead code
3. `DiscoveryService` + `ImportService` — constructor rename, variable rename, dict keys
4. Repository methods + DI cleanup

---

## Core Design Decision: No New Protocol Methods

The `MusicProvider` protocol is **not extended**. Adding `parse_playlist_ref` or `format_track_ref` to the protocol would embed YM quirks into a shared interface all future adapters must implement.

Instead, YM quirks are absorbed **inside `YandexMusicAdapter`** by overriding existing protocol methods to handle YM-specific formatting transparently. Services use the existing protocol surface (`get_playlist_tracks(str)`, `add_tracks_to_playlist(str, list[str])`) with no awareness of the underlying format requirements.

Services discover the platform key via the already-existing `self._provider.provider.value` property (e.g. `"yandex_music"`), which is used to look up the right entry in `playlist.platform_ids`.

---

## Section A: `YandexMusicAdapter` Changes

### A.1 `get_playlist_tracks` — absorb `settings.ym_user_id`

Currently services call `get_playlist_tracks(f"{settings.ym_user_id}:{kind}")`. After Phase 2, services pass the raw value from `platform_ids` (e.g. `"42"`). The adapter handles the `owner_id:kind` format internally:

```python
async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderTrack]:
    if ":" not in playlist_id:
        playlist_id = f"{settings.ym_user_id}:{playlist_id}"
    # ... existing YM API call
```

`settings.ym_user_id` moves from `sync_service.py` and `discovery_service.py` into the adapter.

### A.2 `add_tracks_to_playlist` — absorb `trackId:albumId` enrichment

YM's API requires `"trackId:albumId"` format. Currently `SyncService._collect_ym_track_ids()` builds these strings, including a DB-backed cache of album IDs. After Phase 2:

- Services pass **plain track IDs** to `add_tracks_to_playlist`
- The adapter enriches them with album IDs using an **in-memory cache** + `get_tracks()` API call for misses
- The DB caching of album IDs (`YandexMetadata.album_id`) is no longer written from the service layer (the DB value remains for reads but is no longer updated)

```python
class YandexMusicAdapter:
    def __init__(self, client: YandexMusicClient) -> None:
        self._client = client
        self._album_cache: dict[str, str] = {}  # track_id → album_id

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: list[str]
    ) -> bool:
        enriched = await self._enrich_with_album_ids(track_ids)
        # ... YM API call with enriched IDs

    async def _enrich_with_album_ids(self, track_ids: list[str]) -> list[str]:
        missing = [tid for tid in track_ids if tid not in self._album_cache]
        if missing:
            tracks = await self._client.get_tracks(missing)
            for t in tracks:
                if t.album_id:
                    self._album_cache[t.id] = t.album_id
        return [
            f"{tid}:{self._album_cache[tid]}" if tid in self._album_cache else tid
            for tid in track_ids
        ]
```

The adapter is a singleton (created once in lifespan), so `_album_cache` persists across requests within a server session.

**Trade-off:** First call for a set push now makes one extra `get_tracks()` API call for tracks missing album IDs. This is acceptable — the operation is rare and correctness is preserved. The previous DB write of `update_ym_album_id` is removed along with `SyncService._enrich_missing_album_ids` and `_update_ym_album_id`.

---

## Section B: `SyncService` (`app/services/sync_service.py`)

### B.1 Constructor and imports

```python
# Remove: from app.config import settings  ← no longer needed
# Rename constructor parameter and field:
#   ym: MusicProvider  →  provider: MusicProvider
#   self._ym           →  self._provider
```

### B.2 Methods deleted

| Method | Reason |
|--------|--------|
| `_extract_ym_kind(platform_ids)` | Logic moved inline: `platform_ids.get(self._provider.provider.value)` |
| `_enrich_missing_album_ids()` | Moved to `YandexMusicAdapter._enrich_with_album_ids()` |
| `_update_ym_album_id()` | Moved to adapter (no longer needed in service) |

### B.3 Methods simplified/renamed

| Old | New | Change |
|-----|-----|--------|
| `_collect_ym_track_ids(version)` | `_collect_platform_track_ids(version)` | Drops album enrichment — now collects plain external IDs only |
| `_build_local_ym_map(playlist)` | `_build_local_provider_map(playlist)` | `"yandex_music"` → `self._provider.provider.value` |
| `_push_to_ym(ym_kind, local_ids)` | `_push_to_platform(platform_id, local_ids)` | Receives ready string ID, removes `settings.ym_user_id` |
| `_pull_from_ym(...)` | `_pull_from_platform(...)` | Rename only |

Simplified `_collect_platform_track_ids`:

```python
async def _collect_platform_track_ids(self, version: Any) -> list[str]:
    provider_key = self._provider.provider.value
    items_sorted = sorted(version.items, key=lambda i: i.sort_index)
    track_ids: list[str] = []
    for item in items_sorted:
        ext = await self._tracks.get_external_id(item.track_id, provider_key)
        if ext:
            track_ids.append(ext.external_id)
    return track_ids
```

### B.4 Dict-key changes in return values

| Old key | New key |
|---------|---------|
| `"ym_kind"` | `"platform_playlist_id"` |
| `"ym_id"` | `"external_id"` |
| `"ym_playlist_kind"` | `"platform_playlist_id"` |
| `"ym_playlist_name"` | `"platform_playlist_name"` |

### B.5 Public method names — unchanged

`sync_playlist`, `push_set_to_ym` — renamed in Phase 3 together with their calling controllers.

---

## Section C: `DiscoveryService` (`app/services/discovery_service.py`)

### C.1 Constructor

`ym: MusicProvider` → `provider: MusicProvider`, `self._ym` → `self._provider`. Remove `from app.config import settings`.

### C.2 `_provider_track_summary()` — dict key

```python
def _provider_track_summary(t: ProviderTrack) -> dict[str, Any]:
    return {
        "external_id": t.id,   # was "ym_id"
        ...
    }
```

All internal usages `c["ym_id"]`, `r["ym_id"]` updated to `c["external_id"]`.

### C.3 `expand_playlist_ym` internals

- Passes `platform_ids.get(self._provider.provider.value)` to `get_playlist_tracks()` — adapter handles `user_id:kind` format
- `settings.ym_user_id` reference removed
- `"playlist_kind"` return key → `"platform_playlist_id"`
- `"ym_id_used"` in `find_similar_ym` response → `"external_id_used"`

### C.4 Public method names — unchanged

`find_similar_ym`, `expand_playlist_ym` — renamed in Phase 3.

---

## Section D: `ImportService` (`app/services/import_service.py`)

### D.1 Constructor

`ym: MusicProvider` → `provider: MusicProvider`, `self._ym` → `self._provider`.

### D.2 Method rename

`_resolve_track_refs_to_ym()` → `_resolve_platform_track_refs()`

### D.3 Internal variables

`ym_id` local variables → `external_id` or `track_id` throughout.

### D.4 Dict keys in results

`"ym_id"` in download results → `"external_id"`.

### D.5 Preserved

`"ym:"` / `"YM:"` prefix parsing in `_resolve_platform_track_refs` — this is a user-facing MCP input format, renamed in Phase 3.

---

## Section E: Repository Methods

File: `app/db/repositories/track/external_ids.py`

| Old | Action | Reason |
|-----|--------|--------|
| `resolve_local_ids_to_ym()` | Rename → `resolve_local_ids_to_platform()` | Called from `import_service` and `tiered_pipeline` |
| `update_ym_album_id()` | **Delete** | Only caller (`SyncService._update_ym_album_id`) is deleted in Section B.2 — method becomes dead code |

Callers updated in the same commit:

| File | Change |
|------|--------|
| `app/services/import_service.py` | `resolve_local_ids_to_ym` → `resolve_local_ids_to_platform` |
| `app/services/tiered_pipeline.py` | `resolve_local_ids_to_ym` → `resolve_local_ids_to_platform` |
| `app/services/sync_service.py` | `update_ym_album_id` call site deleted with `_update_ym_album_id` method |

---

## Section F: DI + Cleanup

### F.1 DI factory parameter renames (`app/controllers/dependencies/services.py`)

```python
# get_sync_service:
return SyncService(track_repo, playlist_repo, set_repo, provider)  # was ym

# get_discovery_service:
return DiscoveryService(track_repo, provider)  # was ym

# get_import_service:
return ImportService(track_repo, provider, metadata, ingestion_repo)  # was ym
```

### F.2 Delete `get_ym_client()` (`app/controllers/dependencies/external.py`)

The function is marked legacy and no longer used. Verify with grep before deleting:

```bash
rg "get_ym_client" app/ | wc -l  # must be 0 after removal
```

---

## Section G: Tests

| Old | New |
|-----|-----|
| `ym=ym_mock` in service constructors | `provider=provider_mock` |
| `assert result["ym_id"] == ...` | `assert result["external_id"] == ...` |
| `ym_mock` variable names | `provider_mock` |
| `_make_ym_mock()` helpers | `make_provider_mock()` |

---

## Commit Plan

One file = one logical unit. Each commit must leave `make check` green.

| # | Commit message | Files |
|---|----------------|-------|
| 1 | `refactor(adapters): absorb ym_user_id and trackId:albumId into YandexMusicAdapter` | `app/clients/ym/adapter.py` |
| 2 | `refactor(services): provider-agnostic rename in SyncService` | `sync_service.py` |
| 3 | `refactor(services): provider-agnostic rename in DiscoveryService` | `discovery_service.py` |
| 4 | `refactor(services): provider-agnostic rename in ImportService` | `import_service.py` |
| 5 | `refactor(repos): rename resolve_local_ids_to_ym → platform, delete update_ym_album_id` | `external_ids.py` + `import_service.py` + `tiered_pipeline.py` |
| 6 | `chore(di): rename provider params in DI factories, delete get_ym_client()` | `services.py` + `external.py` |
| 7 | `test(services): update mocks and assertions for provider rename + external_id key` | `tests/` |

After each commit: `make check` must be green.

---

## Invariants (not changed in Phase 2)

- `MusicProvider` protocol — zero new methods
- DB schema — untouched
- Public service method names (`push_set_to_ym`, `expand_playlist_ym`, `find_similar_ym`) — renamed in Phase 3
- `"ym:"` prefix in MCP tool input parsing — renamed in Phase 3
- `settings.ym_*` env vars — not renamed (Phase 4 concern)
- `YandexMetadata` Python class — not renamed

---

## Exit Criteria

```bash
make check  # green

# No ym references in service internals:
rg "self\._ym\b|_push_to_ym|_collect_ym|_extract_ym|\"ym_id\"" app/services/ | wc -l  # 0

# Legacy DI gone:
rg "get_ym_client" app/ | wc -l  # 0

# Repo methods renamed/deleted:
rg "resolve_local_ids_to_ym\|update_ym_album_id" app/ | wc -l  # 0
```

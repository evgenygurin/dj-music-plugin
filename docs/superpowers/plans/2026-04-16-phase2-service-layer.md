# Phase 2: Service Layer Refactoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all YM-specific naming from the service layer: rename `self._ym` → `self._provider`, extract YM formatting quirks into the adapter, rename private methods and dict-keys to provider-agnostic names.

**Architecture:** Protocol-first (no new protocol methods). `YandexMusicAdapter` absorbs `settings.ym_user_id` and `trackId:albumId` enrichment internally. Services call the existing protocol surface with plain IDs. Dict key `"ym_id"` → `"external_id"` throughout service responses.

**Tech Stack:** Python 3.12, SQLAlchemy async, FastMCP, Pydantic v2, uv. Tests: pytest-asyncio with real in-process SQLite DB (no mocking for DB).

---

## Pre-flight

```bash
git checkout refactor/provider-agnostic-naming
make check   # must be green before starting
```

---

## Key Implementation Note

**`YandexMusicAdapter.add_tracks_to_playlist` ALREADY calls `self._client.resolve_track_ids_with_albums(track_ids)`** (line 148 of `adapter.py`). This means the adapter already handles `trackId:albumId` enrichment. `SyncService._collect_ym_track_ids` is redundant — it pre-builds `"trackId:albumId"` strings that the adapter re-processes. After Phase 2 we simply pass plain IDs and the adapter handles the rest. No `_album_cache` needed.

The only adapter change needed: `_parse_playlist_id` currently requires `"owner_id:kind"` format. Services will now pass bare kind strings like `"42"` (from `platform_ids["yandex_music"]`). The adapter must handle this.

---

## File Map

| File | Action |
|------|--------|
| `app/clients/ym/adapter.py` | Modify `_parse_playlist_id` to handle bare kind |
| `app/services/sync_service.py` | Full refactor — constructor, delete 3 methods, simplify 4, dict keys |
| `app/services/discovery_service.py` | Constructor, `self._ym` → `self._provider`, dict keys |
| `app/services/import_service.py` | Constructor, `self._ym` → `self._provider`, method rename, dict keys |
| `app/services/tiered_pipeline.py` | Update `resolve_local_ids_to_ym` call site |
| `app/db/repositories/track/external_ids.py` | Rename `resolve_local_ids_to_ym`, delete `update_ym_album_id` |
| `app/controllers/dependencies/services.py` | Rename `ym=` → `provider=` in 3 factories |
| `app/controllers/dependencies/external.py` | Delete `get_ym_client()` |
| `app/controllers/dependencies/__init__.py` | Remove `get_ym_client` from exports |
| `tests/test_services/test_sync_service.py` | Update mock kwarg, assertions, test names |
| `tests/test_services/test_import_service.py` | Update `ym=` → `provider=` kwarg |

---

## Task 1: Adapter — handle bare kind in `_parse_playlist_id`

**Files:**
- Modify: `app/clients/ym/adapter.py`

- [ ] **Step 1: Read the current `_parse_playlist_id` implementation**

Open `app/clients/ym/adapter.py` lines 104–107:

```python
def _parse_playlist_id(self, playlist_id: str) -> tuple[str, int]:
    """Parse ``"owner_id:kind"`` → (owner_id, kind)."""
    owner, kind_str = playlist_id.split(":", 1)
    return owner, int(kind_str)
```

- [ ] **Step 2: Update `_parse_playlist_id` to accept bare kind**

Replace the method with:

```python
def _parse_playlist_id(self, playlist_id: str) -> tuple[str, int]:
    """Parse playlist_id to (owner_id, kind).

    Accepts both ``"owner_id:kind"`` (full) and ``"kind"`` (bare).
    Bare kind uses the authenticated user's ID from the client.
    """
    if ":" in playlist_id:
        owner, kind_str = playlist_id.split(":", 1)
        return owner, int(kind_str)
    return self._client._user_id, int(playlist_id)
```

Note: `self._client._user_id` is already used by `_make_playlist_id` in the same class (line 110), so this is consistent.

- [ ] **Step 3: Verify `make check` is green**

```bash
make check
```

Expected: all checks pass.

- [ ] **Step 4: Commit**

```bash
git add app/clients/ym/adapter.py
git commit -m "refactor(adapters): handle bare playlist kind in _parse_playlist_id"
```

---

## Task 2: `SyncService` — full provider-agnostic refactor

**Files:**
- Modify: `app/services/sync_service.py`

This is the most significant task. The service loses 3 methods, simplifies 4, and changes all dict keys.

- [ ] **Step 1: Remove `settings` import and rename constructor field**

Replace the import block and class header:

```python
# Remove: from app.config import settings  ← deleted entirely

from __future__ import annotations

import json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.providers.protocol import MusicProvider

class SyncService:
    """Bidirectional playlist sync with music platform."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        provider: MusicProvider,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._sets = set_repo
        self._provider = provider
```

- [ ] **Step 2: Add `_get_platform_playlist_id` helper, update `sync_playlist`**

Replace `_extract_ym_kind` (deleted) with a new helper and update `sync_playlist`:

```python
def _get_platform_playlist_id(self, platform_ids: Any) -> str:
    """Extract platform playlist ID from platform_ids dict or JSON string."""
    pids = platform_ids or {}
    if isinstance(pids, str):
        pids = json.loads(pids)
    pid = pids.get(self._provider.provider.value)
    if not pid:
        raise ValidationError(
            f"Playlist has no {self._provider.provider.value} link. "
            "Set platform_ids first."
        )
    return str(pid)

async def sync_playlist(
    self,
    playlist_id: int,
    direction: str = "pull",
    dry_run: bool = True,
) -> dict[str, Any]:
    """Sync local playlist with platform. Returns diff or sync results."""
    valid_directions = ("pull", "push", "diff")
    if direction not in valid_directions:
        raise ValidationError(
            f"Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
        )

    playlist = await self._playlists.get_with_items(playlist_id)
    if not playlist:
        raise NotFoundError("Playlist", playlist_id)

    platform_playlist_id = self._get_platform_playlist_id(playlist.platform_ids)

    # Fetch platform playlist tracks
    platform_tracks = await self._provider.get_playlist_tracks(platform_playlist_id)
    platform_ids_set = {t.id for t in platform_tracks}
    platform_by_id = {t.id: t for t in platform_tracks}

    # Build local external ID set
    local_ext_ids, local_by_ext_id = await self._build_local_provider_map(playlist)

    # Compute diff
    on_platform_only = platform_ids_set - local_ext_ids
    on_local_only = local_ext_ids - platform_ids_set

    on_platform_details = [
        {
            "external_id": eid,
            "title": platform_by_id[eid].title,
            "artists": ", ".join(a.name for a in platform_by_id[eid].artists),
        }
        for eid in list(on_platform_only)[:50]
    ]
    on_local_details = [
        {"external_id": lid, "track_id": local_by_ext_id.get(lid)}
        for lid in list(on_local_only)[:50]
    ]

    if direction == "diff" or dry_run:
        return {
            "playlist_id": playlist_id,
            "playlist_name": playlist.name,
            "platform_playlist_id": platform_playlist_id,
            "direction": direction,
            "dry_run": dry_run,
            "local_count": len(local_ext_ids),
            "platform_count": len(platform_ids_set),
            "on_platform_only": on_platform_details,
            "on_local_only": on_local_details,
            "in_sync": len(platform_ids_set & local_ext_ids),
        }

    # Apply changes
    added_count = 0
    if direction == "pull" and on_platform_only:
        added_count = await self._pull_from_platform(
            playlist_id,
            playlist,
            on_platform_only,
            platform_by_id,
        )
    elif direction == "push" and on_local_only:
        added_count = await self._push_to_platform(platform_playlist_id, on_local_only)

    return {
        "playlist_id": playlist_id,
        "direction": direction,
        "synced": added_count,
        "on_platform_only": len(on_platform_only),
        "on_local_only": len(on_local_only),
    }
```

- [ ] **Step 3: Update `push_set_to_ym` internals (keep public name)**

```python
async def push_set_to_ym(
    self,
    set_id: int,
    ym_playlist_name: str | None = None,
    mode: str = "auto",
) -> dict[str, Any]:
    """Push DJ set as platform playlist."""
    valid_modes = ("create", "update", "auto")
    if mode not in valid_modes:
        raise ValidationError(f"Invalid mode: {mode}. Valid: {', '.join(valid_modes)}")

    dj_set = await self._sets.get_by_id(set_id)
    if not dj_set:
        raise NotFoundError("Set", set_id)

    version = await self._sets.get_latest_version(set_id)
    if not version or not version.items:
        raise ValidationError(f"Set {set_id} has no versions or tracks")

    # Collect platform track IDs (plain external IDs — adapter handles enrichment)
    platform_track_ids = await self._collect_platform_track_ids(version)
    if not platform_track_ids:
        raise ValidationError("No tracks in this set have platform IDs")

    playlist_name = ym_playlist_name or dj_set.name

    if mode in ("create", "auto"):
        pl = await self._provider.create_playlist(playlist_name)
        platform_playlist_id = pl.id  # already "owner_id:kind" from adapter
    else:
        raise ValidationError(
            "mode='update' requires playlist_id — use platform_playlists(action='get') first"
        )

    added = 0
    for batch_start in range(0, len(platform_track_ids), 20):
        batch = platform_track_ids[batch_start : batch_start + 20]
        await self._provider.add_tracks_to_playlist(platform_playlist_id, batch)
        added += len(batch)

    return {
        "set_id": set_id,
        "set_name": dj_set.name,
        "platform_playlist_id": platform_playlist_id,
        "platform_playlist_name": playlist_name,
        "tracks_pushed": added,
        "total_set_tracks": len(version.items),
        "tracks_with_platform_id": len(platform_track_ids),
        "mode_used": "create",
    }
```

- [ ] **Step 4: Replace private methods**

Delete `_extract_ym_kind`, `_build_local_ym_map`, `_pull_from_ym`, `_push_to_ym`, `_collect_ym_track_ids`, `_enrich_missing_album_ids`, `_update_ym_album_id`.

Add these replacements:

```python
# ── Private ──────────────────────────────────────

async def _build_local_provider_map(
    self,
    playlist: Any,
) -> tuple[set[str], dict[str, int]]:
    """Build mapping of local tracks to their platform external IDs."""
    provider_key = self._provider.provider.value
    local_ext_ids: set[str] = set()
    local_by_ext_id: dict[str, int] = {}

    if playlist.items:
        track_ids = [item.track_id for item in playlist.items]
        for tid in track_ids:
            ext = await self._tracks.get_external_id(tid, provider_key)
            if ext:
                local_ext_ids.add(ext.external_id)
                local_by_ext_id[ext.external_id] = tid

    return local_ext_ids, local_by_ext_id

async def _pull_from_platform(
    self,
    playlist_id: int,
    playlist: Any,
    on_platform_only: set[str],
    platform_by_id: dict[str, Any],
) -> int:
    """Pull tracks from platform into local playlist."""
    provider_key = self._provider.provider.value
    max_idx = max((item.sort_index for item in playlist.items), default=-1)
    added = 0
    for i, eid in enumerate(on_platform_only):
        t = platform_by_id[eid]
        track = await self._tracks.create_with_external_id(
            title=t.title,
            duration_ms=t.duration_ms,
            platform=provider_key,
            external_id=eid,
        )
        await self._playlists.add_track(playlist_id, track.id, max_idx + 1 + i)
        added += 1
    return added

async def _push_to_platform(
    self,
    platform_playlist_id: str,
    on_local_only: set[str],
) -> int:
    """Push local tracks to platform playlist."""
    track_ids = list(on_local_only)
    added = 0
    for batch_start in range(0, len(track_ids), 20):
        batch = track_ids[batch_start : batch_start + 20]
        await self._provider.add_tracks_to_playlist(platform_playlist_id, batch)
        added += len(batch)
    return added

async def _collect_platform_track_ids(self, version: Any) -> list[str]:
    """Collect platform track IDs for set version in sort order.

    Returns plain external IDs. The adapter handles any platform-specific
    format requirements (e.g. YM's trackId:albumId) internally.
    """
    provider_key = self._provider.provider.value
    items_sorted = sorted(version.items, key=lambda i: i.sort_index)
    track_ids: list[str] = []
    for item in items_sorted:
        ext = await self._tracks.get_external_id(item.track_id, provider_key)
        if ext:
            track_ids.append(ext.external_id)
    return track_ids
```

- [ ] **Step 5: Run `make check`**

```bash
make check
```

Expected: all checks pass. If mypy complains about `self._provider.provider.value`, verify `MusicProvider.provider` returns `Provider` enum which has `.value: str`.

- [ ] **Step 6: Commit**

```bash
git add app/services/sync_service.py
git commit -m "refactor(services): provider-agnostic rename in SyncService"
```

---

## Task 3: `DiscoveryService` — provider-agnostic rename

**Files:**
- Modify: `app/services/discovery_service.py`

- [ ] **Step 1: Update constructor**

```python
class DiscoveryService:
    """Track discovery, similar track search, and playlist expansion."""

    def __init__(
        self,
        track_repo: TrackRepository,
        provider: MusicProvider,
    ) -> None:
        self._tracks = track_repo
        self._provider = provider
```

Note: `from app.config import settings` stays — still used for `settings.discovery_min_duration_ms`, `settings.discovery_max_duration_ms`, `settings.discovery_max_seeds`, `settings.discovery_batch_size`.

- [ ] **Step 2: Update `find_similar_ym` — replace `self._ym` and `ym_id` vars**

```python
async def find_similar_ym(
    self,
    track_id: int,
    limit: int = 20,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    genre_filter_list: list[str] | None = None,
    genre_blacklist_list: list[str] | None = None,
    exclude_patterns_list: list[str] | None = None,
) -> dict[str, Any]:
    """Find similar tracks via music platform API with declarative filters."""
    track = await self._tracks.get_by_id(track_id)
    if not track:
        raise NotFoundError("Track", track_id)

    provider_key = self._provider.provider.value
    ext = await self._tracks.get_external_id(track_id, provider_key)
    external_id = ext.external_id if ext else None

    # Fallback: search by title
    if not external_id:
        search_result = await self._provider.search(track.title, search_type="track", page_size=1)
        if search_result.tracks:
            external_id = search_result.tracks[0].id
        else:
            return {
                "track_id": track_id,
                "track_title": track.title,
                "strategy": "platform",
                "similar": [],
                "message": "Could not find this track on platform",
            }

    raw_similar = await self._provider.get_similar(external_id)

    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms

    filtered = _apply_discovery_filters(
        raw_similar,
        limit,
        min_dur,
        max_dur,
        genre_filter_list,
        genre_blacklist_list,
        exclude_patterns_list,
    )

    return {
        "track_id": track_id,
        "track_title": track.title,
        "strategy": "platform",
        "external_id_used": external_id,
        "total_raw": len(raw_similar),
        "after_filter": len(filtered),
        "similar": filtered,
    }
```

- [ ] **Step 3: Update `find_similar_llm` — replace `self._ym`**

In `find_similar_llm`, replace:
- `await self._ym.search(...)` → `await self._provider.search(...)`
- `all_results.append(_provider_track_summary(t))` stays (function name already fine)
- `r["ym_id"]` → `r["external_id"]` (dedup loop)

```python
# Dedup by external_id
seen: set[str] = set()
deduped = []
for r in all_results:
    if r["external_id"] not in seen:
        seen.add(r["external_id"])
        deduped.append(r)
```

- [ ] **Step 4: Update `get_feedback_sets` — replace `self._ym`**

```python
async def get_feedback_sets(self) -> tuple[set[str], set[str]]:
    liked_set = await self._provider.get_liked_ids()
    disliked_set = await self._provider.get_disliked_ids()
    return liked_set, disliked_set
```

- [ ] **Step 5: Update `expand_playlist_ym` — remove `settings.ym_user_id`, fix dict keys**

```python
async def expand_playlist_ym(
    self,
    ym_playlist_kind: int,
    target_count: int = 100,
    genre_filter_list: list[str] | None = None,
    genre_blacklist_list: list[str] | None = None,
    exclude_patterns_list: list[str] | None = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    use_feedback: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Expand platform playlist with similar tracks. One-call orchestrator."""
    import time as _time

    _t0 = _time.monotonic()

    # 1. Fetch current playlist — pass bare kind, adapter prepends owner_id
    platform_playlist_id = str(ym_playlist_kind)
    current = await self._provider.get_playlist_tracks(platform_playlist_id)
    existing_ids = {t.id for t in current}
    need = max(0, target_count - len(current))

    if need == 0:
        return {
            "playlist_kind": ym_playlist_kind,
            "current_count": len(current),
            "target_count": target_count,
            "added": 0,
            "message": "Playlist already meets target count",
        }

    # 2. Select seeds
    max_seeds = min(len(current), settings.discovery_max_seeds)
    seeds = random.sample(current, max_seeds) if len(current) > max_seeds else list(current)

    # 3. Feedback gate
    liked: set[str] = set()
    disliked: set[str] = set()
    if use_feedback:
        liked, disliked = await self.get_feedback_sets()

    # 4. Collect candidates
    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms
    candidates: list[dict[str, Any]] = []
    blocked_count = 0

    for seed in seeds:
        if len(candidates) >= need:
            break

        try:
            raw_similar = await self._provider.get_similar(seed.id)
        except Exception:
            logger.debug("Platform get_similar failed for seed %s", seed.id, exc_info=True)
            continue

        for t in raw_similar:
            if t.id in existing_ids:
                continue
            if any(c["external_id"] == t.id for c in candidates):
                continue
            if use_feedback and t.id in disliked:
                blocked_count += 1
                continue
            dur = t.duration_ms or 0
            if dur and (dur < min_dur or dur > max_dur):
                continue
            if is_excluded_title(t.title, exclude_patterns_list):
                continue
            if not _provider_genre_ok(
                t.album_genre,
                whitelist=genre_filter_list,
                blacklist=genre_blacklist_list,
            ):
                continue

            entry = _provider_track_summary(t)
            entry["is_liked"] = t.id in liked
            candidates.append(entry)

            if len(candidates) >= need:
                break

    # 5. Dry run or add
    to_add = candidates[:need]

    if dry_run:
        return {
            "dry_run": True,
            "playlist_kind": ym_playlist_kind,
            "current_count": len(current),
            "target_count": target_count,
            "candidates_found": len(candidates),
            "would_add": len(to_add),
            "blocked_disliked": blocked_count,
            "seeds_used": len(seeds),
            "candidates": to_add[:50],
        }

    # 6. Batch add
    added = 0
    batch_size = settings.discovery_batch_size

    for batch_start in range(0, len(to_add), batch_size):
        batch = to_add[batch_start : batch_start + batch_size]
        track_ids_batch = [c["external_id"] for c in batch]
        try:
            await self._provider.add_tracks_to_playlist(platform_playlist_id, track_ids_batch)
            added += len(batch)
        except Exception:
            logger.warning("Platform playlist modify failed, stopping batch add", exc_info=True)
            break

    elapsed_ms = int((_time.monotonic() - _t0) * 1000)

    return {
        "playlist_kind": ym_playlist_kind,
        "before_count": len(current),
        "after_count": len(current) + added,
        "added": added,
        "seeds_used": len(seeds),
        "candidates_found": len(candidates),
        "blocked_disliked": blocked_count,
        "sample_tracks": to_add[:20],
        "execution_time_ms": elapsed_ms,
    }
```

- [ ] **Step 6: Update `_provider_track_summary` — rename dict key**

```python
def _provider_track_summary(t: ProviderTrack) -> dict[str, Any]:
    return {
        "external_id": t.id,   # was "ym_id"
        "title": t.title,
        "artists": ", ".join(a.name for a in t.artists),
        "duration_ms": t.duration_ms,
        "album": t.album_title or "",
        "genre": t.album_genre or "",
    }
```

- [ ] **Step 7: Update `_apply_discovery_filters` — replace `self._ym`**

In the module-level function `_apply_discovery_filters`, replace any `_provider_track_summary(t)` calls — the function name already uses the right abstraction, just check the function uses `_provider_track_summary` not `ym_id` directly.

If there's a line like `filtered.append(_provider_track_summary(t))` — that's already correct. But check for any direct `"ym_id"` references in the function body.

- [ ] **Step 8: Run `make check`**

```bash
make check
```

- [ ] **Step 9: Commit**

```bash
git add app/services/discovery_service.py
git commit -m "refactor(services): provider-agnostic rename in DiscoveryService"
```

---

## Task 4: `ImportService` — provider-agnostic rename

**Files:**
- Modify: `app/services/import_service.py`

- [ ] **Step 1: Update constructor**

```python
class ImportService:
    """Import and download tracks from music platform."""

    def __init__(
        self,
        track_repo: TrackRepository,
        provider: MusicProvider,
        metadata_service: Any | None = None,
        ingestion_repo: IngestionRepository | None = None,
    ) -> None:
        self._tracks = track_repo
        self._provider = provider
        self._metadata = metadata_service
        self._ingestion = ingestion_repo
```

- [ ] **Step 2: Update `import_tracks` — replace `self._ym` and `ym_id` vars**

In `import_tracks`, rename local vars `ym_id` → `external_id`, update `self._ym` → `self._provider`. The `"yandex_music"` platform string should use `self._provider.provider.value`:

Key lines to update:
```python
# was: ym_id = str(ref).strip().removeprefix("ym:").removeprefix("YM:")
external_id = str(ref).strip().removeprefix("ym:").removeprefix("YM:")

# was: existing = await self._tracks.get_by_external_id("yandex_music", ym_id)
existing = await self._tracks.get_by_external_id(self._provider.provider.value, external_id)

# was: await self._tracks.add_external_id(track.id, "yandex_music", ym_id)
await self._tracks.add_external_id(track.id, self._provider.provider.value, external_id)

# was: id_mapping[ym_id] = track.id / id_mapping[ym_id] = existing.track_id
id_mapping[external_id] = track.id / id_mapping[external_id] = existing.track_id
```

Note: `"ym:"` / `"YM:"` prefix stripping stays — this is a user-facing input format changed in Phase 3.

- [ ] **Step 3: Rename `_resolve_track_refs_to_ym` → `_resolve_platform_track_refs`**

Rename the method and update:
- the call site in `download_tracks`: `resolved_refs = await self._resolve_platform_track_refs(track_refs)`
- All `self._ym` → `self._provider` inside the method
- `ym_id` local vars → `external_id` or `track_id`
- `id_to_ym = await self._tracks.resolve_local_ids_to_ym(...)` → `id_to_platform = await self._tracks.resolve_local_ids_to_platform(...)`

- [ ] **Step 4: Update `download_tracks` — rename dict keys**

All `"ym_id"` keys in the returned dicts:
```python
# was: files.append({"ym_id": ym_id, "path": str(dest_path), "status": "skipped"})
files.append({"external_id": external_id, "path": str(dest_path), "status": "skipped"})

# was: {"ym_id": ym_id, "path": ...}
{"external_id": external_id, "path": ...}

# was: errors.append({"ym_id": ym_id, "error": str(e)[:100]})
errors.append({"external_id": external_id, "error": str(e)[:100]})
```

- [ ] **Step 5: Update remaining `self._ym` calls**

Search for any remaining `self._ym` in the file — `_enrich_from_ym`, `_resolve_filename`, etc.:
```python
# was: self._ym.get_tracks(...)
self._provider.get_tracks(...)

# was: self._ym.download_track(...)
self._provider.download_track(...)
```

- [ ] **Step 6: Run `make check`**

```bash
make check
```

- [ ] **Step 7: Commit**

```bash
git add app/services/import_service.py
git commit -m "refactor(services): provider-agnostic rename in ImportService"
```

---

## Task 5: Repository — rename + delete YM-specific methods

**Files:**
- Modify: `app/db/repositories/track/external_ids.py`
- Modify: `app/services/tiered_pipeline.py` (call site update)

- [ ] **Step 1: Rename `resolve_local_ids_to_ym` → `resolve_local_ids_to_platform`**

In `app/db/repositories/track/external_ids.py`, rename the method:

```python
async def resolve_local_ids_to_platform(
    self,
    local_ids: list[int],
) -> dict[int, str]:
    """Resolve local track IDs to external platform IDs.

    Returns mapping of local_track_id -> external_id string.
    Currently resolves against yandex_music platform only.
    TODO: accept platform param when second provider is added.
    """
    if not local_ids:
        return {}

    stmt = select(TrackExternalId.track_id, TrackExternalId.external_id).where(
        TrackExternalId.track_id.in_(local_ids),
        TrackExternalId.platform == "yandex_music",
    )
    result = await self.session.execute(stmt)
    return {row.track_id: row.external_id for row in result.all()}
```

- [ ] **Step 2: Delete `update_ym_album_id`**

Delete the entire `update_ym_album_id` method from `external_ids.py`. It has no callers after Task 2 (SyncService deleted `_update_ym_album_id` and `_enrich_missing_album_ids`).

- [ ] **Step 3: Update `tiered_pipeline.py` call site**

In `app/services/tiered_pipeline.py`, replace:

```python
# was:
ym_map = await self._tracks.resolve_local_ids_to_ym(need_analysis)
# ...
ym_id = ym_map.get(track_id)
if not ym_id:
    ...
return await self._download_and_analyze(track_id, ym_id, target_level)
```

With:

```python
platform_map = await self._tracks.resolve_local_ids_to_platform(need_analysis)
# ...
external_id = platform_map.get(track_id)
if not external_id:
    ...
return await self._download_and_analyze(track_id, external_id, target_level)
```

- [ ] **Step 4: Run `make check`**

```bash
make check
```

- [ ] **Step 5: Commit**

```bash
git add app/db/repositories/track/external_ids.py app/services/tiered_pipeline.py
git commit -m "refactor(repos): rename resolve_local_ids_to_platform, delete update_ym_album_id"
```

---

## Task 6: DI factories and `get_ym_client` cleanup

**Files:**
- Modify: `app/controllers/dependencies/services.py`
- Modify: `app/controllers/dependencies/external.py`
- Modify: `app/controllers/dependencies/__init__.py`

- [ ] **Step 1: Rename `ym=` kwargs in DI factories**

In `app/controllers/dependencies/services.py`, update three factories:

```python
def get_sync_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> SyncService:
    return SyncService(track_repo, playlist_repo, set_repo, provider)

def get_discovery_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> DiscoveryService:
    return DiscoveryService(track_repo, provider)

def get_import_service(
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
    metadata: MetadataService = Depends(get_metadata_service),  # noqa: B008
    ingestion_repo: IngestionRepository = Depends(get_ingestion_repo),  # noqa: B008
) -> ImportService:
    return ImportService(track_repo, provider, metadata, ingestion_repo)
```

- [ ] **Step 2: Delete `get_ym_client` from `external.py`**

Remove the entire function from `app/controllers/dependencies/external.py`:

```python
# DELETE THIS:
def get_ym_client() -> YandexMusicClient:
    """Get raw YM client from lifespan context (legacy, prefer get_music_provider)."""
    ctx = _get_context()
    client: YandexMusicClient = ctx.lifespan_context["ym_client"]
    return client
```

Also remove the `from app.clients.ym.client import YandexMusicClient` import if it's now unused (check — it may still be used elsewhere in the file, but in this case it's only used by `get_ym_client`).

- [ ] **Step 3: Remove from `__init__.py` exports**

In `app/controllers/dependencies/__init__.py`, remove:
- The `get_ym_client` import (line 20)
- The `"get_ym_client"` string in `__all__` (line 101)

- [ ] **Step 4: Verify no callers remain**

```bash
rg "get_ym_client" app/ tests/ | wc -l   # must be 0
```

- [ ] **Step 5: Run `make check`**

```bash
make check
```

- [ ] **Step 6: Commit**

```bash
git add app/controllers/dependencies/services.py \
        app/controllers/dependencies/external.py \
        app/controllers/dependencies/__init__.py
git commit -m "chore(di): rename provider params in factories, delete get_ym_client()"
```

---

## Task 7: Tests — update for new API

**Files:**
- Modify: `tests/test_services/test_sync_service.py`
- Modify: `tests/test_services/test_import_service.py`

- [ ] **Step 1: Update `test_sync_service.py` constructor kwarg**

In `_make_sync_service`, change `ym=provider_mock` → `provider=provider_mock`:

```python
def _make_sync_service(db: AsyncSession, provider_mock: AsyncMock) -> SyncService:
    return SyncService(
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        set_repo=SetRepository(db),
        provider=provider_mock,
    )
```

- [ ] **Step 2: Update tests to match new `_push_to_platform` signature**

The old tests tested `svc._push_to_ym(ym_kind=42, ...)` which received an int. After refactoring, `_push_to_platform(platform_playlist_id: str, ...)` receives a ready string.

Replace both tests:

```python
# ── _push_to_platform delegates to MusicProvider ──────────────

@pytest.mark.asyncio
async def test_push_to_platform_calls_provider_with_playlist_id(db: AsyncSession) -> None:
    """_push_to_platform calls add_tracks_to_playlist with the given playlist_id string."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    on_local_only = {"111", "222"}
    added = await svc._push_to_platform(
        platform_playlist_id="12345678:42",
        on_local_only=on_local_only,
    )

    assert added == 2

    add_call = provider_mock.add_tracks_to_playlist.call_args
    playlist_id = add_call[0][0]
    batch = add_call[0][1]

    assert playlist_id == "12345678:42"
    assert set(batch) == {"111", "222"}

@pytest.mark.asyncio
async def test_push_to_platform_passes_plain_ids(db: AsyncSession) -> None:
    """_push_to_platform passes plain IDs; adapter handles platform-specific enrichment."""
    provider_mock = _make_provider_mock()
    svc = _make_sync_service(db, provider_mock)

    on_local_only = {"333"}
    added = await svc._push_to_platform(
        platform_playlist_id="12345678:99",
        on_local_only=on_local_only,
    )

    assert added == 1

    add_call = provider_mock.add_tracks_to_playlist.call_args
    batch = add_call[0][1]
    assert "333" in batch
```

- [ ] **Step 3: Remove stale `from app.config import settings` import from test file**

After the changes, `settings.ym_user_id` is no longer referenced in tests. Remove the import if unused:

```python
# DELETE if unused:
from app.config import settings
```

- [ ] **Step 4: Update `test_import_service.py` constructor kwarg**

In `_make_service`, change `ym=ym_mock` → `provider=ym_mock`:

```python
def _make_service(db: AsyncSession) -> ImportService:
    track_repo = TrackRepository(db)
    provider_mock = AsyncMock()
    provider_mock.get_tracks = AsyncMock(return_value=[])
    provider_mock.provider = AsyncMock()
    provider_mock.provider.value = "yandex_music"
    return ImportService(track_repo=track_repo, provider=provider_mock)
```

Note: `provider_mock.provider.value` must be set because `import_tracks` now calls `self._provider.provider.value` to determine the platform key.

- [ ] **Step 5: Run `make check`**

```bash
make check
```

Expected: all 1362+ tests pass, no linter errors, no type errors.

- [ ] **Step 6: Commit**

```bash
git add tests/test_services/test_sync_service.py \
        tests/test_services/test_import_service.py
git commit -m "test(services): update mocks and assertions for provider rename + external_id key"
```

---

## Final Verification

```bash
make check   # green

# No ym references in service internals:
rg "self\._ym\b|_push_to_ym\b|_collect_ym\b|_extract_ym\b|\"ym_id\"" app/services/ | wc -l
# Expected: 0

# Legacy DI gone:
rg "get_ym_client" app/ tests/ | wc -l
# Expected: 0

# Repo methods renamed/deleted:
rg "resolve_local_ids_to_ym\|update_ym_album_id" app/ | wc -l
# Expected: 0
```

Then push:

```bash
git push origin refactor/provider-agnostic-naming
```

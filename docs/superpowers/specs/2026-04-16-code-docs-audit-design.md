# Code–Documentation Audit: Design

**Date:** 2026-04-16  
**Status:** Approved  

## Problem

After a major documentation update (`.claude/rules/` files), code accumulated discrepancies:

1. Anti-pattern `if ctx is not None:` guard on `ctx.report_progress()` — rule says no-op if no progress token, safe to call always.
2. `del ctx` in tools that should report progress (`sync_playlist`, `push_set_to_ym`, `analyze_batch`).
3. `deliver_set` (BATCH timeout tool) has zero progress reporting.
4. Direct `YandexMusicClient` imports in tools and services — rule: "NEVER import concrete clients, always depend on `MusicProvider` protocol".

## What Is Correct ✓

- All prompts return `PromptResult` ✓
- Resources return `dict[str, Any]` ✓ (knowledge:// blobs use `json.dumps()` — valid exception)
- Bootstrap order correct ✓
- `TrackFeatures` dataclass with `from_db()` ✓
- Tests have `seeded_db` fixture and `_seed_tracks_with_features` helper ✓

## Changes

### Group 1 — Progress reporting

| File | Change |
|------|--------|
| `controllers/tools/sets.py` | Remove `if ctx is not None:` guards on `ctx.report_progress()` |
| `controllers/tools/sync.py` | Remove `del ctx`, add `await ctx.report_progress(0/1, 1)` |
| `controllers/tools/delivery.py` | Add `await ctx.report_progress(0/1, 1)` |
| `controllers/tools/audio.py` | Remove `del ctx` + `Progress`, add `ctx.report_progress()` via async callback |
| `services/workflows/analyze_track_workflow.py` | Rename `progress: Any` → `on_progress: Callable | None`, update callers |

### Group 2 — MusicProvider migration

| File | Change |
|------|--------|
| `controllers/dependencies/__init__.py` | Export `get_music_provider` (already exists in `external.py`) |
| `controllers/tools/audio.py` | `get_similar_tracks`: use `provider: MusicProvider`, inline ProviderTrack filters |
| `controllers/tools/yandex/tracks.py` | Replace `YandexMusicClient` → `MusicProvider` |
| `controllers/tools/yandex/search.py` | Replace `YandexMusicClient` → `MusicProvider`, update kwarg names |
| `controllers/tools/yandex/albums.py` | Replace `YandexMusicClient` → `MusicProvider` |
| `controllers/tools/yandex/playlists.py` | Replace `YandexMusicClient` → `MusicProvider` |
| `controllers/tools/yandex/likes.py` | Replace `YandexMusicClient` → `MusicProvider` |
| `controllers/dependencies/services.py` | Replace 3 `YandexMusicClient` injections → `MusicProvider` |

## Verification

`make check` (lint + typecheck + arch + test) must pass after all changes.

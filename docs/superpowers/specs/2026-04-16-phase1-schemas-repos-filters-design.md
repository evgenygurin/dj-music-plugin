# Phase 1 Design: Schemas, Repositories, Filters

## Context

Provider-agnostic refactoring of the DJ Music Plugin. This is Phase 1 of 4 — the lowest-risk phase, touching only internal naming and a layer-violation fix. No public MCP API changes.

Branch: `refactor/provider-agnostic-naming`

Parent prompt: `docs/superpowers/specs/2026-04-16-provider-agnostic-refactoring-prompt.md`

---

## Scope

~12 files. Three independent sub-tasks:

1. Rename `ym_responses.py` schema classes
2. Rename repository methods `*_ym_metadata` → `*_platform_metadata`
3. Move `is_excluded_title` to `core/utils/` and add import-linter contract

---

## Section A: Schema Renaming

### What changes

`app/schemas/ym_responses.py` → `app/schemas/platform_responses.py`

| Old name | New name |
|----------|----------|
| `YMSearchResponse` | `PlatformSearchResult` |
| `YMTrackBatch` | `PlatformTrackBatch` |
| `YMArtistTrackItem` | `ArtistTrackItem` |
| `YMArtistTracksPage` | `ArtistTracksPage` |
| `YMAlbumResponse` | `AlbumResult` |
| `YMPlaylistActionResult` | `PlaylistActionResult` |
| `YMLikesActionResult` | `LikesActionResult` |

### Backward-compat aliases

`app/schemas/__init__.py` keeps re-export aliases with old names so Phase 2–3 consumers compile without changes until their own phase:

```python
# Aliases for gradual migration — remove after Phase 3
YMSearchResponse = PlatformSearchResult
YMTrackBatch = PlatformTrackBatch
# ... etc
```

### Not in scope

`app/schemas/yandex.py` (`YMTrackSummary`) — not touched in Phase 1. `ym_id` field rename is deferred to Phase 2 (dict-key audit).

Controllers that import `YM*` directly from `app.schemas.ym_responses` are **not updated in Phase 1** — they will be fixed in Phase 3 when the tool files are renamed anyway.

---

## Section B: Repository Methods

### Files

| File | Old method | New method |
|------|-----------|-----------|
| `app/db/repositories/track/library.py` | `get_ym_metadata()` | `get_platform_metadata()` |
| `app/db/repositories/track/library.py` | `save_ym_metadata()` | `save_platform_metadata()` |
| `app/db/repositories/metadata.py` | `get_ym_metadata()` | `get_platform_metadata()` |

### Callers updated in same commit

| Caller | Method called |
|--------|--------------|
| `app/services/import_service.py` | `save_ym_metadata` |
| `app/services/sync_service.py` | `get_ym_metadata` |
| `app/services/metadata_service.py` | `get_ym_metadata` |

### Invariants

- Python class `YandexMetadata` (maps to `yandex_metadata` table) — **not renamed**
- DB schema unchanged
- Method signatures unchanged (same parameters, same return types)

---

## Section C: Filter Layer-Violation Fix

### Problem

`app/services/discovery_service.py` and `app/controllers/tools/audio.py` import `is_excluded_title` from `app.clients.ym.filters`. The services→clients import violates the dependency rule.

### Solution

Create `app/core/utils/filters.py` with `is_excluded_title`:

```python
def is_excluded_title(title: str, patterns: list[str] | None = None) -> bool:
    """Return True if track title matches any exclude pattern."""
    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)
```

`app.config` import is allowed — the `utils-leaf` contract only forbids app-domain imports, not config.

Update callers:
- `app/services/discovery_service.py`: `from app.core.utils.filters import is_excluded_title`
- `app/controllers/tools/audio.py`: same

`is_excluded_title` stays in `app/clients/ym/filters.py` as well (it's not used there, but removing it is a separate concern — leave as-is to minimize Phase 1 scope).

### New import-linter contract

Add to `.importlinter`:

```ini
[importlinter:contract:services-no-clients]
name = Services must not import client layer directly
type = forbidden
source_modules = app.services
forbidden_modules = app.clients
```

---

## Commit plan

One logical unit = one commit:

1. `refactor(schemas): rename YM* response classes to platform-agnostic names` — rename file + classes + add aliases
2. `refactor(repos): rename get/save_ym_metadata → get/save_platform_metadata` — repos + all callers
3. `fix(services): move is_excluded_title to core/utils/filters, fix layer violation` — new file + update imports + import-linter contract

After each commit: `make check` must be green.

---

## Exit criteria

```bash
make check  # green
rg "YMSearch|YMTrack|YMAlbum|YMPlaylist|YMLikes" app/schemas/ | wc -l  # 0 (excluding aliases)
```

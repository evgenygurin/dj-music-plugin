# Phase 1: Schemas, Repositories, Filters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename YM-specific schema classes to platform-agnostic names, rename repository metadata methods, move `is_excluded_title` to core utils, and enforce the services-no-clients import contract — all without breaking `make check`.

**Architecture:** Three independent sub-tasks (schemas, repos, filters), each committed separately. Controllers keep working via a compatibility shim (`ym_responses.py` re-exports from `platform_responses.py`) — they are cleaned up in Phase 3. Phase 1 touches only internal naming and a layer-violation fix.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy async, import-linter, ruff, mypy, pytest.

---

## File map

| File | Action |
|------|--------|
| `app/schemas/ym_responses.py` | Convert to compatibility shim |
| `app/schemas/platform_responses.py` | Create — new home for renamed classes |
| `app/schemas/__init__.py` | Update imports to use new names |
| `app/db/repositories/track/library.py` | Rename 2 methods |
| `app/db/repositories/metadata.py` | Rename 1 method |
| `app/services/import_service.py` | Update 1 call site |
| `app/services/sync_service.py` | Update 1 call site |
| `app/services/metadata_service.py` | Update 1 call site |
| `app/core/utils/filters.py` | Create — `is_excluded_title` |
| `app/services/discovery_service.py` | Update import |
| `app/controllers/tools/audio.py` | Update import |
| `.importlinter` | Add `services-no-clients` contract |

---

## Task 1: Create `platform_responses.py` and compatibility shim

**Files:**
- Create: `app/schemas/platform_responses.py`
- Modify: `app/schemas/ym_responses.py`
- Modify: `app/schemas/__init__.py`

- [ ] **Step 1: Create `app/schemas/platform_responses.py`**

```python
"""Platform-agnostic Pydantic response DTOs for MCP tools.

These models provide typed ``outputSchema`` so LLM agents know
the exact shape of every platform tool response.
"""

from __future__ import annotations

from pydantic import BaseModel

# ── search ──────────────────────────────────────────────────

class PlatformSearchResult(BaseModel):
    """Response from ``search_platform``."""

    query: str
    type: str
    tracks: list[dict[str, object]]
    albums: list[dict[str, object]]
    artists: list[dict[str, object]]
    playlists: list[dict[str, object]]

# ── get_platform_tracks ──────────────────────────────────────

class PlatformTrackBatch(BaseModel):
    """Response from ``get_platform_tracks``."""

    count: int
    tracks: list[dict[str, object]]

# ── get_artist_tracks ────────────────────────────────────────

class ArtistTrackItem(BaseModel):
    """Single track in artist-tracks response."""

    id: str
    title: str
    duration_ms: int | None = None
    albums: list[dict[str, object]] = []

class ArtistTracksPage(BaseModel):
    """Response from ``get_artist_tracks``."""

    artist_id: str
    offset: int
    limit: int
    sort_by: str
    count: int
    tracks: list[ArtistTrackItem]
    has_next: bool

# ── get_album ────────────────────────────────────────────────

class AlbumResult(BaseModel):
    """Response from ``get_album``."""

    album_id: str
    album: dict[str, object]

# ── platform_playlists ───────────────────────────────────────

class PlaylistActionResult(BaseModel):
    """Response from ``platform_playlists`` (all actions)."""

    action: str
    playlists: list[dict[str, object]] | None = None
    playlist: dict[str, object] | None = None
    kind: int | None = None
    new_name: str | None = None
    result: dict[str, object] | None = None
    count: int | None = None
    offset: int | None = None
    limit: int | None = None
    track_ids: list[str] | None = None
    tracks: list[dict[str, object]] | None = None
    next_offset: int | None = None
    truncated: bool | None = None
    removed: int | None = None
    not_found: list[str] | None = None
    revision: int | None = None

# ── platform_likes ───────────────────────────────────────────

class LikesActionResult(BaseModel):
    """Response from ``platform_likes`` (all actions)."""

    action: str
    count: int | None = None
    offset: int | None = None
    limit: int | None = None
    liked_ids: list[str] | None = None
    next_offset: int | None = None
    truncated: bool | None = None
    track_ids: list[str] | None = None
    success: bool | None = None
```

- [ ] **Step 2: Replace `app/schemas/ym_responses.py` with a compatibility shim**

Controllers in `app/controllers/tools/yandex/` import directly from this module. The shim keeps them compiling without changes until Phase 3.

```python
"""Compatibility shim — re-exports platform_responses under legacy YM names.

Remove this file after Phase 3 when all controllers are updated.
"""

from app.schemas.platform_responses import (
    AlbumResult as YMAlbumResponse,
    ArtistTrackItem as YMArtistTrackItem,
    ArtistTracksPage as YMArtistTracksPage,
    LikesActionResult as YMLikesActionResult,
    PlatformSearchResult as YMSearchResponse,
    PlatformTrackBatch as YMTrackBatch,
    PlaylistActionResult as YMPlaylistActionResult,
)

__all__ = [
    "YMAlbumResponse",
    "YMArtistTrackItem",
    "YMArtistTracksPage",
    "YMLikesActionResult",
    "YMSearchResponse",
    "YMTrackBatch",
    "YMPlaylistActionResult",
]
```

- [ ] **Step 3: Update `app/schemas/__init__.py`**

Replace the imports block and `__all__` to use new names (keep legacy aliases too):

```python
"""Shared Pydantic DTOs used across the services and MCP tools layers.

Single source of truth for framework-agnostic structured output models.

Layer organisation:
- :mod:`common` — pagination envelope
- :mod:`track` — TrackBrief, TrackStandard
- :mod:`playlist` — PlaylistSummary
- :mod:`set` — SetSummary
- :mod:`yandex` — YMTrackSummary
- :mod:`platform_responses` — platform-agnostic tool response DTOs

Domain helpers (``is_excluded_title``, ``genre_ok``)
live in :mod:`app.core.utils.filters` and :mod:`app.clients.ym.filters`.
"""

from __future__ import annotations

from app.schemas.common import PaginatedResponse
from app.schemas.platform_responses import (
    AlbumResult,
    ArtistTrackItem,
    ArtistTracksPage,
    LikesActionResult,
    PlaylistActionResult,
    PlatformSearchResult,
    PlatformTrackBatch,
)
from app.schemas.playlist import PlaylistSummary
from app.schemas.set import SetSummary
from app.schemas.track import TrackBrief, TrackStandard
from app.schemas.yandex import YMTrackSummary

# Legacy aliases — remove after Phase 3
YMAlbumResponse = AlbumResult
YMArtistTrackItem = ArtistTrackItem
YMArtistTracksPage = ArtistTracksPage
YMLikesActionResult = LikesActionResult
YMPlaylistActionResult = PlaylistActionResult
YMSearchResponse = PlatformSearchResult
YMTrackBatch = PlatformTrackBatch

__all__ = [
    "AlbumResult",
    "ArtistTrackItem",
    "ArtistTracksPage",
    "LikesActionResult",
    "PaginatedResponse",
    "PlaylistActionResult",
    "PlaylistSummary",
    "PlatformSearchResult",
    "PlatformTrackBatch",
    "SetSummary",
    "TrackBrief",
    "TrackStandard",
    # Legacy aliases
    "YMAlbumResponse",
    "YMArtistTrackItem",
    "YMArtistTracksPage",
    "YMLikesActionResult",
    "YMPlaylistActionResult",
    "YMSearchResponse",
    "YMTrackBatch",
    "YMTrackSummary",
]
```

- [ ] **Step 4: Run lint + type check**

```bash
cd /Users/laptop/dev/dj-music-plugin
uv run ruff check app/schemas/ && uv run mypy app/schemas/
```

Expected: no errors.

- [ ] **Step 5: Run full check**

```bash
uv run pytest -x -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 6: Verify exit criterion**

```bash
rg "class YMSearch|class YMTrack|class YMAlbum|class YMPlaylist|class YMLikes" app/schemas/
```

Expected: 0 lines (classes are gone, only aliases remain).

- [ ] **Step 7: Commit**

```bash
git add app/schemas/platform_responses.py app/schemas/ym_responses.py app/schemas/__init__.py
git commit -m "refactor(schemas): rename YM* response classes to platform-agnostic names"
```

---

## Task 2: Rename repository metadata methods

**Files:**
- Modify: `app/db/repositories/track/library.py` (lines 41–83)
- Modify: `app/db/repositories/metadata.py` (line 24)
- Modify: `app/services/import_service.py` (line 302)
- Modify: `app/services/sync_service.py` (line 250)
- Modify: `app/services/metadata_service.py` (line 166)

- [ ] **Step 1: Rename methods in `app/db/repositories/track/library.py`**

Change line 41 from:
```python
    async def get_ym_metadata(self, track_id: int) -> YandexMetadata | None:
```
to:
```python
    async def get_platform_metadata(self, track_id: int) -> YandexMetadata | None:
```

Change line 47 from:
```python
    async def save_ym_metadata(
        self,
        track_id: int,
        ym_id: str,
        ym_track: Any,
    ) -> YandexMetadata:
        """Save YM metadata from either a ProviderTrack or a YMTrack response object."""
```
to:
```python
    async def save_platform_metadata(
        self,
        track_id: int,
        ym_id: str,
        ym_track: Any,
    ) -> YandexMetadata:
        """Save platform metadata from either a ProviderTrack or a YMTrack response object."""
```

- [ ] **Step 2: Rename method in `app/db/repositories/metadata.py`**

Change line 24 from:
```python
    async def get_ym_metadata(self, track_id: int) -> YandexMetadata | None:
        """Get YandexMetadata row for a track."""
```
to:
```python
    async def get_platform_metadata(self, track_id: int) -> YandexMetadata | None:
        """Get platform metadata row for a track."""
```

- [ ] **Step 3: Update caller in `app/services/import_service.py` (line ~302)**

Change:
```python
                await self._tracks.save_ym_metadata(
```
to:
```python
                await self._tracks.save_platform_metadata(
```

- [ ] **Step 4: Update caller in `app/services/sync_service.py` (line ~250)**

Change:
```python
            ym_meta = await self._tracks.get_ym_metadata(item.track_id)
```
to:
```python
            ym_meta = await self._tracks.get_platform_metadata(item.track_id)
```

- [ ] **Step 5: Update caller in `app/services/metadata_service.py` (line ~166)**

Change:
```python
        meta = await self._repo.get_ym_metadata(track_id)
```
to:
```python
        meta = await self._repo.get_platform_metadata(track_id)
```

- [ ] **Step 6: Verify no remaining old method calls**

```bash
rg "save_ym_metadata|get_ym_metadata" app/
```

Expected: 0 lines.

- [ ] **Step 7: Run full check**

```bash
uv run ruff check app/ && uv run mypy app/ && uv run pytest -x -q 2>&1 | tail -5
```

Expected: no errors, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/db/repositories/track/library.py app/db/repositories/metadata.py \
        app/services/import_service.py app/services/sync_service.py \
        app/services/metadata_service.py
git commit -m "refactor(repos): rename get/save_ym_metadata → get/save_platform_metadata"
```

---

## Task 3: Move `is_excluded_title` to core utils and add import-linter contract

**Files:**
- Create: `app/core/utils/filters.py`
- Modify: `app/services/discovery_service.py` (line 14)
- Modify: `app/controllers/tools/audio.py` (line 23)
- Modify: `.importlinter`

- [ ] **Step 1: Create `app/core/utils/filters.py`**

```python
"""Generic track-filtering helpers.

Pure functions depending only on app.config.settings.
Used by services and controllers — intentionally kept in core.utils
so that services don't need to import from the client layer.
"""

from __future__ import annotations

from app.config import settings

def is_excluded_title(title: str, patterns: list[str] | None = None) -> bool:
    """Return True if track title matches any exclusion pattern (remix, edit, live…)."""
    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)
```

- [ ] **Step 2: Update import in `app/services/discovery_service.py`**

Change line 14 from:
```python
from app.clients.ym.filters import is_excluded_title
```
to:
```python
from app.core.utils.filters import is_excluded_title
```

- [ ] **Step 3: Update import in `app/controllers/tools/audio.py`**

Change line 23 from:
```python
from app.clients.ym.filters import is_excluded_title
```
to:
```python
from app.core.utils.filters import is_excluded_title
```

- [ ] **Step 4: Add `services-no-clients` contract to `.importlinter`**

Append to `.importlinter` after the last existing contract:

```ini
# ── Contract 6: services must not import client layer ───────
[importlinter:contract:services-no-clients]
name = Services must not import client layer directly
type = forbidden
source_modules =
    app.services
forbidden_modules =
    app.clients
```

- [ ] **Step 5: Verify import-linter passes**

```bash
uv run lint-imports
```

Expected: all contracts pass (including the new one).

- [ ] **Step 6: Run full check**

```bash
uv run ruff check app/ && uv run mypy app/ && uv run pytest -x -q 2>&1 | tail -5
```

Expected: no errors, all tests pass.

- [ ] **Step 7: Verify exit criterion**

```bash
rg "from app.clients.ym.filters import is_excluded_title" app/services/ app/controllers/
```

Expected: 0 lines.

- [ ] **Step 8: Commit**

```bash
git add app/core/utils/filters.py app/services/discovery_service.py \
        app/controllers/tools/audio.py .importlinter
git commit -m "fix(services): move is_excluded_title to core/utils/filters, add services-no-clients contract"
```

---

## Final verification

- [ ] **Run full `make check`**

```bash
make check
```

Expected: lint + typecheck + arch + tests all green.

- [ ] **Check Phase 1 exit criteria from spec**

```bash
rg "class YMSearch|class YMTrack|class YMAlbum|class YMPlaylist|class YMLikes" app/schemas/
# Expected: 0 lines

rg "save_ym_metadata|get_ym_metadata" app/
# Expected: 0 lines

rg "from app.clients.ym.filters import is_excluded_title" app/services/ app/controllers/
# Expected: 0 lines
```

- [ ] **Push branch**

```bash
git push origin refactor/provider-agnostic-naming
```

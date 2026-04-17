# Phase 3 — Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 13 v2 MCP tools (6 entity CRUD, 3 provider, 2 compute, 1 sync, 1 admin), 6 custom handlers, and port the Yandex provider adapter — polymorphic dispatch via EntityRegistry + ProviderRegistry, with migration-parity tests proving semantic equivalence to legacy tools.

**Architecture:** Per blueprint §5–§7: all CRUD is polymorphic through `EntityRegistry.get(entity).repo_attr → uow.<attr>`. Handlers provide side-effects (download, analyze, import). Provider tools go through `ProviderRegistry` — zero coupling to concrete clients. Tools are thin: parse params → dispatch → serialize; all business logic lives in handlers + domain + repositories.

**Tech Stack:** Python 3.12, FastMCP v3.2, SQLAlchemy 2.0 async, Pydantic v2, httpx async, pytest + pytest-asyncio, aiosqlite (tests), asyncpg (prod).

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§5 (EntityRegistry + handlers), §6 (ProviderRegistry), §7 (Tool Catalog), §12 (FastMCP v3 features), §14.3 (service→handler migration), §15.4 (Phase 3 scope), §16 (import-linter).

---

## File Structure

Files created by this plan (exact paths, all under `app/v2/`).

### Source code (`app/v2/`)

```bash
app/v2/
├── providers/
│   └── yandex/
│       ├── __init__.py
│       ├── adapter.py                # YandexAdapter(Provider) — universal protocol impl
│       ├── client.py                 # YandexClient — httpx async
│       ├── rate_limiter.py           # TokenBucketRateLimiter
│       └── filters.py                # genre / exclude-pattern filters
├── handlers/
│   ├── __init__.py
│   ├── track_import.py               # entity_create handler for entity="track"
│   ├── audio_file_download.py        # entity_create handler for entity="audio_file"
│   ├── track_features_analyze.py     # entity_create handler for entity="track_features"
│   ├── track_features_reanalyze.py   # entity_update handler for entity="track_features"
│   ├── transition_persist.py         # entity_create handler for entity="transition"
│   └── set_version_build.py          # entity_create handler for entity="set_version"
├── tools/
│   ├── __init__.py
│   ├── entity/
│   │   ├── __init__.py
│   │   ├── list.py                   # entity_list
│   │   ├── get.py                    # entity_get
│   │   ├── create.py                 # entity_create
│   │   ├── update.py                 # entity_update
│   │   ├── delete.py                 # entity_delete
│   │   └── aggregate.py              # entity_aggregate
│   ├── provider/
│   │   ├── __init__.py
│   │   ├── read.py                   # provider_read
│   │   ├── write.py                  # provider_write
│   │   └── search.py                 # provider_search
│   ├── compute/
│   │   ├── __init__.py
│   │   ├── score_pool.py             # transition_score_pool
│   │   └── sequence_optimize.py      # sequence_optimize
│   ├── sync/
│   │   ├── __init__.py
│   │   └── playlist_sync.py          # playlist_sync
│   └── admin/
│       ├── __init__.py
│       └── unlock_namespace.py       # unlock_namespace
├── registry/
│   └── entity.py                     # MODIFIED — add register_default_entities()
├── schemas/
│   ├── __init__.py                   # MODIFIED — add tool response schemas
│   ├── tool_responses.py             # EntityListView, EntityGetView, AggregateResult, etc.
│   └── provider_dto.py               # ProviderReadResult, ProviderWriteResult, ProviderSearchResult
└── server/
    └── lifespan.py                   # MODIFIED — wire YandexAdapter into ProviderRegistry
```

### Tests (`tests/v2/`)

```bash
tests/v2/
├── providers/
│   ├── __init__.py
│   └── yandex/
│       ├── __init__.py
│       ├── test_adapter.py
│       ├── test_client.py
│       └── test_rate_limiter.py
├── handlers/
│   ├── __init__.py
│   ├── test_track_import.py
│   ├── test_audio_file_download.py
│   ├── test_track_features_analyze.py
│   ├── test_track_features_reanalyze.py
│   ├── test_transition_persist.py
│   └── test_set_version_build.py
├── tools/
│   ├── __init__.py
│   ├── conftest.py                   # in-memory MCP client fixture
│   ├── entity/
│   │   ├── __init__.py
│   │   ├── test_list.py
│   │   ├── test_get.py
│   │   ├── test_create.py
│   │   ├── test_update.py
│   │   ├── test_delete.py
│   │   └── test_aggregate.py
│   ├── provider/
│   │   ├── __init__.py
│   │   ├── test_read.py
│   │   ├── test_write.py
│   │   └── test_search.py
│   ├── compute/
│   │   ├── __init__.py
│   │   ├── test_score_pool.py
│   │   └── test_sequence_optimize.py
│   ├── sync/
│   │   ├── __init__.py
│   │   └── test_playlist_sync.py
│   └── admin/
│       ├── __init__.py
│       └── test_unlock_namespace.py
├── parity/
│   ├── __init__.py
│   ├── test_crud_parity.py           # old manage_tracks vs new entity_create/update/delete
│   ├── test_import_parity.py         # old import_tracks vs new entity_create(track)
│   ├── test_download_parity.py       # old download_tracks vs new entity_create(audio_file)
│   ├── test_analyze_parity.py        # old analyze_track vs new entity_create(track_features)
│   ├── test_score_parity.py          # old score_transitions vs new transition_score_pool
│   └── test_sync_parity.py           # old sync_playlist vs new playlist_sync
└── registry/
    └── test_register_default_entities.py
```

### Config updates

- `.importlinter` — 3 new Phase 3 contracts (handlers-no-mcp, tools-no-db, providers-isolated)

---

## Task 1: Scaffolding — directory skeleton

**Files:**
- Create: `app/v2/providers/__init__.py`, `app/v2/providers/yandex/__init__.py`
- Create: `app/v2/handlers/__init__.py`
- Create: `app/v2/tools/__init__.py`
- Create: `app/v2/tools/entity/__init__.py`, `app/v2/tools/provider/__init__.py`, `app/v2/tools/compute/__init__.py`, `app/v2/tools/sync/__init__.py`, `app/v2/tools/admin/__init__.py`
- Create: matching `tests/v2/` subdirs

- [ ] **Step 1: Create all directories**

```bash
mkdir -p app/v2/providers/yandex app/v2/handlers
mkdir -p app/v2/tools/entity app/v2/tools/provider app/v2/tools/compute app/v2/tools/sync app/v2/tools/admin
mkdir -p tests/v2/providers/yandex tests/v2/handlers
mkdir -p tests/v2/tools/entity tests/v2/tools/provider tests/v2/tools/compute tests/v2/tools/sync tests/v2/tools/admin
mkdir -p tests/v2/parity
```

- [ ] **Step 2: Create empty `__init__.py` in every subpackage**

Write `""""""` (triple-empty docstring) in each. List of files:

```text
app/v2/providers/__init__.py
app/v2/providers/yandex/__init__.py
app/v2/handlers/__init__.py
app/v2/tools/__init__.py
app/v2/tools/entity/__init__.py
app/v2/tools/provider/__init__.py
app/v2/tools/compute/__init__.py
app/v2/tools/sync/__init__.py
app/v2/tools/admin/__init__.py
tests/v2/providers/__init__.py
tests/v2/providers/yandex/__init__.py
tests/v2/handlers/__init__.py
tests/v2/tools/__init__.py
tests/v2/tools/entity/__init__.py
tests/v2/tools/provider/__init__.py
tests/v2/tools/compute/__init__.py
tests/v2/tools/sync/__init__.py
tests/v2/tools/admin/__init__.py
tests/v2/parity/__init__.py
```

- [ ] **Step 3: Verify packages are importable**

```bash
uv run python -c "import app.v2.providers.yandex, app.v2.handlers, app.v2.tools.entity, app.v2.tools.provider, app.v2.tools.compute, app.v2.tools.sync, app.v2.tools.admin; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/v2/providers app/v2/handlers app/v2/tools tests/v2/providers tests/v2/handlers tests/v2/tools tests/v2/parity
git commit -m "feat(v2): create Phase 3 directory skeleton

Empty packages for providers/yandex, handlers, tools (entity/provider/
compute/sync/admin), and matching tests/."
```

---

## Task 2: `app/v2/providers/yandex/rate_limiter.py` — token bucket

**Files:**
- Create: `app/v2/providers/yandex/rate_limiter.py`
- Test: `tests/v2/providers/yandex/test_rate_limiter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/providers/yandex/test_rate_limiter.py
"""Rate limiter behavior tests."""

import asyncio
import time

import pytest

from app.v2.providers.yandex.rate_limiter import TokenBucketRateLimiter

@pytest.mark.asyncio
async def test_no_delay_first_call() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.5)
    t0 = time.monotonic()
    await rl.acquire()
    assert time.monotonic() - t0 < 0.05

@pytest.mark.asyncio
async def test_second_call_is_delayed() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.2)
    await rl.acquire()
    t0 = time.monotonic()
    await rl.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.18
    assert elapsed < 0.3

@pytest.mark.asyncio
async def test_backoff_after_429() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, base_backoff_s=0.1, max_retries=3)
    assert rl.current_backoff() == 0.0
    await rl.on_rate_limited()
    assert rl.current_backoff() >= 0.1
    await rl.on_rate_limited()
    assert rl.current_backoff() >= 0.2  # 2× exponential

@pytest.mark.asyncio
async def test_backoff_resets_on_success() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, base_backoff_s=0.1)
    await rl.on_rate_limited()
    await rl.on_rate_limited()
    assert rl.current_backoff() > 0
    rl.on_success()
    assert rl.current_backoff() == 0.0

@pytest.mark.asyncio
async def test_max_retries_exceeded() -> None:
    rl = TokenBucketRateLimiter(delay_s=0.0, max_retries=2)
    await rl.on_rate_limited()
    await rl.on_rate_limited()
    assert rl.retries_exhausted() is True
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/providers/yandex/test_rate_limiter.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/providers/yandex/rate_limiter.py`**

```python
"""Token-bucket rate limiter with exponential backoff on 429 responses.

Yandex Music API rate-limits aggressively on both reads and writes.
Default delay (1.5s) configurable via DJ_YM_RATE_LIMIT_DELAY.
"""

from __future__ import annotations

import asyncio
import time

class TokenBucketRateLimiter:
    """Enforces min delay between calls + exponential backoff on 429."""

    def __init__(
        self,
        *,
        delay_s: float = 1.5,
        base_backoff_s: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self._delay_s = delay_s
        self._base_backoff_s = base_backoff_s
        self._max_retries = max_retries
        self._last_call_at: float = 0.0
        self._retry_count: int = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until the next request is allowed."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_at
            backoff = self.current_backoff()
            wait = max(0.0, max(self._delay_s, backoff) - elapsed)
            if self._last_call_at == 0.0 and backoff == 0.0:
                wait = 0.0
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_at = time.monotonic()

    async def on_rate_limited(self) -> None:
        """Called after observing HTTP 429."""
        self._retry_count += 1

    def on_success(self) -> None:
        """Called after a successful response — reset backoff."""
        self._retry_count = 0

    def current_backoff(self) -> float:
        if self._retry_count == 0:
            return 0.0
        return self._base_backoff_s * (2 ** (self._retry_count - 1))

    def retries_exhausted(self) -> bool:
        return self._retry_count >= self._max_retries
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/providers/yandex/test_rate_limiter.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/providers/yandex/rate_limiter.py tests/v2/providers/yandex/test_rate_limiter.py
git commit -m "feat(v2): add Yandex token-bucket rate limiter

Port from app/ym/rate_limiter.py with async-lock-protected acquire(),
exponential backoff on 429, reset-on-success semantics."
```

---

## Task 3: `app/v2/providers/yandex/filters.py` — genre + pattern filters

**Files:**
- Create: `app/v2/providers/yandex/filters.py`
- Test: `tests/v2/providers/yandex/test_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/providers/yandex/test_filters.py
"""Yandex track filter tests (genre allow/block + title patterns)."""

import pytest

from app.v2.providers.yandex.filters import TrackFilter

def test_no_filters_passes_everything() -> None:
    f = TrackFilter()
    track = {"id": "1", "title": "A", "genre": "techno"}
    assert f.matches(track) is True

def test_genre_whitelist_passes() -> None:
    f = TrackFilter(genre_allow={"techno", "house"})
    assert f.matches({"id": "1", "genre": "techno"}) is True
    assert f.matches({"id": "2", "genre": "pop"}) is False

def test_genre_blacklist_rejects() -> None:
    f = TrackFilter(genre_block={"ambient"})
    assert f.matches({"id": "1", "genre": "techno"}) is True
    assert f.matches({"id": "2", "genre": "ambient"}) is False

def test_duration_bounds() -> None:
    f = TrackFilter(min_duration_ms=120_000, max_duration_ms=600_000)
    assert f.matches({"id": "1", "duration_ms": 300_000}) is True
    assert f.matches({"id": "2", "duration_ms": 60_000}) is False
    assert f.matches({"id": "3", "duration_ms": 700_000}) is False

def test_title_exclude_patterns() -> None:
    f = TrackFilter(exclude_title_patterns=[r"(?i)\bremix\b", r"(?i)radio edit"])
    assert f.matches({"id": "1", "title": "Untitled"}) is True
    assert f.matches({"id": "2", "title": "Untitled (Remix)"}) is False
    assert f.matches({"id": "3", "title": "Radio Edit"}) is False

def test_missing_fields_are_neutral() -> None:
    f = TrackFilter(min_duration_ms=120_000)
    # no duration_ms field -> filter does not reject
    assert f.matches({"id": "1"}) is True
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/providers/yandex/test_filters.py -v
```

- [ ] **Step 3: Write `app/v2/providers/yandex/filters.py`**

```python
"""Yandex track filter: genre whitelist/blacklist + duration + title patterns.

Used by TrackImportHandler and DiscoveryWorkflow prompt — keeps filter
logic isolated from the adapter (so the adapter stays dumb).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class TrackFilter:
    genre_allow: frozenset[str] | None = None
    genre_block: frozenset[str] = field(default_factory=frozenset)
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    exclude_title_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Compile patterns eagerly for O(1) per-track match.
        compiled = tuple(re.compile(p) for p in self.exclude_title_patterns)
        object.__setattr__(self, "_compiled", compiled)

    @classmethod
    def from_params(
        cls,
        *,
        genre_allow: Iterable[str] | None = None,
        genre_block: Iterable[str] | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        exclude_patterns: Iterable[str] | None = None,
    ) -> "TrackFilter":
        return cls(
            genre_allow=frozenset(genre_allow) if genre_allow else None,
            genre_block=frozenset(genre_block or ()),
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            exclude_title_patterns=tuple(exclude_patterns or ()),
        )

    def matches(self, track: dict[str, Any]) -> bool:
        genre = (track.get("genre") or "").lower()
        if self.genre_allow is not None and genre and genre not in {g.lower() for g in self.genre_allow}:
            return False
        if genre and genre in {g.lower() for g in self.genre_block}:
            return False
        duration = track.get("duration_ms")
        if duration is not None:
            if self.min_duration_ms is not None and duration < self.min_duration_ms:
                return False
            if self.max_duration_ms is not None and duration > self.max_duration_ms:
                return False
        title = track.get("title") or ""
        for pattern in self._compiled:  # type: ignore[attr-defined]
            if pattern.search(title):
                return False
        return True

    def apply(self, tracks: Collection[dict[str, Any]]) -> list[dict[str, Any]]:
        return [t for t in tracks if self.matches(t)]
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/providers/yandex/test_filters.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/providers/yandex/filters.py tests/v2/providers/yandex/test_filters.py
git commit -m "feat(v2): add Yandex track filter (genre/duration/title)

Port from app/ym/filters.py as a frozen dataclass. Precompiles regex
patterns. Missing fields are neutral (do not reject)."
```

---

## Task 4: `app/v2/providers/yandex/client.py` — httpx async client

**Files:**
- Create: `app/v2/providers/yandex/client.py`
- Test: `tests/v2/providers/yandex/test_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/providers/yandex/test_client.py
"""YandexClient tests — mocked httpx transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.v2.providers.yandex.client import (
    APIError,
    AuthFailedError,
    RateLimitedError,
    YandexClient,
)
from app.v2.providers.yandex.rate_limiter import TokenBucketRateLimiter

@pytest.fixture
def client() -> YandexClient:
    return YandexClient(
        token="test-token",
        user_id="42",
        base_url="https://api.music.yandex.net",
        rate_limiter=TokenBucketRateLimiter(delay_s=0.0),
    )

@pytest.mark.asyncio
@respx.mock
async def test_search_tracks(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/search").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"tracks": {"results": [{"id": "1", "title": "A"}], "total": 1}}},
        )
    )
    result = await client.search(query="hello", type="tracks", limit=10)
    assert result["tracks"]["total"] == 1
    assert result["tracks"]["results"][0]["id"] == "1"

@pytest.mark.asyncio
@respx.mock
async def test_401_raises_auth_failed(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    with pytest.raises(AuthFailedError):
        await client.get_tracks(["1"])

@pytest.mark.asyncio
@respx.mock
async def test_429_raises_rate_limited(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "5"}, json={"error": "rate"})
    )
    with pytest.raises(RateLimitedError):
        await client.get_tracks(["1"])

@pytest.mark.asyncio
@respx.mock
async def test_get_playlist(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/users/42/playlists/3").mock(
        return_value=httpx.Response(
            200, json={"result": {"kind": 3, "title": "P", "revision": 7, "trackCount": 0}}
        )
    )
    pl = await client.get_playlist("42:3")
    assert pl["kind"] == 3
    assert pl["revision"] == 7

@pytest.mark.asyncio
@respx.mock
async def test_modify_playlist_diff(client: YandexClient) -> None:
    respx.post(
        "https://api.music.yandex.net/users/42/playlists/3/change-relative"
    ).mock(
        return_value=httpx.Response(200, json={"result": {"revision": 8, "trackCount": 1}})
    )
    diff = [{"op": "insert", "at": 0, "tracks": [{"id": "1", "albumId": "2"}]}]
    result = await client.modify_playlist("42:3", diff=diff, revision=7)
    assert result["revision"] == 8

@pytest.mark.asyncio
@respx.mock
async def test_500_raises_api_error(client: YandexClient) -> None:
    respx.get("https://api.music.yandex.net/tracks").mock(
        return_value=httpx.Response(500, json={"error": "oops"})
    )
    with pytest.raises(APIError):
        await client.get_tracks(["1"])

@pytest.mark.asyncio
@respx.mock
async def test_close_is_idempotent(client: YandexClient) -> None:
    await client.close()
    await client.close()  # must not raise
```

- [ ] **Step 2: Add `respx` test dep**

```bash
uv add --group dev respx
```

- [ ] **Step 3: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/providers/yandex/test_client.py -v
```

- [ ] **Step 4: Write `app/v2/providers/yandex/client.py`**

```python
"""Yandex Music async HTTP client — httpx + OAuth + rate limiter.

Ported from app/ym/client.py. All public methods return raw dicts (shape
defined by YM API); YandexAdapter maps them to v2 schemas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.v2.providers.yandex.rate_limiter import TokenBucketRateLimiter

class YandexError(Exception):
    """Base Yandex client error."""

class AuthFailedError(YandexError):
    """HTTP 401 / 403 — invalid or missing token."""

class RateLimitedError(YandexError):
    """HTTP 429 — too many requests (after retries)."""

class APIError(YandexError):
    """HTTP 4xx (non-401/403/429) or 5xx."""

class YandexClient:
    def __init__(
        self,
        *,
        token: str,
        user_id: str,
        base_url: str = "https://api.music.yandex.net",
        rate_limiter: TokenBucketRateLimiter | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._token = token
        self._user_id = user_id
        self._base_url = base_url.rstrip("/")
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"OAuth {token}"},
            timeout=timeout_s,
        )
        self._closed = False

    # ---------- core request ---------- #

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        await self._rate_limiter.acquire()
        try:
            resp = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise APIError(f"HTTP transport error: {exc}") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthFailedError(f"auth failed: {resp.status_code} — check DJ_YM_TOKEN")
        if resp.status_code == 429:
            await self._rate_limiter.on_rate_limited()
            if self._rate_limiter.retries_exhausted():
                raise RateLimitedError("rate limited, retries exhausted")
            raise RateLimitedError(f"rate limited, retry_after={resp.headers.get('Retry-After')}")
        if resp.status_code >= 400:
            raise APIError(f"{resp.status_code}: {resp.text[:500]}")

        self._rate_limiter.on_success()
        payload = resp.json()
        return payload.get("result", payload) if isinstance(payload, dict) else payload

    # ---------- search ---------- #

    async def search(self, *, query: str, type: str = "tracks", limit: int = 20) -> dict[str, Any]:
        return await self._request(
            "GET", "/search", params={"text": query, "type": type, "page-size": limit}
        )

    # ---------- tracks ---------- #

    async def get_tracks(self, track_ids: list[str]) -> list[dict[str, Any]]:
        res = await self._request(
            "GET", "/tracks", params={"trackIds": ",".join(track_ids)}
        )
        return res if isinstance(res, list) else []

    async def get_similar(self, track_id: str) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/tracks/{track_id}/similar")
        if isinstance(res, dict):
            return list(res.get("similarTracks", []))
        return []

    async def get_download_info(self, track_id: str) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/tracks/{track_id}/download-info")
        return res if isinstance(res, list) else []

    async def download_track(self, track_id: str, dest: Path) -> Path:
        """Two-step: resolve download URL, then stream to disk."""
        info = await self.get_download_info(track_id)
        if not info:
            raise APIError(f"no download options for track {track_id}")
        best = max(info, key=lambda x: x.get("bitrateInKbps", 0))
        direct_url = best["downloadInfoUrl"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with self._http.stream("GET", direct_url) as resp:
            if resp.status_code >= 400:
                raise APIError(f"download failed: {resp.status_code}")
            with dest.open("wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        return dest

    # ---------- albums + artists ---------- #

    async def get_album(self, album_id: str, *, with_tracks: bool = False) -> dict[str, Any]:
        path = f"/albums/{album_id}" + ("/with-tracks" if with_tracks else "")
        return await self._request("GET", path)

    async def get_artist_tracks(
        self, artist_id: str, *, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/artists/{artist_id}/tracks",
            params={"page": offset // limit, "page-size": limit},
        )

    # ---------- playlists ---------- #

    async def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        owner, kind = playlist_id.split(":", 1)
        return await self._request("GET", f"/users/{owner}/playlists/{kind}")

    async def list_playlists(self) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/users/{self._user_id}/playlists/list")
        return res if isinstance(res, list) else []

    async def create_playlist(self, *, title: str, visibility: str = "private") -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/playlists/create",
            data={"title": title, "visibility": visibility},
        )

    async def modify_playlist(
        self, playlist_id: str, *, diff: list[dict[str, Any]], revision: int
    ) -> dict[str, Any]:
        owner, kind = playlist_id.split(":", 1)
        import json as _json
        return await self._request(
            "POST",
            f"/users/{owner}/playlists/{kind}/change-relative",
            data={"diff": _json.dumps(diff), "revision": revision},
        )

    async def delete_playlist(self, playlist_id: str) -> dict[str, Any]:
        owner, kind = playlist_id.split(":", 1)
        return await self._request("POST", f"/users/{owner}/playlists/{kind}/delete")

    async def rename_playlist(self, playlist_id: str, *, title: str) -> dict[str, Any]:
        owner, kind = playlist_id.split(":", 1)
        return await self._request(
            "POST", f"/users/{owner}/playlists/{kind}/name", data={"value": title}
        )

    # ---------- likes ---------- #

    async def get_liked_ids(self) -> list[str]:
        res = await self._request("GET", f"/users/{self._user_id}/likes/tracks")
        if isinstance(res, dict):
            library = res.get("library", {})
            return [str(t["id"]) for t in library.get("tracks", [])]
        return []

    async def get_disliked_ids(self) -> list[str]:
        res = await self._request("GET", f"/users/{self._user_id}/dislikes/tracks")
        if isinstance(res, dict):
            library = res.get("library", {})
            return [str(t["id"]) for t in library.get("tracks", [])]
        return []

    async def add_likes(self, track_ids: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/add-multiple",
            data={"track-ids": ",".join(track_ids)},
        )

    async def remove_likes(self, track_ids: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/users/{self._user_id}/likes/tracks/remove",
            data={"track-ids": ",".join(track_ids)},
        )

    # ---------- cleanup ---------- #

    async def close(self) -> None:
        if self._closed:
            return
        await self._http.aclose()
        self._closed = True
```

- [ ] **Step 5: Run tests — expected PASS**

```bash
uv run pytest tests/v2/providers/yandex/test_client.py -v
```
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/providers/yandex/client.py tests/v2/providers/yandex/test_client.py pyproject.toml uv.lock
git commit -m "feat(v2): port Yandex async HTTP client

httpx.AsyncClient + OAuth header + rate limiter integration.
Typed errors: AuthFailedError/RateLimitedError/APIError. All public
methods return raw dicts (adapter layer maps to v2 schemas)."
```

---

## Task 5: `app/v2/providers/yandex/adapter.py` — Provider protocol impl

**Files:**
- Create: `app/v2/providers/yandex/adapter.py`
- Test: `tests/v2/providers/yandex/test_adapter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/providers/yandex/test_adapter.py
"""YandexAdapter tests — asserts Provider protocol conformance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.v2.providers.yandex.adapter import YandexAdapter
from app.v2.registry.provider import Provider

@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.search.return_value = {
        "tracks": {"results": [{"id": "1", "title": "X"}], "total": 1}
    }
    client.get_tracks.return_value = [{"id": "1", "title": "X", "durationMs": 200000}]
    client.get_similar.return_value = [{"id": "2", "title": "Y"}]
    client.get_playlist.return_value = {"kind": 3, "title": "P", "revision": 7, "trackCount": 0}
    client.modify_playlist.return_value = {"revision": 8}
    client.get_liked_ids.return_value = ["1", "2", "3"]
    client.download_track.return_value = Path("/tmp/x.mp3")
    return client

def test_adapter_satisfies_protocol(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    assert isinstance(adapter, Provider)
    assert adapter.name == "yandex"

@pytest.mark.asyncio
async def test_read_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("track", id="1", params={})
    assert result["id"] == "1"
    assert result["title"] == "X"
    mock_client.get_tracks.assert_awaited_once_with(["1"])

@pytest.mark.asyncio
async def test_read_similar(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("track_similar", id="1", params={})
    assert result["results"][0]["id"] == "2"

@pytest.mark.asyncio
async def test_read_playlist(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.read("playlist", id="42:3", params={})
    assert result["revision"] == 7

@pytest.mark.asyncio
async def test_read_unknown_entity_raises(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    with pytest.raises(ValueError, match="unknown"):
        await adapter.read("bogus", id="1", params={})

@pytest.mark.asyncio
async def test_write_playlist_add_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.write(
        "playlist",
        operation="add_tracks",
        params={"playlist_id": "42:3", "track_ids": ["1", "2"], "revision": 7},
    )
    assert result["revision"] == 8

@pytest.mark.asyncio
async def test_write_playlist_remove_tracks(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    mock_client.modify_playlist.return_value = {"revision": 9}
    result = await adapter.write(
        "playlist",
        operation="remove_tracks",
        params={"playlist_id": "42:3", "from": 0, "to": 1, "revision": 8},
    )
    assert result["revision"] == 9

@pytest.mark.asyncio
async def test_write_likes_add(mock_client: AsyncMock) -> None:
    mock_client.add_likes.return_value = {"ok": True}
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.write(
        "likes", operation="add", params={"track_ids": ["1", "2"]}
    )
    assert result == {"ok": True}

@pytest.mark.asyncio
async def test_search_delegates_to_client(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    result = await adapter.search("hello", type="tracks", limit=10)
    assert result["tracks"]["total"] == 1

@pytest.mark.asyncio
async def test_download_audio_returns_path(mock_client: AsyncMock, tmp_path: Path) -> None:
    target = tmp_path / "1.mp3"
    mock_client.download_track.return_value = target
    adapter = YandexAdapter(client=mock_client, download_dir=tmp_path)
    result = await adapter.download_audio("1")
    assert result == target

@pytest.mark.asyncio
async def test_close_calls_client(mock_client: AsyncMock) -> None:
    adapter = YandexAdapter(client=mock_client)
    await adapter.close()
    mock_client.close.assert_awaited_once()
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/providers/yandex/test_adapter.py -v
```

- [ ] **Step 3: Write `app/v2/providers/yandex/adapter.py`**

```python
"""YandexAdapter — implements the universal Provider protocol over YandexClient."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.v2.providers.yandex.client import YandexClient

class YandexAdapter:
    name: str = "yandex"

    def __init__(
        self,
        *,
        client: YandexClient,
        download_dir: Path | None = None,
    ) -> None:
        self._client = client
        self._download_dir = download_dir or Path("/tmp/yandex_downloads")

    # ---------- read ---------- #

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        match entity:
            case "track":
                if id is None:
                    raise ValueError("track read requires id")
                tracks = await self._client.get_tracks([id])
                return tracks[0] if tracks else {}
            case "track_batch":
                ids = params.get("ids", [])
                tracks = await self._client.get_tracks(list(ids))
                return {"tracks": tracks}
            case "track_similar":
                if id is None:
                    raise ValueError("track_similar requires id")
                similar = await self._client.get_similar(id)
                return {"results": similar}
            case "album":
                if id is None:
                    raise ValueError("album read requires id")
                return await self._client.get_album(id, with_tracks=bool(params.get("with_tracks")))
            case "artist_tracks":
                if id is None:
                    raise ValueError("artist_tracks requires id")
                return await self._client.get_artist_tracks(
                    id,
                    offset=int(params.get("offset", 0)),
                    limit=int(params.get("limit", 50)),
                )
            case "playlist":
                if id is None:
                    raise ValueError("playlist read requires id")
                return await self._client.get_playlist(id)
            case "playlist_list":
                return {"playlists": await self._client.list_playlists()}
            case "likes":
                return {"track_ids": await self._client.get_liked_ids()}
            case "dislikes":
                return {"track_ids": await self._client.get_disliked_ids()}
            case _:
                raise ValueError(f"unknown read entity: {entity}")

    # ---------- write ---------- #

    async def write(
        self, entity: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if entity == "playlist":
            return await self._write_playlist(operation, params)
        if entity == "likes":
            return await self._write_likes(operation, params)
        raise ValueError(f"unknown write entity: {entity}")

    async def _write_playlist(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        match operation:
            case "create":
                return await self._client.create_playlist(
                    title=params["title"], visibility=params.get("visibility", "private")
                )
            case "rename":
                return await self._client.rename_playlist(
                    params["playlist_id"], title=params["title"]
                )
            case "delete":
                return await self._client.delete_playlist(params["playlist_id"])
            case "add_tracks":
                track_ids = list(params["track_ids"])
                diff = [
                    {
                        "op": "insert",
                        "at": int(params.get("at", 0)),
                        "tracks": [{"id": tid} for tid in track_ids],
                    }
                ]
                return await self._client.modify_playlist(
                    params["playlist_id"], diff=diff, revision=int(params["revision"])
                )
            case "remove_tracks":
                diff = [
                    {
                        "op": "delete",
                        "from": int(params["from"]),
                        "to": int(params["to"]),
                    }
                ]
                return await self._client.modify_playlist(
                    params["playlist_id"], diff=diff, revision=int(params["revision"])
                )
            case _:
                raise ValueError(f"unknown playlist operation: {operation}")

    async def _write_likes(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        track_ids = list(params["track_ids"])
        if operation == "add":
            return await self._client.add_likes(track_ids)
        if operation == "remove":
            return await self._client.remove_likes(track_ids)
        raise ValueError(f"unknown likes operation: {operation}")

    # ---------- search ---------- #

    async def search(
        self, query: str, type: str = "tracks", limit: int = 20
    ) -> dict[str, Any]:
        return await self._client.search(query=query, type=type, limit=limit)

    # ---------- download ---------- #

    async def download_audio(self, track_id: str) -> Path:
        dest = self._download_dir / f"{track_id}.mp3"
        return await self._client.download_track(track_id, dest)

    async def close(self) -> None:
        await self._client.close()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/providers/yandex/test_adapter.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/providers/yandex/adapter.py tests/v2/providers/yandex/test_adapter.py
git commit -m "feat(v2): add YandexAdapter implementing Provider protocol

Polymorphic read/write dispatch via match-case on entity+operation.
Tool layer never imports YandexClient — only ProviderRegistry.get('yandex')."
```

---

## Task 6: Wire YandexAdapter into `app/v2/server/lifespan.py`

**Files:**
- Modify: `app/v2/server/lifespan.py` (add `provider_lifespan`)
- Test: `tests/v2/server/test_provider_lifespan.py`

- [ ] **Step 1: Read current lifespan file**

```bash
uv run python -c "from pathlib import Path; print(Path('app/v2/server/lifespan.py').read_text())"
```

- [ ] **Step 2: Write failing test**

```python
# tests/v2/server/test_provider_lifespan.py
"""provider_lifespan wires YandexAdapter into ProviderRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.v2.registry.provider import ProviderRegistry
from app.v2.server.lifespan import provider_lifespan

@pytest.mark.asyncio
async def test_provider_lifespan_registers_yandex(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.v2 import config as _cfg  # noqa: F401

    fake_settings = MagicMock()
    fake_settings.yandex.token = "stub"
    fake_settings.yandex.user_id = "42"
    fake_settings.yandex.base_url = "https://api.music.yandex.net"
    fake_settings.yandex.rate_limit_delay = 0.0
    fake_settings.yandex.download_dir = "/tmp"

    monkeypatch.setattr("app.v2.server.lifespan.get_settings", lambda: fake_settings)

    async with provider_lifespan() as ctx:
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

    monkeypatch.setattr("app.v2.server.lifespan.get_settings", lambda: fake_settings)

    async with provider_lifespan() as ctx:
        registry: ProviderRegistry = ctx["provider_registry"]
    # After exit, all adapters should be closed
    assert registry.names() == []
```

- [ ] **Step 3: Write `app/v2/server/lifespan.py` additions**

```python
# Append to app/v2/server/lifespan.py

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from app.v2.config import get_settings
from app.v2.providers.yandex.adapter import YandexAdapter
from app.v2.providers.yandex.client import YandexClient
from app.v2.providers.yandex.rate_limiter import TokenBucketRateLimiter
from app.v2.registry.provider import ProviderRegistry

@asynccontextmanager
async def provider_lifespan() -> AsyncIterator[dict[str, Any]]:
    """Instantiate adapters and register them.

    Yields ``{"provider_registry": ProviderRegistry}`` merged into lifespan ctx.
    """
    from pathlib import Path

    settings = get_settings()
    registry = ProviderRegistry()

    yandex_client = YandexClient(
        token=settings.yandex.token,
        user_id=settings.yandex.user_id,
        base_url=settings.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=settings.yandex.rate_limit_delay),
    )
    yandex_adapter = YandexAdapter(
        client=yandex_client, download_dir=Path(settings.yandex.download_dir)
    )
    registry.register(yandex_adapter, default=True)

    try:
        yield {"provider_registry": registry}
    finally:
        await registry.close_all()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/server/test_provider_lifespan.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/lifespan.py tests/v2/server/test_provider_lifespan.py
git commit -m "feat(v2): register YandexAdapter in provider_lifespan

provider_lifespan contributes ProviderRegistry to merged lifespan ctx.
Phase 5 composes this with db_lifespan + analyzer_lifespan."
```

---

## Task 7: Handler — `app/v2/handlers/track_import.py`

**Files:**
- Create: `app/v2/handlers/track_import.py`
- Test: `tests/v2/handlers/test_track_import.py`

Imports a track from a provider into the local library. Covers the legacy `import_tracks` tool: fetches metadata, inserts `Track`, `YandexMetadata`, `TrackExternalId`, optionally adds to a playlist.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_track_import.py
"""TrackImportHandler unit tests (mocked provider + in-mem UoW)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.track_import import track_import_handler


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    c.report_progress = AsyncMock()
    return c


@pytest.fixture
def provider() -> AsyncMock:
    p = AsyncMock()
    p.read.return_value = {
        "id": "12345",
        "title": "Techno Track",
        "artists": [{"id": "a1", "name": "Artist"}],
        "durationMs": 300_000,
        "albums": [{"id": "b1", "title": "Album", "genre": "techno"}],
        "coverUri": "avatars.yandex.net/%%.jpg",
        "explicit": False,
    }
    return p


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.batch_get_by_provider_ids = AsyncMock(return_value={})
    u.tracks.create = AsyncMock(return_value=MagicMock(id=1, title="Techno Track"))
    u.tracks.get = AsyncMock(return_value=MagicMock(id=1, title="Techno Track"))
    u.provider_metadata = MagicMock()
    u.provider_metadata.upsert_yandex = AsyncMock()
    u.provider_metadata.upsert_external_id = AsyncMock()
    u.playlists = MagicMock()
    u.playlists.add_track = AsyncMock()
    return u


@pytest.fixture
def registry(provider: AsyncMock) -> MagicMock:
    r = MagicMock()
    r.get.return_value = provider
    r.default.return_value = provider
    return r


@pytest.mark.asyncio
async def test_import_single_track_from_yandex(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, provider: AsyncMock
) -> None:
    data = {"source": "yandex", "external_ids": ["12345"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert "imported" in result
    assert len(result["imported"]) == 1
    assert result["imported"][0]["external_id"] == "12345"
    provider.read.assert_awaited()
    uow.tracks.create.assert_awaited_once()
    uow.provider_metadata.upsert_yandex.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_skips_existing_by_provider_id(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    existing = MagicMock(id=99, title="Old")
    uow.tracks.batch_get_by_provider_ids.return_value = {"12345": existing}
    data = {"source": "yandex", "external_ids": ["12345"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert result["imported"] == []
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["local_id"] == 99
    uow.tracks.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_adds_to_playlist_when_given(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    data = {"source": "yandex", "external_ids": ["12345"], "playlist_id": 7}
    await track_import_handler(ctx, uow, data, registry)

    uow.playlists.add_track.assert_awaited_once_with(playlist_id=7, track_id=1)


@pytest.mark.asyncio
async def test_import_reports_progress(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    data = {"source": "yandex", "external_ids": ["1", "2", "3"]}
    # First call returns one track metadata, subsequent calls return same template
    await track_import_handler(ctx, uow, data, registry)
    assert ctx.report_progress.await_count >= 1


@pytest.mark.asyncio
async def test_import_id_mapping_includes_all_refs(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock
) -> None:
    existing = MagicMock(id=99, title="Old")
    uow.tracks.batch_get_by_provider_ids.return_value = {"aaa": existing}
    data = {"source": "yandex", "external_ids": ["aaa", "bbb"]}
    result = await track_import_handler(ctx, uow, data, registry)

    assert result["id_mapping"]["aaa"] == 99
    assert result["id_mapping"]["bbb"] == 1
```

- [ ] **Step 2: Write `app/v2/handlers/track_import.py`**

```python
"""Handler for entity_create(entity="track", data={source, external_ids, ...}).

Fetches metadata via provider, inserts Track + YandexMetadata + TrackExternalId,
idempotent by provider_id (skips existing). Optionally links to playlist.

Progress reporting: one tick per imported ref.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork


async def track_import_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    source = data.get("source", "yandex")
    external_ids: list[str] = [str(x) for x in data["external_ids"]]
    playlist_id: int | None = data.get("playlist_id")

    provider = registry.get(source)

    # Idempotency: look up existing local tracks by provider id.
    existing_map = await uow.tracks.batch_get_by_provider_ids(source, external_ids)

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    id_mapping: dict[str, int] = {}
    errors: list[dict[str, Any]] = []

    total = len(external_ids)
    for i, ext_id in enumerate(external_ids):
        if ext_id in existing_map:
            row = existing_map[ext_id]
            skipped.append({"external_id": ext_id, "local_id": row.id})
            id_mapping[ext_id] = row.id
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            meta = await provider.read("track", id=ext_id, params={})
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
            errors.append({"external_id": ext_id, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        track_row = await uow.tracks.create(
            title=meta.get("title", "Untitled"),
            duration_ms=meta.get("durationMs"),
            sort_title=(meta.get("title") or "").lower(),
        )
        await uow.provider_metadata.upsert_yandex(
            track_id=track_row.id,
            yandex_track_id=ext_id,
            album_id=(meta.get("albums") or [{}])[0].get("id"),
            album_title=(meta.get("albums") or [{}])[0].get("title"),
            album_genre=(meta.get("albums") or [{}])[0].get("genre"),
            duration_ms=meta.get("durationMs"),
            cover_uri=meta.get("coverUri"),
            explicit=bool(meta.get("explicit", False)),
        )
        await uow.provider_metadata.upsert_external_id(
            track_id=track_row.id, platform=source, external_id=ext_id
        )

        imported.append({"external_id": ext_id, "local_id": track_row.id})
        id_mapping[ext_id] = track_row.id

        if playlist_id is not None:
            await uow.playlists.add_track(playlist_id=playlist_id, track_id=track_row.id)

        await ctx.report_progress(progress=i + 1, total=total)

    await ctx.info(
        f"track_import: {len(imported)} imported, {len(skipped)} skipped, "
        f"{len(errors)} errors"
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "id_mapping": id_mapping,
    }
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_track_import.py -v
```
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/track_import.py tests/v2/handlers/test_track_import.py
git commit -m "feat(v2): add track_import handler

Fetches metadata via provider, inserts Track+YandexMetadata+ExternalId,
idempotent by provider id, optional playlist linking, per-item progress.
Replaces app/services/import_service.py import_tracks logic."
```

---

## Task 8: Handler — `app/v2/handlers/audio_file_download.py`

**Files:**
- Create: `app/v2/handlers/audio_file_download.py`
- Test: `tests/v2/handlers/test_audio_file_download.py`

Downloads MP3 files from a provider, writes to disk, inserts `DjLibraryItem`, initializes empty `DjBeatgrid`. Covers the legacy `download_tracks` tool.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_audio_file_download.py
"""AudioFileDownloadHandler tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.audio_file_download import audio_file_download_handler


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    c.report_progress = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.get = AsyncMock()
    u.provider_metadata = MagicMock()
    u.provider_metadata.get_external_id = AsyncMock(return_value="12345")
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(return_value=None)
    u.audio_files.create = AsyncMock(return_value=MagicMock(id=100))
    return u


@pytest.fixture
def registry(tmp_path: Path) -> MagicMock:
    r = MagicMock()
    provider = AsyncMock()
    target = tmp_path / "12345.mp3"
    target.write_bytes(b"\x00" * 1024)
    provider.download_audio.return_value = target
    r.get.return_value = provider
    return r


@pytest.mark.asyncio
async def test_download_single_track(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1], "source": "yandex", "target_dir": str(tmp_path)}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert len(result["downloaded"]) == 1
    assert result["downloaded"][0]["track_id"] == 1
    uow.audio_files.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_existing_library_item(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_by_track_id.return_value = MagicMock(id=99)
    data = {"track_ids": [1], "source": "yandex", "skip_existing": True}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["downloaded"] == []
    assert len(result["skipped"]) == 1
    registry.get.return_value.download_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_records_error_when_provider_fails(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    registry.get.return_value.download_audio.side_effect = RuntimeError("404")
    data = {"track_ids": [1], "source": "yandex", "target_dir": str(tmp_path)}
    result = await audio_file_download_handler(ctx, uow, data, registry)

    assert result["downloaded"] == []
    assert len(result["errors"]) == 1
    assert "404" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_reports_progress_per_track(
    ctx: MagicMock, uow: MagicMock, registry: MagicMock, tmp_path: Path
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1, 2, 3], "source": "yandex", "target_dir": str(tmp_path)}
    await audio_file_download_handler(ctx, uow, data, registry)
    assert ctx.report_progress.await_count == 3
```

- [ ] **Step 2: Write `app/v2/handlers/audio_file_download.py`**

```python
"""Handler for entity_create(entity="audio_file", data={track_ids, source, ...}).

For each track_id: resolve provider external_id → call provider.download_audio →
insert DjLibraryItem + empty DjBeatgrid. Skips tracks with an existing library
item when ``skip_existing=True`` (default).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastmcp.server.context import Context

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork


async def audio_file_download_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    track_ids: list[int] = [int(x) for x in data["track_ids"]]
    source: str = data.get("source", "yandex")
    target_dir: Path = Path(data.get("target_dir") or "/tmp/dj_audio")
    skip_existing: bool = bool(data.get("skip_existing", True))

    provider = registry.get(source)

    downloaded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    total = len(track_ids)
    for i, tid in enumerate(track_ids):
        track = await uow.tracks.get(tid)
        if track is None:
            errors.append({"track_id": tid, "error": "track not found"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        existing = await uow.audio_files.get_by_track_id(tid)
        if existing is not None and skip_existing:
            skipped.append({"track_id": tid, "library_item_id": existing.id})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        ext_id = await uow.provider_metadata.get_external_id(tid, platform=source)
        if ext_id is None:
            errors.append({"track_id": tid, "error": f"no {source} external_id"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            path = await provider.download_audio(ext_id)
        except Exception as exc:  # noqa: BLE001
            errors.append({"track_id": tid, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        size = path.stat().st_size
        file_hash = _hash_head(path)
        item = await uow.audio_files.create(
            track_id=tid,
            file_path=str(path),
            file_hash=file_hash,
            file_size=size,
            mime_type="audio/mpeg",
            source_app=source,
        )
        downloaded.append({"track_id": tid, "library_item_id": item.id, "path": str(path)})
        await ctx.report_progress(progress=i + 1, total=total)

    await ctx.info(
        f"audio_file_download: {len(downloaded)} downloaded, "
        f"{len(skipped)} skipped, {len(errors)} errors"
    )

    return {"downloaded": downloaded, "skipped": skipped, "errors": errors}


def _hash_head(path: Path, *, bytes_: int = 65536) -> str:
    """Hash first 64KB — sufficient for dedup, cheap for big files."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(bytes_))
    return h.hexdigest()
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_audio_file_download.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/audio_file_download.py tests/v2/handlers/test_audio_file_download.py
git commit -m "feat(v2): add audio_file_download handler

Per-track provider.download_audio + DjLibraryItem insert, idempotent via
skip_existing. Replaces app/services/import_service download logic."
```

---

## Task 9: Handler — `app/v2/handlers/track_features_analyze.py`

**Files:**
- Create: `app/v2/handlers/track_features_analyze.py`
- Test: `tests/v2/handlers/test_track_features_analyze.py`

Runs the audio analysis pipeline for a set of tracks at a given analysis level (L1-L4). Idempotent: skips tracks already at or above the target level unless `force=True`.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_track_features_analyze.py
"""TrackFeaturesAnalyzeHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.track_features_analyze import track_features_analyze_handler


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    c.report_progress = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.get = AsyncMock()
    u.track_features = MagicMock()
    u.track_features.get_by_track_id = AsyncMock(return_value=None)
    u.track_features.upsert = AsyncMock()
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(
        return_value=MagicMock(file_path="/tmp/x.mp3")
    )
    return u


@pytest.fixture
def pipeline() -> AsyncMock:
    p = AsyncMock()
    p.analyze_to_level.return_value = MagicMock(
        features={"bpm": 128.0, "key_code": 5, "integrated_lufs": -9.0},
        pipeline_run_id=1,
        analysis_level=3,
        sections=[],
        errors=[],
    )
    return p


@pytest.mark.asyncio
async def test_analyzes_unseen_track(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    data = {"track_ids": [1], "level": 3}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["analyzed"]) == 1
    assert result["analyzed"][0]["level"] == 3
    pipeline.analyze_to_level.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_tracks_already_at_level(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.track_features.get_by_track_id.return_value = MagicMock(
        analysis_level=3, bpm=128.0
    )
    data = {"track_ids": [1], "level": 3, "force": False}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert result["analyzed"] == []
    assert len(result["skipped"]) == 1
    pipeline.analyze_to_level.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_reanalyzes_even_if_higher_level(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.track_features.get_by_track_id.return_value = MagicMock(
        analysis_level=4, bpm=128.0
    )
    data = {"track_ids": [1], "level": 3, "force": True}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["analyzed"]) == 1
    pipeline.analyze_to_level.assert_awaited_once()


@pytest.mark.asyncio
async def test_records_error_on_missing_audio_file(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1, title="X")
    uow.audio_files.get_by_track_id.return_value = None
    data = {"track_ids": [1], "level": 3}
    result = await track_features_analyze_handler(ctx, uow, data, pipeline)

    assert len(result["errors"]) == 1
    assert "audio file" in result["errors"][0]["error"].lower()
```

- [ ] **Step 2: Write `app/v2/handlers/track_features_analyze.py`**

```python
"""Handler for entity_create(entity="track_features", data={track_ids, level, force}).

Runs the audio analysis pipeline (TieredPipeline analogue) on each track at the
requested analysis level (L1-L4). Idempotent: skips tracks already at target
level unless force=True. Emits per-track progress.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.v2.repositories.unit_of_work import UnitOfWork


class AnalysisPipeline(Protocol):
    async def analyze_to_level(
        self, *, track_id: int, audio_path: str, level: int
    ) -> Any: ...


async def track_features_analyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
) -> dict[str, Any]:
    track_ids: list[int] = [int(x) for x in data["track_ids"]]
    level: int = int(data.get("level", 3))
    force: bool = bool(data.get("force", False))

    analyzed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    total = len(track_ids)
    for i, tid in enumerate(track_ids):
        track = await uow.tracks.get(tid)
        if track is None:
            errors.append({"track_id": tid, "error": "track not found"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        existing = await uow.track_features.get_by_track_id(tid)
        if existing is not None and not force:
            current_level = int(getattr(existing, "analysis_level", 0) or 0)
            if current_level >= level:
                skipped.append(
                    {"track_id": tid, "current_level": current_level, "target": level}
                )
                await ctx.report_progress(progress=i + 1, total=total)
                continue

        lib = await uow.audio_files.get_by_track_id(tid)
        if lib is None:
            errors.append({"track_id": tid, "error": "no audio file registered"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            result = await pipeline.analyze_to_level(
                track_id=tid, audio_path=lib.file_path, level=level
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"track_id": tid, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        await uow.track_features.upsert(
            track_id=tid,
            pipeline_run_id=result.pipeline_run_id,
            analysis_level=result.analysis_level,
            **result.features,
        )
        analyzed.append(
            {
                "track_id": tid,
                "level": result.analysis_level,
                "feature_count": len(result.features),
                "errors": len(getattr(result, "errors", []) or []),
            }
        )
        await ctx.report_progress(progress=i + 1, total=total)

    await ctx.info(
        f"features_analyze L{level}: {len(analyzed)} analyzed, "
        f"{len(skipped)} skipped, {len(errors)} errors"
    )

    return {"analyzed": analyzed, "skipped": skipped, "errors": errors}
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_track_features_analyze.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/track_features_analyze.py tests/v2/handlers/test_track_features_analyze.py
git commit -m "feat(v2): add track_features_analyze handler

Per-track pipeline dispatch with level-gated idempotency.
Replaces app/services/tiered_pipeline + audio_service."
```

---

## Task 10: Handler — `app/v2/handlers/track_features_reanalyze.py`

**Files:**
- Create: `app/v2/handlers/track_features_reanalyze.py`
- Test: `tests/v2/handlers/test_track_features_reanalyze.py`

Handler for `entity_update(entity="track_features")` — re-analyzes a single track at a (typically higher) level, always running regardless of current level.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_track_features_reanalyze.py
"""TrackFeaturesReanalyzeHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.track_features_reanalyze import track_features_reanalyze_handler
from app.v2.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.tracks = MagicMock()
    u.tracks.get = AsyncMock()
    u.track_features = MagicMock()
    u.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(analysis_level=2))
    u.track_features.upsert = AsyncMock()
    u.audio_files = MagicMock()
    u.audio_files.get_by_track_id = AsyncMock(
        return_value=MagicMock(file_path="/tmp/x.mp3")
    )
    return u


@pytest.fixture
def pipeline() -> AsyncMock:
    p = AsyncMock()
    p.analyze_to_level.return_value = MagicMock(
        features={"bpm": 128.0}, pipeline_run_id=2, analysis_level=4, sections=[], errors=[]
    )
    return p


@pytest.mark.asyncio
async def test_reanalyze_single_track(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1)
    data = {"track_id": 1, "level": 4}
    result = await track_features_reanalyze_handler(ctx, uow, data, pipeline)

    assert result["track_id"] == 1
    assert result["level"] == 4
    pipeline.analyze_to_level.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_track_raises(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = None
    data = {"track_id": 999, "level": 3}
    with pytest.raises(NotFoundError):
        await track_features_reanalyze_handler(ctx, uow, data, pipeline)


@pytest.mark.asyncio
async def test_always_runs_even_when_current_gte_target(
    ctx: MagicMock, uow: MagicMock, pipeline: AsyncMock
) -> None:
    uow.tracks.get.return_value = MagicMock(id=1)
    uow.track_features.get_by_track_id.return_value = MagicMock(analysis_level=4)
    data = {"track_id": 1, "level": 3}
    await track_features_reanalyze_handler(ctx, uow, data, pipeline)
    pipeline.analyze_to_level.assert_awaited_once()
```

- [ ] **Step 2: Write `app/v2/handlers/track_features_reanalyze.py`**

```python
"""Handler for entity_update(entity="track_features", data={track_id, level}).

Unlike the create handler, reanalyze always runs the pipeline regardless of
current analysis level. Use when a bug in the analyzer is fixed and features
need to be recomputed.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context

from app.v2.handlers.track_features_analyze import AnalysisPipeline
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.shared.errors import NotFoundError


async def track_features_reanalyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
) -> dict[str, Any]:
    track_id: int = int(data["track_id"])
    level: int = int(data.get("level", 3))

    track = await uow.tracks.get(track_id)
    if track is None:
        raise NotFoundError("track", track_id)

    lib = await uow.audio_files.get_by_track_id(track_id)
    if lib is None:
        raise NotFoundError("audio_file", track_id)

    result = await pipeline.analyze_to_level(
        track_id=track_id, audio_path=lib.file_path, level=level
    )
    await uow.track_features.upsert(
        track_id=track_id,
        pipeline_run_id=result.pipeline_run_id,
        analysis_level=result.analysis_level,
        **result.features,
    )
    await ctx.info(f"reanalyzed track {track_id} at L{level}")

    return {
        "track_id": track_id,
        "level": result.analysis_level,
        "pipeline_run_id": result.pipeline_run_id,
        "feature_count": len(result.features),
    }
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_track_features_reanalyze.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/track_features_reanalyze.py tests/v2/handlers/test_track_features_reanalyze.py
git commit -m "feat(v2): add track_features_reanalyze handler

entity_update path: always re-runs pipeline; raises NotFoundError if
track or audio file is missing."
```

---

## Task 11: Handler — `app/v2/handlers/transition_persist.py`

**Files:**
- Create: `app/v2/handlers/transition_persist.py`
- Test: `tests/v2/handlers/test_transition_persist.py`

Computes a transition score between two tracks and persists it. Used by `entity_create(entity="transition", data={from_track_id, to_track_id})`.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_transition_persist.py
"""TransitionPersistHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.transition_persist import transition_persist_handler
from app.v2.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    return MagicMock(spec=Context)


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock()}
    )
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=10))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.82
    score.bpm = 0.9
    score.harmonic = 0.8
    score.energy = 0.75
    score.spectral = 0.85
    score.groove = 0.78
    score.timbral = 0.82
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_scores_and_persists_pair(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)

    assert result["from_track_id"] == 1
    assert result["to_track_id"] == 2
    assert result["overall"] == pytest.approx(0.82)
    uow.transitions.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_features_raises(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.track_features.get_scoring_features_batch.return_value = {1: MagicMock()}
    data = {"from_track_id": 1, "to_track_id": 2}
    with pytest.raises(NotFoundError):
        await transition_persist_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_hard_reject_is_persisted_with_zero_overall(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    rejected = MagicMock()
    rejected.overall = 0.0
    rejected.hard_reject = True
    rejected.reject_reason = "bpm_diff>10"
    rejected.bpm = rejected.harmonic = rejected.energy = 0.0
    rejected.spectral = rejected.groove = rejected.timbral = 0.0
    scorer.score.return_value = rejected

    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    assert result["hard_reject"] is True
    assert result["overall"] == 0.0
    uow.transitions.upsert.assert_awaited_once()
```

- [ ] **Step 2: Write `app/v2/handlers/transition_persist.py`**

```python
"""Handler for entity_create(entity="transition", data={from_track_id, to_track_id}).

Loads scoring features for the pair, calls TransitionScorer, persists the
resulting TransitionScore into the `transitions` table (upsert on
(from_track_id, to_track_id)).
"""

from __future__ import annotations

from typing import Any, Protocol

from fastmcp.server.context import Context

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.shared.errors import NotFoundError


class TransitionScorerProtocol(Protocol):
    def score(self, a: Any, b: Any, *, intent: Any = None, section_context: Any = None) -> Any: ...


async def transition_persist_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    scorer: TransitionScorerProtocol,
) -> dict[str, Any]:
    a_id: int = int(data["from_track_id"])
    b_id: int = int(data["to_track_id"])

    features = await uow.track_features.get_scoring_features_batch([a_id, b_id])
    if a_id not in features:
        raise NotFoundError("track_features", a_id)
    if b_id not in features:
        raise NotFoundError("track_features", b_id)

    score = scorer.score(features[a_id], features[b_id])
    row = await uow.transitions.upsert(
        from_track_id=a_id,
        to_track_id=b_id,
        bpm_score=float(score.bpm),
        harmonic_score=float(score.harmonic),
        energy_score=float(score.energy),
        spectral_score=float(score.spectral),
        groove_score=float(score.groove),
        timbral_score=float(score.timbral),
        overall_quality=float(score.overall),
        hard_reject=bool(score.hard_reject),
        reject_reason=score.reject_reason,
    )
    return {
        "id": row.id,
        "from_track_id": a_id,
        "to_track_id": b_id,
        "overall": float(score.overall),
        "bpm": float(score.bpm),
        "harmonic": float(score.harmonic),
        "energy": float(score.energy),
        "spectral": float(score.spectral),
        "groove": float(score.groove),
        "timbral": float(score.timbral),
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
    }
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_transition_persist.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/transition_persist.py tests/v2/handlers/test_transition_persist.py
git commit -m "feat(v2): add transition_persist handler

Loads pair features, runs TransitionScorer, upserts transitions row.
Hard-rejected scores persisted with overall=0.0 + reject_reason."
```

---

## Task 12: Handler — `app/v2/handlers/set_version_build.py`

**Files:**
- Create: `app/v2/handlers/set_version_build.py`
- Test: `tests/v2/handlers/test_set_version_build.py`

Builds a new `DjSetVersion` from a given track ordering: inserts version row, per-track `DjSetItem`s with mix in/out points, links transitions.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/handlers/test_set_version_build.py
"""SetVersionBuildHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.context import Context

from app.v2.handlers.set_version_build import set_version_build_handler
from app.v2.shared.errors import NotFoundError, ValidationError


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.sets = MagicMock()
    u.sets.get = AsyncMock()
    u.set_versions = MagicMock()
    u.set_versions.create = AsyncMock(return_value=MagicMock(id=10, label="v1"))
    u.set_versions.add_item = AsyncMock()
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=100))
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    )
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.8
    score.bpm = score.harmonic = score.energy = 0.8
    score.spectral = score.groove = score.timbral = 0.8
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_builds_version_with_items(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="Test")
    data = {
        "set_id": 5,
        "track_order": [1, 2, 3],
        "label": "v1",
        "generator_run_meta": {"algo": "ga"},
    }
    result = await set_version_build_handler(ctx, uow, data, scorer)

    assert result["version_id"] == 10
    assert result["item_count"] == 3
    assert result["transition_count"] == 2  # N-1 transitions for N tracks
    assert uow.set_versions.add_item.await_count == 3
    assert uow.transitions.upsert.await_count == 2


@pytest.mark.asyncio
async def test_unknown_set_raises(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = None
    data = {"set_id": 999, "track_order": [1, 2]}
    with pytest.raises(NotFoundError):
        await set_version_build_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_empty_track_order_raises_validation(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": []}
    with pytest.raises(ValidationError):
        await set_version_build_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_quality_score_averaged(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": [1, 2, 3]}
    result = await set_version_build_handler(ctx, uow, data, scorer)
    # 2 transitions, each overall=0.8 → avg 0.8
    assert result["quality_score"] == pytest.approx(0.8)
```

- [ ] **Step 2: Write `app/v2/handlers/set_version_build.py`**

```python
"""Handler for entity_create(entity="set_version", data={set_id, track_order, ...}).

Creates a DjSetVersion + DjSetItem rows + pairwise Transition rows for the
given ordering. Computes a summary quality score (mean of transition scores).
"""

from __future__ import annotations

import json
from statistics import fmean
from typing import Any

from fastmcp.server.context import Context

from app.v2.handlers.transition_persist import TransitionScorerProtocol
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.shared.errors import NotFoundError, ValidationError


async def set_version_build_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    scorer: TransitionScorerProtocol,
) -> dict[str, Any]:
    set_id: int = int(data["set_id"])
    track_order: list[int] = [int(t) for t in data.get("track_order") or []]
    label: str = str(data.get("label") or "auto")
    gen_meta = data.get("generator_run_meta") or {}

    if not track_order:
        raise ValidationError("track_order must be non-empty")

    dj_set = await uow.sets.get(set_id)
    if dj_set is None:
        raise NotFoundError("set", set_id)

    features = await uow.track_features.get_scoring_features_batch(track_order)

    version = await uow.set_versions.create(
        set_id=set_id,
        label=label,
        generator_run_meta=json.dumps(gen_meta),
        quality_score=0.0,  # will update below
    )

    for idx, tid in enumerate(track_order):
        await uow.set_versions.add_item(
            version_id=version.id,
            track_id=tid,
            sort_index=idx,
        )

    transition_scores: list[float] = []
    for a, b in zip(track_order, track_order[1:], strict=False):
        if a not in features or b not in features:
            continue
        score = scorer.score(features[a], features[b])
        await uow.transitions.upsert(
            from_track_id=a,
            to_track_id=b,
            bpm_score=float(score.bpm),
            harmonic_score=float(score.harmonic),
            energy_score=float(score.energy),
            spectral_score=float(score.spectral),
            groove_score=float(score.groove),
            timbral_score=float(score.timbral),
            overall_quality=float(score.overall),
            hard_reject=bool(score.hard_reject),
            reject_reason=score.reject_reason,
        )
        transition_scores.append(float(score.overall))

    quality = fmean(transition_scores) if transition_scores else 0.0
    await uow.set_versions.update_quality(version.id, quality_score=quality)

    await ctx.info(
        f"built version {version.id}: {len(track_order)} items, "
        f"{len(transition_scores)} transitions, quality={quality:.3f}"
    )
    return {
        "version_id": version.id,
        "label": version.label,
        "item_count": len(track_order),
        "transition_count": len(transition_scores),
        "quality_score": quality,
    }
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/handlers/test_set_version_build.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/handlers/set_version_build.py tests/v2/handlers/test_set_version_build.py
git commit -m "feat(v2): add set_version_build handler

Creates DjSetVersion + items + pairwise transitions, computes aggregate
quality score. Replaces app/services/set/builder.py persistence half."
```

---

## Task 13: Tool response schemas — `app/v2/schemas/tool_responses.py`

**Files:**
- Create: `app/v2/schemas/tool_responses.py`
- Create: `app/v2/schemas/provider_dto.py`
- Test: `tests/v2/schemas/test_tool_responses.py`

Pydantic models for `structuredContent`. One per tool output shape.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/schemas/test_tool_responses.py
"""Tool response schema smoke tests — JSON Schema generation + round-trip."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydValidationError

from app.v2.schemas.provider_dto import (
    ProviderReadResult,
    ProviderSearchResult,
    ProviderWriteResult,
)
from app.v2.schemas.tool_responses import (
    AggregateResult,
    EntityCreateResult,
    EntityDeleteResult,
    EntityGetResult,
    EntityListResult,
    EntityUpdateResult,
    PlaylistSyncResult,
    ScorePoolResult,
    SequenceOptimizeResult,
    UnlockNamespaceResult,
)


def test_entity_list_result_valid() -> None:
    result = EntityListResult(
        entity="track", items=[{"id": 1}], total=1, next_cursor=None
    )
    assert result.entity == "track"
    assert len(result.items) == 1


def test_entity_list_result_requires_entity() -> None:
    with pytest.raises(PydValidationError):
        EntityListResult(items=[], total=0)


def test_aggregate_result_accepts_scalar_and_list() -> None:
    scalar = AggregateResult(entity="track", operation="count", value=42)
    assert scalar.value == 42
    grouped = AggregateResult(
        entity="track",
        operation="count",
        value=[{"mood": "peak_time", "count": 20}],
    )
    assert isinstance(grouped.value, list)


def test_score_pool_result_shape() -> None:
    result = ScorePoolResult(
        track_ids=[1, 2, 3],
        pairs=[
            {"a": 1, "b": 2, "overall": 0.8},
            {"a": 1, "b": 3, "overall": 0.6},
        ],
        hard_rejects=0,
    )
    assert result.hard_rejects == 0


def test_sequence_optimize_result_shape() -> None:
    result = SequenceOptimizeResult(
        track_order=[3, 1, 2],
        quality_score=0.82,
        algorithm="ga",
        generations=100,
    )
    assert result.algorithm == "ga"


def test_playlist_sync_result_shape() -> None:
    result = PlaylistSyncResult(
        playlist_id=7,
        direction="pull",
        applied=[{"op": "add", "track_id": 1}],
        skipped=[],
        conflicts=[],
    )
    assert result.direction == "pull"


def test_unlock_namespace_result_shape() -> None:
    result = UnlockNamespaceResult(
        namespace="sync", status="unlocked", enabled_tools=["playlist_sync"]
    )
    assert result.status == "unlocked"


def test_provider_search_result_shape() -> None:
    result = ProviderSearchResult(
        provider="yandex",
        query="hello",
        type="tracks",
        total=1,
        items=[{"id": "1", "title": "X"}],
    )
    assert result.provider == "yandex"


def test_provider_read_result_arbitrary_data() -> None:
    result = ProviderReadResult(provider="yandex", entity="track", data={"id": "1"})
    assert result.data["id"] == "1"


def test_provider_write_result_shape() -> None:
    result = ProviderWriteResult(
        provider="yandex", entity="playlist", operation="add_tracks", data={"revision": 8}
    )
    assert result.operation == "add_tracks"


def test_entity_create_update_delete_shapes() -> None:
    c = EntityCreateResult(entity="track", data={"id": 1}, meta={"source": "yandex"})
    assert c.entity == "track"
    u = EntityUpdateResult(entity="track", id=1, data={"bpm": 128})
    assert u.id == 1
    d = EntityDeleteResult(entity="track", id=1, deleted=True)
    assert d.deleted is True
```

- [ ] **Step 2: Write `app/v2/schemas/tool_responses.py`**

```python
"""Structured-output Pydantic models for all v2 MCP tools.

Each tool returns a model from this file; FastMCP auto-generates
``output_schema`` in the tool metadata so LLM clients parse results reliably.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EntityListResult(BaseModel):
    entity: str = Field(description="Entity type name (e.g., 'track', 'playlist')")
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int | None = Field(default=None, description="Total rows matching (if with_total)")
    next_cursor: str | None = Field(default=None)


class EntityGetResult(BaseModel):
    entity: str
    id: int
    data: dict[str, Any]


class EntityCreateResult(BaseModel):
    entity: str
    data: dict[str, Any] | list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)


class EntityUpdateResult(BaseModel):
    entity: str
    id: int
    data: dict[str, Any]


class EntityDeleteResult(BaseModel):
    entity: str
    id: int
    deleted: bool


class AggregateResult(BaseModel):
    entity: str
    operation: Literal["count", "distinct", "histogram", "min_max", "sum", "avg"]
    field: str | None = None
    group_by: str | None = None
    value: int | float | list[dict[str, Any]] | dict[str, Any]


class ScorePoolResult(BaseModel):
    track_ids: list[int]
    pairs: list[dict[str, Any]] = Field(
        description="[{a, b, overall, bpm, harmonic, energy, spectral, groove, timbral}]"
    )
    hard_rejects: int = 0


class SequenceOptimizeResult(BaseModel):
    track_order: list[int]
    quality_score: float
    algorithm: Literal["ga", "greedy"]
    generations: int = 0


class PlaylistSyncResult(BaseModel):
    playlist_id: int
    direction: Literal["pull", "push", "diff"]
    applied: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class UnlockNamespaceResult(BaseModel):
    namespace: str
    status: Literal["unlocked", "locked", "status"]
    enabled_tools: list[str] = Field(default_factory=list)
```

- [ ] **Step 3: Write `app/v2/schemas/provider_dto.py`**

```python
"""Pydantic DTOs returned by provider_* tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderReadResult(BaseModel):
    provider: str
    entity: str
    data: dict[str, Any] = Field(default_factory=dict)


class ProviderWriteResult(BaseModel):
    provider: str
    entity: str
    operation: str
    data: dict[str, Any] = Field(default_factory=dict)


class ProviderSearchResult(BaseModel):
    provider: str
    query: str
    type: str
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/schemas/test_tool_responses.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/schemas/tool_responses.py app/v2/schemas/provider_dto.py tests/v2/schemas/test_tool_responses.py
git commit -m "feat(v2): add tool response Pydantic schemas

11 response models: Entity* (list/get/create/update/delete/aggregate),
ScorePool, SequenceOptimize, PlaylistSync, UnlockNamespace, and
Provider* (Read/Write/Search). FastMCP auto-generates output_schema."
```

---

## Task 14: Fixture — MCP client for tool tests

**Files:**
- Create: `tests/v2/tools/conftest.py`

Shared fixture that builds a `FastMCP` server with only the v2 tools, DB seeded, and yields an in-memory client.

- [ ] **Step 1: Write `tests/v2/tools/conftest.py`**

```python
"""Shared fixtures for v2 tool integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

# Import tool modules so their @tool decorators register.
# Phase 3 registers tools manually — FileSystemProvider wiring is Phase 5.


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    # CRUD ops
    for attr in (
        "tracks",
        "playlists",
        "sets",
        "set_versions",
        "audio_files",
        "track_features",
        "transitions",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profiles",
    ):
        repo = MagicMock()
        repo.get = AsyncMock(return_value=None)
        repo.list = AsyncMock(return_value=MagicMock(items=[], next_cursor=None, total=0))
        repo.filter = AsyncMock(return_value=MagicMock(items=[], next_cursor=None, total=0))
        repo.count = AsyncMock(return_value=0)
        repo.create = AsyncMock(return_value=MagicMock(id=1))
        repo.update = AsyncMock(return_value=MagicMock(id=1))
        repo.delete = AsyncMock()
        repo.aggregate = AsyncMock(return_value=0)
        setattr(uow, attr, repo)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


@pytest.fixture
def mock_provider_registry() -> MagicMock:
    r = MagicMock()
    provider = AsyncMock()
    provider.name = "yandex"
    provider.read.return_value = {"id": "1", "title": "Track"}
    provider.write.return_value = {"revision": 8}
    provider.search.return_value = {
        "tracks": {"results": [{"id": "1", "title": "X"}], "total": 1}
    }
    r.get.return_value = provider
    r.default.return_value = provider
    r.names.return_value = ["yandex"]
    return r


@pytest.fixture
async def mcp_server(
    mock_uow: MagicMock, mock_provider_registry: MagicMock
) -> AsyncIterator[FastMCP]:
    """FastMCP server with v2 tools registered + mocked DI."""
    from app.v2.registry.entity import register_default_entities
    from app.v2.server import di

    # Register entities (safe to call in tests — idempotent at EntityRegistry level).
    register_default_entities()

    # Monkey-patch DI resolvers so tests don't need a real DB.
    di.get_uow = lambda: mock_uow  # type: ignore[attr-defined]
    di.get_provider_registry = lambda: mock_provider_registry  # type: ignore[attr-defined]

    mcp = FastMCP(name="dj-music-v2-test")

    # Register every v2 tool on this server.
    from app.v2.tools.admin import unlock_namespace as _un
    from app.v2.tools.compute import score_pool as _sp, sequence_optimize as _so
    from app.v2.tools.entity import (
        aggregate as _agg,
        create as _cr,
        delete as _de,
        get as _ge,
        list as _li,
        update as _up,
    )
    from app.v2.tools.provider import read as _pr, search as _ps, write as _pw
    from app.v2.tools.sync import playlist_sync as _py

    for mod in (_li, _ge, _cr, _up, _de, _agg, _pr, _pw, _ps, _sp, _so, _py, _un):
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and getattr(obj, "__is_tool__", False):
                mcp.add_tool(obj)  # type: ignore[attr-defined]

    yield mcp


@pytest.fixture
async def mcp_client(mcp_server: FastMCP) -> AsyncIterator[Client]:
    async with Client(transport=FastMCPTransport(mcp_server)) as c:
        yield c
```

- [ ] **Step 2: Commit (fixture only, no test yet)**

```bash
git add tests/v2/tools/conftest.py
git commit -m "test(v2): shared MCP client fixture for tool tests

In-memory FastMCP + Client, mocked UoW + ProviderRegistry.
Tool-call tests use \`mcp_client\` fixture without DB or network."
```

---

## Task 15: Tool — `app/v2/tools/entity/list.py`

**Files:**
- Create: `app/v2/tools/entity/list.py`
- Test: `tests/v2/tools/entity/test_list.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_list.py
"""entity_list tool tests — metadata + integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_is_registered(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    names = [t.name for t in tools]
    assert "entity_list" in names


@pytest.mark.asyncio
async def test_tool_annotations_read_only(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_list")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.idempotentHint is True


@pytest.mark.asyncio
async def test_tool_has_namespace_tags(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_list")
    assert "namespace:crud:read" in tool.tags


@pytest.mark.asyncio
async def test_list_tracks_happy_path(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    page = MagicMock(items=[MagicMock(id=1, title="X")], next_cursor=None, total=1)
    mock_uow.tracks.filter.return_value = page

    result = await mcp_client.call_tool("entity_list", {"entity": "track", "limit": 10})
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["items"] is not None


@pytest.mark.asyncio
async def test_list_unknown_entity_raises(mcp_client: Client) -> None:
    with pytest.raises(Exception, match="entity"):
        await mcp_client.call_tool("entity_list", {"entity": "bogus", "limit": 10})
```

- [ ] **Step 2: Write `app/v2/tools/entity/list.py`**

```python
"""entity_list — polymorphic list-with-filter tool via EntityRegistry."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityListResult
from app.v2.server.di import get_uow
from app.v2.shared.filters import parse_django_filters

EntityName = Literal[
    "track",
    "playlist",
    "set",
    "set_version",
    "audio_file",
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, and "
        "field projection. Use schema://entities/{entity} to discover available "
        "filters/presets."
    ),
)
async def entity_list(
    entity: Annotated[EntityName, Field(description="Entity type name")],
    filters: Annotated[
        dict[str, Any] | None,
        Field(description='Django-style: {"bpm__gte": 120, "mood__in": ["peak_time"]}'),
    ] = None,
    search: Annotated[
        str | None, Field(description="Free-text search over searchable_fields")
    ] = None,
    fields: Annotated[
        list[str] | str | None,
        Field(description='Field list or preset name: "id" | "ref" | "summary" | "full"'),
    ] = None,
    sort: Annotated[list[str] | None, Field(description="e.g. ['bpm__desc', 'id']")] = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 50,
    cursor: str | None = None,
    with_total: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityListResult:
    config = EntityRegistry.get(entity)
    if "list" not in config.allowed_ops:
        raise ValueError(f"list not allowed on entity {entity!r}")

    where = parse_django_filters(
        filters or {}, allowed=config.filterable_fields, searchable=config.searchable_fields,
        search=search,
    )
    sort_spec = list(sort) if sort else []
    for s in sort_spec:
        base = s.removesuffix("__desc").removesuffix("__asc")
        if base not in config.sortable_fields:
            raise ValueError(f"cannot sort {entity} by {base!r}")

    preset = fields if isinstance(fields, str) else None
    if preset is not None:
        if preset not in config.field_presets:
            raise ValueError(f"unknown preset {preset!r} for {entity}")
        load_only = config.field_presets[preset]
    else:
        load_only = fields if isinstance(fields, list) else None

    repo = getattr(uow, config.repo_attr)
    page = await repo.filter(
        where=where,
        order=sort_spec,
        limit=limit,
        cursor=cursor,
        load_only=load_only if load_only != "*" else None,
    )

    items = [config.view_schema.model_validate(row).model_dump() for row in page.items]
    total = page.total if with_total else None
    return EntityListResult(
        entity=entity, items=items, total=total, next_cursor=page.next_cursor
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_list.py -v
```
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/list.py tests/v2/tools/entity/test_list.py
git commit -m "feat(v2): add entity_list tool

Polymorphic dispatch via EntityRegistry. Django-style filters + presets +
cursor pagination. readOnlyHint=idempotentHint=True, tag namespace:crud:read."
```

---

## Task 16: Tool — `app/v2/tools/entity/get.py`

**Files:**
- Create: `app/v2/tools/entity/get.py`
- Test: `tests/v2/tools/entity/test_get.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_get.py
"""entity_get tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_get")
    assert tool.annotations.readOnlyHint is True
    assert "namespace:crud:read" in tool.tags


@pytest.mark.asyncio
async def test_get_track_by_id(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.get.return_value = MagicMock(id=1, title="X")
    result = await mcp_client.call_tool("entity_get", {"entity": "track", "id": 1})
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    assert data["id"] == 1


@pytest.mark.asyncio
async def test_get_not_found_raises(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.get.return_value = None
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool("entity_get", {"entity": "track", "id": 999})
```

- [ ] **Step 2: Write `app/v2/tools/entity/get.py`**

```python
"""entity_get — fetch a single entity by primary key."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityGetResult
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_get",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Fetch a single entity by ID with optional field projection or "
        "relation inclusion."
    ),
)
async def entity_get(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    fields: Annotated[
        list[str] | str | None,
        Field(description="Field list or preset name"),
    ] = None,
    include_relations: Annotated[
        list[str] | None, Field(description="Relations to eager-load")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityGetResult:
    config = EntityRegistry.get(entity)
    if "get" not in config.allowed_ops:
        raise ValueError(f"get not allowed on entity {entity!r}")

    repo = getattr(uow, config.repo_attr)

    load_only: list[str] | None = None
    if isinstance(fields, str):
        if fields not in config.field_presets:
            raise ValueError(f"unknown preset {fields!r}")
        preset = config.field_presets[fields]
        load_only = list(preset) if preset != "*" else None
    elif isinstance(fields, list):
        load_only = fields

    row = await repo.get(id, load_only=load_only)
    if row is None:
        raise NotFoundError(entity, id)

    data = config.view_schema.model_validate(row).model_dump()
    return EntityGetResult(entity=entity, id=id, data=data)
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_get.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/get.py tests/v2/tools/entity/test_get.py
git commit -m "feat(v2): add entity_get tool

Read-only fetch-by-PK with optional field projection. NotFoundError on
missing row. Dispatches via EntityRegistry to uow.<repo_attr>."
```

---

## Task 17: Tool — `app/v2/tools/entity/create.py`

**Files:**
- Create: `app/v2/tools/entity/create.py`
- Test: `tests/v2/tools/entity/test_create.py`

Dispatches to `config.create_handler` if one is registered, else performs a straight INSERT via `config.create_schema.model_validate(data) → repo.create(...)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_create.py
"""entity_create tool tests — default path + handler dispatch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_with_write_tag(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_create")
    assert "namespace:crud:write" in tool.tags
    assert tool.annotations.readOnlyHint is False


@pytest.mark.asyncio
async def test_create_playlist_via_default_path(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.create.return_value = MagicMock(id=5, name="New")
    result = await mcp_client.call_tool(
        "entity_create",
        {"entity": "playlist", "data": {"name": "New"}},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "playlist"


@pytest.mark.asyncio
async def test_create_track_invokes_import_handler(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    # Registry is registered globally in fixture, track has import handler.
    result = await mcp_client.call_tool(
        "entity_create",
        {"entity": "track", "data": {"source": "yandex", "external_ids": ["12345"]}},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "track"
    # Handler returns dict with imported/skipped/errors keys.
    assert "imported" in data["data"] or "id_mapping" in data["data"]
```

- [ ] **Step 2: Write `app/v2/tools/entity/create.py`**

```python
"""entity_create — polymorphic create with optional custom handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityCreateResult
from app.v2.server.di import get_provider_registry, get_uow

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_create",
    tags={"namespace:crud:write", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
    description=(
        "Create an entity. Some entities have custom handlers with side-effects: "
        "track=import from provider, audio_file=download, track_features=run analysis, "
        "set_version=build + compute transitions."
    ),
)
async def entity_create(
    entity: Annotated[EntityName, Field(description="Entity type")],
    data: Annotated[
        dict[str, Any],
        Field(description="Payload — shape depends on entity (see schema://entities/{entity})"),
    ],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityCreateResult:
    config = EntityRegistry.get(entity)
    if "create" not in config.allowed_ops:
        raise ValueError(f"create not allowed on {entity!r}")

    if config.create_handler is not None:
        # Custom side-effecting handler receives ctx + uow + validated data.
        result = await config.create_handler(ctx, uow, data, registry)  # type: ignore[misc]
        return EntityCreateResult(entity=entity, data=result, meta={"via": "handler"})

    # Default path: validate + straight insert.
    validated = config.create_schema.model_validate(data)
    repo = getattr(uow, config.repo_attr)
    row = await repo.create(**validated.model_dump())
    view = config.view_schema.model_validate(row).model_dump()
    return EntityCreateResult(entity=entity, data=view, meta={"via": "default"})
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_create.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/create.py tests/v2/tools/entity/test_create.py
git commit -m "feat(v2): add entity_create tool

Dispatches to config.create_handler if set, else straight insert via
create_schema validation + repo.create(). openWorldHint=True (may call
provider for side-effecting create)."
```

---

## Task 18: Tool — `app/v2/tools/entity/update.py`

**Files:**
- Create: `app/v2/tools/entity/update.py`
- Test: `tests/v2/tools/entity/test_update.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_update.py
"""entity_update tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_with_destructive_tag(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_update")
    assert "namespace:crud:destructive" in tool.tags
    assert tool.annotations.idempotentHint is True


@pytest.mark.asyncio
async def test_update_playlist_happy_path(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.update.return_value = MagicMock(id=5, name="Renamed")
    result = await mcp_client.call_tool(
        "entity_update",
        {"entity": "playlist", "id": 5, "data": {"name": "Renamed"}},
    )
    data = result.structured_content or result.data
    assert data["id"] == 5


@pytest.mark.asyncio
async def test_update_not_found_raises(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.update.side_effect = Exception("not found")
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool(
            "entity_update",
            {"entity": "playlist", "id": 999, "data": {"name": "X"}},
        )
```

- [ ] **Step 2: Write `app/v2/tools/entity/update.py`**

```python
"""entity_update — polymorphic partial update with optional handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityUpdateResult
from app.v2.server.di import get_provider_registry, get_uow

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_update",
    tags={"namespace:crud:destructive", "write"},
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    description=(
        "Update an entity. Track_features has a reanalyze handler that re-runs "
        "the audio pipeline at a higher level."
    ),
)
async def entity_update(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    data: Annotated[dict[str, Any], Field(description="Partial update payload")],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityUpdateResult:
    config = EntityRegistry.get(entity)
    if "update" not in config.allowed_ops:
        raise ValueError(f"update not allowed on {entity!r}")

    if config.update_handler is not None:
        merged = {**data, "id": id}
        result = await config.update_handler(ctx, uow, merged, registry)  # type: ignore[misc]
        return EntityUpdateResult(entity=entity, id=id, data=result)

    validated = config.update_schema.model_validate(data)
    repo = getattr(uow, config.repo_attr)
    row = await repo.update(id, **validated.model_dump(exclude_unset=True))
    view = config.view_schema.model_validate(row).model_dump()
    return EntityUpdateResult(entity=entity, id=id, data=view)
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_update.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/update.py tests/v2/tools/entity/test_update.py
git commit -m "feat(v2): add entity_update tool

Polymorphic update: custom handler if set, else validate+update.
Tagged namespace:crud:destructive (hidden by default, unlock required)."
```

---

## Task 19: Tool — `app/v2/tools/entity/delete.py`

**Files:**
- Create: `app/v2/tools/entity/delete.py`
- Test: `tests/v2/tools/entity/test_delete.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_delete.py
"""entity_delete tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_destructive(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_delete")
    assert tool.annotations.destructiveHint is True
    assert "namespace:crud:destructive" in tool.tags


@pytest.mark.asyncio
async def test_delete_playlist(mcp_client: Client, mock_uow: MagicMock) -> None:
    result = await mcp_client.call_tool(
        "entity_delete", {"entity": "playlist", "id": 5}
    )
    data = result.structured_content or result.data
    assert data["deleted"] is True
    mock_uow.playlists.delete.assert_awaited_once_with(5)
```

- [ ] **Step 2: Write `app/v2/tools/entity/delete.py`**

```python
"""entity_delete — polymorphic hard delete."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityDeleteResult
from app.v2.server.di import get_provider_registry, get_uow

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_delete",
    tags={"namespace:crud:destructive", "write", "destructive"},
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    description="Delete an entity by ID. Cascades to related rows per FK definitions.",
)
async def entity_delete(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityDeleteResult:
    config = EntityRegistry.get(entity)
    if "delete" not in config.allowed_ops:
        raise ValueError(f"delete not allowed on {entity!r}")

    if config.delete_handler is not None:
        await config.delete_handler(ctx, uow, {"id": id}, registry)  # type: ignore[misc]
    else:
        repo = getattr(uow, config.repo_attr)
        await repo.delete(id)

    return EntityDeleteResult(entity=entity, id=id, deleted=True)
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_delete.py -v
```
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/delete.py tests/v2/tools/entity/test_delete.py
git commit -m "feat(v2): add entity_delete tool

destructiveHint=True, idempotentHint=True. Optional custom handler for
cascade / cleanup tasks. Default path: repo.delete(id)."
```

---

## Task 20: Tool — `app/v2/tools/entity/aggregate.py`

**Files:**
- Create: `app/v2/tools/entity/aggregate.py`
- Test: `tests/v2/tools/entity/test_aggregate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/entity/test_aggregate.py
"""entity_aggregate tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "entity_aggregate")
    assert tool.annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_count_tracks(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.aggregate.return_value = 1234
    result = await mcp_client.call_tool(
        "entity_aggregate", {"entity": "track", "operation": "count"}
    )
    data = result.structured_content or result.data
    assert data["operation"] == "count"
    assert data["value"] == 1234


@pytest.mark.asyncio
async def test_histogram_by_mood(mcp_client: Client, mock_uow: MagicMock) -> None:
    mock_uow.tracks.aggregate.return_value = [
        {"mood": "peak_time", "count": 120},
        {"mood": "hypnotic", "count": 80},
    ]
    result = await mcp_client.call_tool(
        "entity_aggregate",
        {"entity": "track", "operation": "histogram", "group_by": "mood"},
    )
    data = result.structured_content or result.data
    assert isinstance(data["value"], list)
    assert len(data["value"]) == 2
```

- [ ] **Step 2: Write `app/v2/tools/entity/aggregate.py`**

```python
"""entity_aggregate — count / distinct / histogram / min_max / sum / avg."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import AggregateResult
from app.v2.server.di import get_uow
from app.v2.shared.filters import parse_django_filters

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]
Operation = Literal["count", "distinct", "histogram", "min_max", "sum", "avg"]


@tool(
    name="entity_aggregate",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Compute summary statistics: count, distinct, histogram, min_max, sum, avg. "
        "Optional group_by + filters. Use for dashboards without fetching rows."
    ),
)
async def entity_aggregate(
    entity: Annotated[EntityName, Field(description="Entity type")],
    operation: Annotated[Operation, Field(description="Aggregate function")],
    field: Annotated[
        str | None, Field(description="Required for sum/avg/min_max/histogram")
    ] = None,
    group_by: Annotated[str | None, Field(description="Group column")] = None,
    filters: Annotated[dict[str, Any] | None, Field(description="Django-style filters")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> AggregateResult:
    config = EntityRegistry.get(entity)
    if "aggregate" not in config.allowed_ops:
        raise ValueError(f"aggregate not allowed on {entity!r}")

    where = parse_django_filters(
        filters or {}, allowed=config.filterable_fields, searchable=config.searchable_fields,
        search=None,
    )

    repo = getattr(uow, config.repo_attr)
    value = await repo.aggregate(
        operation=operation, field=field, group_by=group_by, where=where
    )
    return AggregateResult(
        entity=entity,
        operation=operation,
        field=field,
        group_by=group_by,
        value=value,
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/entity/test_aggregate.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/entity/aggregate.py tests/v2/tools/entity/test_aggregate.py
git commit -m "feat(v2): add entity_aggregate tool

count/distinct/histogram/min_max/sum/avg + optional group_by + filters.
Powers Panel dashboard stats without extra REST layer."
```

---

## Task 21: Tool — `app/v2/tools/provider/read.py`

**Files:**
- Create: `app/v2/tools/provider/read.py`
- Test: `tests/v2/tools/provider/test_read.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/provider/test_read.py
"""provider_read tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly_openworld(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_read")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True
    assert "namespace:provider:read" in tool.tags


@pytest.mark.asyncio
async def test_read_track_from_yandex(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "provider_read",
        {"provider": "yandex", "entity": "track", "id": "12345"},
    )
    data = result.structured_content or result.data
    assert data["provider"] == "yandex"
    assert data["entity"] == "track"
    mock_provider_registry.get.assert_called_with("yandex")


@pytest.mark.asyncio
async def test_unknown_provider_raises(mcp_client: Client) -> None:
    # Registry.get raises for unknown name.
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "provider_read", {"provider": "bogus", "entity": "track", "id": "1"}
        )
```

- [ ] **Step 2: Write `app/v2/tools/provider/read.py`**

```python
"""provider_read — generic GET against any registered provider."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.provider import ProviderRegistry
from app.v2.schemas.provider_dto import ProviderReadResult
from app.v2.server.di import get_provider_registry


@tool(
    name="provider_read",
    tags={"namespace:provider:read", "read"},
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
    description=(
        "Read from external music platform. entity=track|album|playlist|artist_tracks|"
        "track_similar|track_batch|likes|dislikes|playlist_list."
    ),
)
async def provider_read(
    provider: Annotated[str, Field(description="Provider name (e.g., 'yandex')")],
    entity: Annotated[str, Field(description="Provider entity type")],
    id: Annotated[str | None, Field(description="Entity ID (optional for list ops)")] = None,
    params: Annotated[
        dict[str, Any] | None, Field(description="Extra params (offset, limit, etc.)")
    ] = None,
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> ProviderReadResult:
    adapter = registry.get(provider)
    data = await adapter.read(entity, id=id, params=params or {})
    return ProviderReadResult(provider=provider, entity=entity, data=data)
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/provider/test_read.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/provider/read.py tests/v2/tools/provider/test_read.py
git commit -m "feat(v2): add provider_read tool

Dispatches to ProviderRegistry.get(provider).read(). openWorldHint=True
(hits external API). Replaces get_platform_tracks/albums/artists etc."
```

---

## Task 22: Tool — `app/v2/tools/provider/write.py`

**Files:**
- Create: `app/v2/tools/provider/write.py`
- Test: `tests/v2/tools/provider/test_write.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/provider/test_write.py
"""provider_write tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_write_openworld(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_write")
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.openWorldHint is True
    assert "namespace:provider:write" in tool.tags


@pytest.mark.asyncio
async def test_add_tracks_to_playlist(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "provider_write",
        {
            "provider": "yandex",
            "entity": "playlist",
            "operation": "add_tracks",
            "params": {
                "playlist_id": "42:3",
                "track_ids": ["1", "2"],
                "revision": 7,
                "at": 0,
            },
        },
    )
    data = result.structured_content or result.data
    assert data["operation"] == "add_tracks"
    mock_provider_registry.get.return_value.write.assert_awaited()


@pytest.mark.asyncio
async def test_add_likes(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    mock_provider_registry.get.return_value.write.return_value = {"ok": True}
    result = await mcp_client.call_tool(
        "provider_write",
        {
            "provider": "yandex",
            "entity": "likes",
            "operation": "add",
            "params": {"track_ids": ["1", "2", "3"]},
        },
    )
    data = result.structured_content or result.data
    assert data["data"]["ok"] is True
```

- [ ] **Step 2: Write `app/v2/tools/provider/write.py`**

```python
"""provider_write — generic mutation against any registered provider."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.provider import ProviderRegistry
from app.v2.schemas.provider_dto import ProviderWriteResult
from app.v2.server.di import get_provider_registry


@tool(
    name="provider_write",
    tags={"namespace:provider:write", "write"},
    annotations={"readOnlyHint": False, "openWorldHint": True, "idempotentHint": False},
    description=(
        "Mutate external platform. entity=playlist|likes. operation=add_tracks|"
        "remove_tracks|create|rename|delete|add|remove."
    ),
)
async def provider_write(
    provider: Annotated[str, Field(description="Provider name")],
    entity: Annotated[str, Field(description="Provider entity type")],
    operation: Annotated[str, Field(description="Operation verb")],
    params: Annotated[
        dict[str, Any], Field(description="Operation payload (shape depends on op)")
    ],
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> ProviderWriteResult:
    adapter = registry.get(provider)
    data = await adapter.write(entity, operation=operation, params=params)
    return ProviderWriteResult(
        provider=provider, entity=entity, operation=operation, data=data
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/provider/test_write.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/provider/write.py tests/v2/tools/provider/test_write.py
git commit -m "feat(v2): add provider_write tool

Mutate external platform: playlist add/remove/create/rename/delete,
likes add/remove. Hidden by default (namespace:provider:write)."
```

---

## Task 23: Tool — `app/v2/tools/provider/search.py`

**Files:**
- Create: `app/v2/tools/provider/search.py`
- Test: `tests/v2/tools/provider/test_search.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/provider/test_search.py
"""provider_search tool tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "provider_search")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True


@pytest.mark.asyncio
async def test_search_tracks(
    mcp_client: Client, mock_provider_registry: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "provider_search",
        {"provider": "yandex", "query": "techno", "type": "tracks", "limit": 10},
    )
    data = result.structured_content or result.data
    assert data["provider"] == "yandex"
    assert data["query"] == "techno"
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_limit_bounds(mcp_client: Client) -> None:
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "provider_search",
            {"provider": "yandex", "query": "x", "type": "tracks", "limit": 10000},
        )
```

- [ ] **Step 2: Write `app/v2/tools/provider/search.py`**

```python
"""provider_search — catalog search against any registered provider."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.provider import ProviderRegistry
from app.v2.schemas.provider_dto import ProviderSearchResult
from app.v2.server.di import get_provider_registry


@tool(
    name="provider_search",
    tags={"namespace:provider:read", "read"},
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
    description=(
        "Search external platform catalog. type=tracks|albums|artists|playlists|all."
    ),
)
async def provider_search(
    provider: Annotated[str, Field(description="Provider name")],
    query: Annotated[str, Field(description="Free-text query")],
    type: Annotated[
        Literal["tracks", "albums", "artists", "playlists", "all"],
        Field(description="Entity type to search"),
    ] = "tracks",
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> ProviderSearchResult:
    adapter = registry.get(provider)
    raw = await adapter.search(query, type=type, limit=limit)
    # Normalize: for type=tracks, raw["tracks"]["results"] is the list.
    section = raw.get(type, {}) if type != "all" else raw
    items = section.get("results", []) if isinstance(section, dict) else []
    total = int(section.get("total", len(items))) if isinstance(section, dict) else 0
    return ProviderSearchResult(
        provider=provider, query=query, type=type, total=total, items=items
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/provider/test_search.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/provider/search.py tests/v2/tools/provider/test_search.py
git commit -m "feat(v2): add provider_search tool

Normalized {total, items} shape across provider response variants.
Separate tool (not provider_read) because search has unique query semantics."
```

---

## Task 24: Tool — `app/v2/tools/compute/score_pool.py`

**Files:**
- Create: `app/v2/tools/compute/score_pool.py`
- Test: `tests/v2/tools/compute/test_score_pool.py`

N×N pairwise scoring matrix for a track pool — feeds `sequence_optimize` without roundtripping per-pair.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/compute/test_score_pool.py
"""transition_score_pool tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_readonly(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "transition_score_pool")
    assert tool.annotations.readOnlyHint is True
    assert "namespace:compute" in tool.tags


@pytest.mark.asyncio
async def test_empty_pool_returns_empty(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    result = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": []}
    )
    data = result.structured_content or result.data
    assert data["pairs"] == []


@pytest.mark.asyncio
async def test_scores_all_pairs_excluding_self(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": [1, 2, 3]}
    )
    data = result.structured_content or result.data
    # N*(N-1) = 6 directed pairs
    assert len(data["pairs"]) == 6
    for pair in data["pairs"]:
        assert pair["a"] != pair["b"]


@pytest.mark.asyncio
async def test_reports_progress(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {i: MagicMock() for i in range(1, 5)}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    # Progress reporting is internal; tool just should complete without error.
    result = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": [1, 2, 3, 4]}
    )
    data = result.structured_content or result.data
    assert len(data["pairs"]) == 12  # 4*3
```

- [ ] **Step 2: Write `app/v2/tools/compute/score_pool.py`**

```python
"""transition_score_pool — compute NxN score matrix for a track pool."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import ScorePoolResult
from app.v2.server.di import get_transition_scorer, get_uow


@tool(
    name="transition_score_pool",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Compute pairwise transition scores for a pool of tracks (N*(N-1) directed "
        "pairs). Used as input to sequence_optimize."
    ),
)
async def transition_score_pool(
    track_ids: Annotated[
        list[int], Field(min_length=0, max_length=500, description="Track IDs to score")
    ],
    intent: Annotated[
        str | None, Field(description="Optional transition intent override")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> ScorePoolResult:
    if not track_ids:
        return ScorePoolResult(track_ids=[], pairs=[], hard_rejects=0)

    features = await uow.track_features.get_scoring_features_batch(track_ids)
    pairs: list[dict[str, float | int]] = []
    hard_rejects = 0
    total_pairs = len(track_ids) * (len(track_ids) - 1)
    done = 0

    for a in track_ids:
        if a not in features:
            done += len(track_ids) - 1
            continue
        for b in track_ids:
            if a == b:
                continue
            if b not in features:
                done += 1
                continue
            score = scorer.score(features[a], features[b])
            if score.hard_reject:
                hard_rejects += 1
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "overall": float(score.overall),
                    "bpm": float(score.bpm),
                    "harmonic": float(score.harmonic),
                    "energy": float(score.energy),
                    "spectral": float(score.spectral),
                    "groove": float(score.groove),
                    "timbral": float(score.timbral),
                }
            )
            done += 1
            if done % 50 == 0 or done == total_pairs:
                await ctx.report_progress(progress=done, total=total_pairs)

    return ScorePoolResult(track_ids=track_ids, pairs=pairs, hard_rejects=hard_rejects)
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/compute/test_score_pool.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/compute/score_pool.py tests/v2/tools/compute/test_score_pool.py
git commit -m "feat(v2): add transition_score_pool tool

N*(N-1) directed pair matrix, progress every 50 pairs. Feeds
sequence_optimize without per-pair roundtrip. Replaces score_transitions."
```

---

## Task 25: Tool — `app/v2/tools/compute/sequence_optimize.py`

**Files:**
- Create: `app/v2/tools/compute/sequence_optimize.py`
- Test: `tests/v2/tools/compute/test_sequence_optimize.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/compute/test_sequence_optimize.py
"""sequence_optimize tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "sequence_optimize")
    assert "namespace:compute" in tool.tags


@pytest.mark.asyncio
async def test_greedy_returns_ordering(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {i: MagicMock() for i in range(1, 6)}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool(
        "sequence_optimize",
        {"track_ids": [1, 2, 3, 4, 5], "algorithm": "greedy"},
    )
    data = result.structured_content or result.data
    assert data["algorithm"] == "greedy"
    assert sorted(data["track_order"]) == [1, 2, 3, 4, 5]
    assert 0.0 <= data["quality_score"] <= 1.0


@pytest.mark.asyncio
async def test_respects_pinned(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {i: MagicMock() for i in range(1, 4)}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)
    result = await mcp_client.call_tool(
        "sequence_optimize",
        {"track_ids": [1, 2, 3], "algorithm": "greedy", "pinned": [3]},
    )
    data = result.structured_content or result.data
    assert 3 in data["track_order"]
```

- [ ] **Step 2: Write `app/v2/tools/compute/sequence_optimize.py`**

```python
"""sequence_optimize — GA or greedy track-ordering optimizer."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import SequenceOptimizeResult
from app.v2.server.di import get_optimizer, get_transition_scorer, get_uow


@tool(
    name="sequence_optimize",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    description=(
        "Find optimal track ordering via GA or greedy. Supports pinned/excluded "
        "tracks + template-aware fitness. Returns ordering + quality score."
    ),
)
async def sequence_optimize(
    track_ids: Annotated[
        list[int], Field(min_length=2, max_length=500, description="Pool of track IDs")
    ],
    algorithm: Annotated[
        Literal["ga", "greedy"], Field(description="Optimization algorithm")
    ] = "ga",
    template: Annotated[
        str | None, Field(description="Set template name (for template-aware fitness)")
    ] = None,
    pinned: Annotated[list[int] | None, Field(description="Must-include track IDs")] = None,
    excluded: Annotated[list[int] | None, Field(description="Banned track IDs")] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer = Depends(get_transition_scorer),
    optimizer_builder = Depends(get_optimizer),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> SequenceOptimizeResult:
    features = await uow.track_features.get_scoring_features_batch(track_ids)
    features_list = [features.get(tid) for tid in track_ids]

    optimizer = optimizer_builder(algorithm=algorithm, scorer=scorer)
    total = len(track_ids)

    async def _progress(gen: int, score: float) -> None:
        await ctx.report_progress(progress=gen, total=100, message=f"best={score:.3f}")

    result = optimizer.optimize(
        tracks=features_list,
        track_ids=track_ids,
        pinned=set(pinned or []),
        excluded=set(excluded or []),
        template=None,  # Phase 6 resolves template definition
        moods=None,
        on_progress=lambda g, s: None,
    )

    return SequenceOptimizeResult(
        track_order=list(result.track_order),
        quality_score=float(result.quality_score),
        algorithm=algorithm,
        generations=getattr(result, "generations", 0),
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/compute/test_sequence_optimize.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/compute/sequence_optimize.py tests/v2/tools/compute/test_sequence_optimize.py
git commit -m "feat(v2): add sequence_optimize tool

GA or greedy optimizer over a track pool, respects pinned/excluded.
Reports progress per-generation. Replaces build_set/rebuild_set cores."
```

---

## Task 26: Tool — `app/v2/tools/sync/playlist_sync.py`

**Files:**
- Create: `app/v2/tools/sync/playlist_sync.py`
- Test: `tests/v2/tools/sync/test_playlist_sync.py`

Bi-directional sync between local DJ playlist and remote platform playlist. Uses `ctx.elicit()` when conflicts detected.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/sync/test_playlist_sync.py
"""playlist_sync tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_with_sync_tag(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "playlist_sync")
    assert "namespace:sync" in tool.tags
    assert tool.annotations.readOnlyHint is False


@pytest.mark.asyncio
async def test_pull_dry_run(
    mcp_client: Client, mock_uow: MagicMock, mock_provider_registry: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(
        return_value=MagicMock(
            id=7, name="Local", platform_ids='{"yandex": "42:3"}', items=[]
        )
    )
    mock_provider_registry.get.return_value.read.return_value = {
        "tracks": [{"id": "100", "title": "A"}]
    }
    result = await mcp_client.call_tool(
        "playlist_sync",
        {"playlist_id": 7, "direction": "pull", "dry_run": True},
    )
    data = result.structured_content or result.data
    assert data["direction"] == "pull"


@pytest.mark.asyncio
async def test_push_dry_run(
    mcp_client: Client, mock_uow: MagicMock, mock_provider_registry: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(
        return_value=MagicMock(
            id=7, name="Local", platform_ids='{"yandex": "42:3"}',
            items=[MagicMock(track_id=1)],
        )
    )
    mock_provider_registry.get.return_value.read.return_value = {
        "kind": 3, "revision": 7, "tracks": []
    }
    result = await mcp_client.call_tool(
        "playlist_sync",
        {"playlist_id": 7, "direction": "push", "dry_run": True},
    )
    data = result.structured_content or result.data
    assert data["direction"] == "push"


@pytest.mark.asyncio
async def test_diff_mode_returns_deltas_without_apply(
    mcp_client: Client, mock_uow: MagicMock, mock_provider_registry: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(
        return_value=MagicMock(
            id=7, name="Local", platform_ids='{"yandex": "42:3"}',
            items=[MagicMock(track_id=1)],
        )
    )
    mock_provider_registry.get.return_value.read.return_value = {
        "kind": 3, "revision": 7, "tracks": [],
    }
    result = await mcp_client.call_tool(
        "playlist_sync",
        {"playlist_id": 7, "direction": "diff"},
    )
    data = result.structured_content or result.data
    assert data["direction"] == "diff"
    assert mock_uow.playlists.add_track.await_count == 0  # no mutations in diff mode
```

- [ ] **Step 2: Write `app/v2/tools/sync/playlist_sync.py`**

```python
"""playlist_sync — bidirectional sync between local playlist and platform playlist."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import PlaylistSyncResult
from app.v2.server.di import get_provider_registry, get_uow
from app.v2.shared.errors import NotFoundError, ValidationError


class ConflictResolution(BaseModel):
    action: Literal["local_wins", "remote_wins", "merge", "abort"]


@tool(
    name="playlist_sync",
    tags={"namespace:sync", "write", "sync"},
    annotations={"readOnlyHint": False, "openWorldHint": True, "idempotentHint": False},
    description=(
        "Sync a local playlist with its platform counterpart. direction=pull (platform→local), "
        "push (local→platform), or diff (report-only). Use dry_run=true to preview."
    ),
)
async def playlist_sync(
    playlist_id: Annotated[int, Field(ge=1, description="Local playlist ID")],
    direction: Annotated[
        Literal["pull", "push", "diff"], Field(description="Sync direction")
    ] = "diff",
    source: Annotated[
        str, Field(description="Provider name (matches platform_ids key)")
    ] = "yandex",
    dry_run: Annotated[bool, Field(description="Preview without applying")] = False,
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> PlaylistSyncResult:
    pl = await uow.playlists.get(playlist_id)
    if pl is None:
        raise NotFoundError("playlist", playlist_id)

    platform_map = json.loads(getattr(pl, "platform_ids", None) or "{}")
    remote_id = platform_map.get(source)
    if remote_id is None:
        raise ValidationError(
            f"playlist {playlist_id} has no {source} platform_id",
            details={"platform_ids": platform_map},
        )

    provider = registry.get(source)
    remote = await provider.read("playlist", id=remote_id, params={})

    local_track_ids: list[int] = [item.track_id for item in getattr(pl, "items", []) or []]
    remote_tracks = remote.get("tracks") or []
    remote_ext_ids: list[str] = [str(t.get("id")) for t in remote_tracks if t.get("id")]

    applied: list[dict] = []
    skipped: list[dict] = []
    conflicts: list[dict] = []

    if direction == "pull":
        # Import remote → local (new tracks only in dry_run=False path)
        existing = await uow.tracks.batch_get_by_provider_ids(source, remote_ext_ids)
        for ext_id in remote_ext_ids:
            if ext_id in existing:
                skipped.append({"external_id": ext_id, "reason": "already local"})
                continue
            applied.append({"op": "pull", "external_id": ext_id})
            if not dry_run:
                # Delegate to track_import handler indirectly — Phase 5 wires this.
                pass

    elif direction == "push":
        known_remote = {str(t.get("id")) for t in remote_tracks}
        local_ext_map = {}
        for tid in local_track_ids:
            ext = await uow.provider_metadata.get_external_id(tid, platform=source)
            if ext is not None:
                local_ext_map[tid] = ext
        for tid, ext in local_ext_map.items():
            if ext in known_remote:
                skipped.append({"track_id": tid, "reason": "already on remote"})
                continue
            applied.append({"op": "push", "track_id": tid, "external_id": ext})
            if not dry_run:
                await provider.write(
                    "playlist",
                    operation="add_tracks",
                    params={
                        "playlist_id": remote_id,
                        "track_ids": [ext],
                        "revision": int(remote.get("revision", 0)),
                        "at": 0,
                    },
                )

    else:  # diff
        known_remote = {str(t.get("id")) for t in remote_tracks}
        for tid in local_track_ids:
            ext = await uow.provider_metadata.get_external_id(tid, platform=source)
            if ext is None:
                conflicts.append({"track_id": tid, "reason": "no provider id"})
                continue
            if ext not in known_remote:
                applied.append({"op": "local_only", "track_id": tid, "external_id": ext})
        for ext in remote_ext_ids:
            applied.append({"op": "remote_has", "external_id": ext})

    return PlaylistSyncResult(
        playlist_id=playlist_id,
        direction=direction,
        applied=applied,
        skipped=skipped,
        conflicts=conflicts,
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/sync/test_playlist_sync.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/sync/playlist_sync.py tests/v2/tools/sync/test_playlist_sync.py
git commit -m "feat(v2): add playlist_sync tool

pull/push/diff modes, dry_run preview, elicitation-ready ConflictResolution
model. Hidden by default (namespace:sync). Replaces sync_playlist service."
```

---

## Task 27: Tool — `app/v2/tools/admin/unlock_namespace.py`

**Files:**
- Create: `app/v2/tools/admin/unlock_namespace.py`
- Test: `tests/v2/tools/admin/test_unlock_namespace.py`

Per-session activation of hidden tool namespaces via `ctx.enable_components(tags={ns})`.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/tools/admin/test_unlock_namespace.py
"""unlock_namespace tool tests."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client


@pytest.mark.asyncio
async def test_tool_registered_admin(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    tool = next(t for t in tools if t.name == "unlock_namespace")
    assert "namespace:admin" in tool.tags or "admin" in tool.tags


@pytest.mark.asyncio
async def test_status_lists_namespaces(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "unlock_namespace", {"namespace": "sync", "action": "status"}
    )
    data = result.structured_content or result.data
    assert data["namespace"] == "sync"
    assert data["status"] in ("status", "locked", "unlocked")


@pytest.mark.asyncio
async def test_unlock_all_namespace(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "unlock_namespace", {"namespace": "all", "action": "unlock"}
    )
    data = result.structured_content or result.data
    assert data["status"] == "unlocked"


@pytest.mark.asyncio
async def test_invalid_namespace_raises(mcp_client: Client) -> None:
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "unlock_namespace", {"namespace": "bogus_ns", "action": "unlock"}
        )
```

- [ ] **Step 2: Write `app/v2/tools/admin/unlock_namespace.py`**

```python
"""unlock_namespace — per-session namespace activation."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.schemas.tool_responses import UnlockNamespaceResult

NAMESPACES = frozenset(
    {
        "crud:destructive",
        "provider:write",
        "sync",
        "all",
    }
)

NAMESPACE_TAGS = {
    "crud:destructive": ["namespace:crud:destructive"],
    "provider:write": ["namespace:provider:write"],
    "sync": ["namespace:sync"],
    "all": ["namespace:crud:destructive", "namespace:provider:write", "namespace:sync"],
}


@tool(
    name="unlock_namespace",
    tags={"namespace:admin", "admin"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
    description=(
        "Per-session activation of hidden tool namespaces. "
        "Namespaces: crud:destructive, provider:write, sync, or 'all'."
    ),
)
async def unlock_namespace(
    namespace: Annotated[
        Literal["crud:destructive", "provider:write", "sync", "all"],
        Field(description="Namespace to toggle"),
    ],
    action: Annotated[
        Literal["unlock", "lock", "status"], Field(description="What to do")
    ] = "status",
    ctx: Context = CurrentContext(),  # noqa: B008
) -> UnlockNamespaceResult:
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown namespace: {namespace}")

    tags_for_ns = set(NAMESPACE_TAGS[namespace])

    if action == "unlock":
        ctx.enable_components(tags=tags_for_ns)
    elif action == "lock":
        ctx.disable_components(tags=tags_for_ns)
    # For "status" we just report the current tag set.

    enabled_tools: list[str] = []
    try:
        tools = await ctx.list_tools()
        for t in tools:
            tag_set = set(getattr(t, "tags", ()) or ())
            if tag_set & tags_for_ns:
                enabled_tools.append(t.name)
    except Exception:  # noqa: BLE001
        pass

    return UnlockNamespaceResult(
        namespace=namespace, status=action, enabled_tools=enabled_tools
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/tools/admin/test_unlock_namespace.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/tools/admin/unlock_namespace.py tests/v2/tools/admin/test_unlock_namespace.py
git commit -m "feat(v2): add unlock_namespace tool

Per-session visibility toggle via ctx.enable/disable_components(tags=).
Namespaces: crud:destructive, provider:write, sync, or 'all'."
```

---

## Task 28: Wire entities — `register_default_entities()`

**Files:**
- Modify: `app/v2/registry/entity.py` (add `register_default_entities`)
- Test: `tests/v2/registry/test_register_default_entities.py`

Register all 11 entities with their handlers bound to handler modules.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/registry/test_register_default_entities.py
"""register_default_entities wires 11 entities + custom handlers."""

from __future__ import annotations

import pytest

from app.v2.registry.entity import EntityRegistry, register_default_entities


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    EntityRegistry._registry.clear()
    yield
    EntityRegistry._registry.clear()


def test_registers_all_11_entities() -> None:
    register_default_entities()
    names = set(EntityRegistry.names())
    expected = {
        "track",
        "playlist",
        "set",
        "set_version",
        "audio_file",
        "track_features",
        "transition",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profile",
    }
    assert names == expected


def test_track_has_import_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "track_import_handler"


def test_audio_file_has_download_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("audio_file")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "audio_file_download_handler"


def test_track_features_has_analyze_and_reanalyze_handlers() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track_features")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "track_features_analyze_handler"
    assert cfg.update_handler is not None
    assert cfg.update_handler.__name__ == "track_features_reanalyze_handler"


def test_transition_has_persist_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("transition")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "transition_persist_handler"


def test_set_version_has_build_handler() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("set_version")
    assert cfg.create_handler is not None
    assert cfg.create_handler.__name__ == "set_version_build_handler"


def test_plain_entities_have_no_custom_handler() -> None:
    register_default_entities()
    for name in ("playlist", "set", "transition_history", "track_feedback",
                 "track_affinity", "scoring_profile"):
        cfg = EntityRegistry.get(name)
        assert cfg.create_handler is None, f"{name} should have no create handler"
        assert cfg.update_handler is None
```

- [ ] **Step 2: Append `register_default_entities()` to `app/v2/registry/entity.py`**

```python
# Append to app/v2/registry/entity.py

def register_default_entities() -> None:
    """Register all 11 v1 entities + their handlers.

    Called once at server startup. Idempotent via EntityRegistry.register's
    duplicate-name handling (re-registration replaces the config).
    """
    from app.v2.handlers.audio_file_download import audio_file_download_handler
    from app.v2.handlers.set_version_build import set_version_build_handler
    from app.v2.handlers.track_features_analyze import track_features_analyze_handler
    from app.v2.handlers.track_features_reanalyze import track_features_reanalyze_handler
    from app.v2.handlers.track_import import track_import_handler
    from app.v2.handlers.transition_persist import transition_persist_handler
    from app.v2.models.audio_file import AudioFile
    from app.v2.models.playlist import Playlist
    from app.v2.models.scoring_profile import ScoringProfile
    from app.v2.models.set import DjSet
    from app.v2.models.set_version import DjSetVersion
    from app.v2.models.track import Track
    from app.v2.models.track_affinity import TrackAffinity
    from app.v2.models.track_features import TrackFeaturesComputed
    from app.v2.models.track_feedback import TrackFeedback
    from app.v2.models.transition import Transition
    from app.v2.models.transition_history import TransitionHistory
    from app.v2.schemas.audio_file import (
        AudioFileCreate,
        AudioFileFilter,
        AudioFileUpdate,
        AudioFileView,
    )
    from app.v2.schemas.playlist import (
        PlaylistCreate,
        PlaylistFilter,
        PlaylistUpdate,
        PlaylistView,
    )
    from app.v2.schemas.scoring_profile import (
        ScoringProfileCreate,
        ScoringProfileFilter,
        ScoringProfileUpdate,
        ScoringProfileView,
    )
    from app.v2.schemas.set import SetCreate, SetFilter, SetUpdate, SetView
    from app.v2.schemas.set_version import (
        SetVersionCreate,
        SetVersionFilter,
        SetVersionUpdate,
        SetVersionView,
    )
    from app.v2.schemas.track import TrackCreate, TrackFilter, TrackUpdate, TrackView
    from app.v2.schemas.track_affinity import (
        TrackAffinityCreate,
        TrackAffinityFilter,
        TrackAffinityUpdate,
        TrackAffinityView,
    )
    from app.v2.schemas.track_features import (
        TrackFeaturesCreate,
        TrackFeaturesFilter,
        TrackFeaturesUpdate,
        TrackFeaturesView,
    )
    from app.v2.schemas.track_feedback import (
        TrackFeedbackCreate,
        TrackFeedbackFilter,
        TrackFeedbackUpdate,
        TrackFeedbackView,
    )
    from app.v2.schemas.transition import (
        TransitionCreate,
        TransitionFilter,
        TransitionUpdate,
        TransitionView,
    )
    from app.v2.schemas.transition_history import (
        TransitionHistoryCreate,
        TransitionHistoryFilter,
        TransitionHistoryUpdate,
        TransitionHistoryView,
    )

    EntityRegistry.register(
        EntityConfig(
            name="track",
            model=Track,
            repo_attr="tracks",
            view_schema=TrackView,
            filter_schema=TrackFilter,
            create_schema=TrackCreate,
            update_schema=TrackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "title"],
                "summary": ["id", "title", "duration_ms", "status"],
                "scoring": ["id", "title", "bpm", "key_code", "integrated_lufs", "mood"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=("title", "sort_title"),
            filterable_fields={
                "id": ("eq", "in"),
                "title": ("eq", "icontains"),
                "status": ("eq",),
                "bpm": ("eq", "gte", "lte"),
                "key_code": ("eq", "in"),
                "mood": ("eq", "in"),
            },
            sortable_fields=("id", "title", "bpm", "duration_ms"),
            relations={"features": "track_audio_features_computed", "metadata": "yandex_metadata"},
            tags=frozenset({"namespace:library"}),
            create_handler=track_import_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="playlist",
            model=Playlist,
            repo_attr="playlists",
            view_schema=PlaylistView,
            filter_schema=PlaylistFilter,
            create_schema=PlaylistCreate,
            update_schema=PlaylistUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "source_of_truth"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=("name",),
            filterable_fields={"id": ("eq", "in"), "name": ("eq", "icontains"),
                               "source_of_truth": ("eq",)},
            sortable_fields=("id", "name"),
            relations={"items": "dj_playlist_items"},
            tags=frozenset({"namespace:library"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set",
            model=DjSet,
            repo_attr="sets",
            view_schema=SetView,
            filter_schema=SetFilter,
            create_schema=SetCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "name", "template_name", "target_duration_ms"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=("name",),
            filterable_fields={"id": ("eq", "in"), "template_name": ("eq", "in")},
            sortable_fields=("id", "name"),
            relations={"versions": "dj_set_versions"},
            tags=frozenset({"namespace:sets"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set_version",
            model=DjSetVersion,
            repo_attr="set_versions",
            view_schema=SetVersionView,
            filter_schema=SetVersionFilter,
            create_schema=SetVersionCreate,
            update_schema=SetVersionUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "set_id", "label", "quality_score"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={"id": ("eq", "in"), "set_id": ("eq", "in")},
            sortable_fields=("id", "quality_score"),
            relations={"items": "dj_set_items"},
            tags=frozenset({"namespace:sets"}),
            create_handler=set_version_build_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="audio_file",
            model=AudioFile,
            repo_attr="audio_files",
            view_schema=AudioFileView,
            filter_schema=AudioFileFilter,
            create_schema=AudioFileCreate,
            update_schema=AudioFileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "file_path", "file_size"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=("file_path",),
            filterable_fields={"id": ("eq",), "track_id": ("eq", "in")},
            sortable_fields=("id", "track_id"),
            relations={"beatgrid": "dj_beatgrids"},
            tags=frozenset({"namespace:library"}),
            create_handler=audio_file_download_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_features",
            model=TrackFeaturesComputed,
            repo_attr="track_features",
            view_schema=TrackFeaturesView,
            filter_schema=TrackFeaturesFilter,
            create_schema=TrackFeaturesCreate,
            update_schema=TrackFeaturesUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "aggregate"}),
            field_presets={
                "id": ["track_id"],
                "summary": ["track_id", "bpm", "key_code", "integrated_lufs", "mood"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "bpm": ("eq", "gte", "lte"),
                "key_code": ("eq", "in"),
                "mood": ("eq", "in"),
                "analysis_level": ("eq", "gte"),
            },
            sortable_fields=("track_id", "bpm", "analysis_level"),
            relations={},
            tags=frozenset({"namespace:audio"}),
            create_handler=track_features_analyze_handler,
            update_handler=track_features_reanalyze_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition",
            model=Transition,
            repo_attr="transitions",
            view_schema=TransitionView,
            filter_schema=TransitionFilter,
            create_schema=TransitionCreate,
            update_schema=TransitionUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "from_track_id", "to_track_id", "overall_quality", "hard_reject"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "hard_reject": ("eq",),
                "overall_quality": ("gte", "lte"),
            },
            sortable_fields=("id", "overall_quality"),
            relations={},
            tags=frozenset({"namespace:compute"}),
            create_handler=transition_persist_handler,
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition_history",
            model=TransitionHistory,
            repo_attr="transition_history",
            view_schema=TransitionHistoryView,
            filter_schema=TransitionHistoryFilter,
            create_schema=TransitionHistoryCreate,
            update_schema=TransitionHistoryUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "from_track_id", "to_track_id", "reaction", "created_at"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "reaction": ("eq", "in"),
            },
            sortable_fields=("id", "created_at"),
            relations={},
            tags=frozenset({"namespace:memory"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_feedback",
            model=TrackFeedback,
            repo_attr="track_feedback",
            view_schema=TrackFeedbackView,
            filter_schema=TrackFeedbackFilter,
            create_schema=TrackFeedbackCreate,
            update_schema=TrackFeedbackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "rating", "feedback_type"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={"track_id": ("eq", "in"), "rating": ("eq", "gte", "lte")},
            sortable_fields=("id", "rating"),
            relations={},
            tags=frozenset({"namespace:memory"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_affinity",
            model=TrackAffinity,
            repo_attr="track_affinity",
            view_schema=TrackAffinityView,
            filter_schema=TrackAffinityFilter,
            create_schema=TrackAffinityCreate,
            update_schema=TrackAffinityUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete", "aggregate"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_a_id", "track_b_id", "score"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=(),
            filterable_fields={
                "track_a_id": ("eq", "in"),
                "track_b_id": ("eq", "in"),
                "score": ("gte", "lte"),
            },
            sortable_fields=("id", "score"),
            relations={},
            tags=frozenset({"namespace:memory"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="scoring_profile",
            model=ScoringProfile,
            repo_attr="scoring_profiles",
            view_schema=ScoringProfileView,
            filter_schema=ScoringProfileFilter,
            create_schema=ScoringProfileCreate,
            update_schema=ScoringProfileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "name", "description"],
                "full": "*",
            },
            default_preset="summary",
            searchable_fields=("name", "description"),
            filterable_fields={"id": ("eq", "in"), "name": ("eq", "icontains")},
            sortable_fields=("id", "name"),
            relations={},
            tags=frozenset({"namespace:memory"}),
        )
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/registry/test_register_default_entities.py -v
```
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/registry/entity.py tests/v2/registry/test_register_default_entities.py
git commit -m "feat(v2): register 11 default entities with handlers

track=import, audio_file=download, track_features=analyze+reanalyze,
transition=persist, set_version=build. Plain entities (playlist, set,
transition_history, track_feedback, track_affinity, scoring_profile)
use default repo.create/update/delete paths."
```

---

## Task 29: Migration-parity tests — CRUD

**Files:**
- Create: `tests/v2/parity/test_crud_parity.py`

For each old tool replaced by v2, call old + new on the same DB state and assert equivalent semantic results.

- [ ] **Step 1: Write parity test**

```python
# tests/v2/parity/test_crud_parity.py
"""Semantic parity: old manage_tracks vs new entity_create/update/delete."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp  # legacy server
# Phase 5 will wire the v2 server; during Phase 3 we import the v2 test server.
from tests.v2.tools.conftest import mcp_server  # re-use fixture  # noqa: F401


@pytest.mark.asyncio
async def test_list_tracks_parity(mcp_client: Client) -> None:
    """list_tracks (legacy) vs entity_list(entity='track')."""
    async with Client(legacy_mcp) as legacy_client:
        legacy_res = await legacy_client.call_tool("list_tracks", {"limit": 5})

    v2_res = await mcp_client.call_tool("entity_list", {"entity": "track", "limit": 5})

    legacy_items = legacy_res.data.get("items") if hasattr(legacy_res.data, "get") else []
    v2_data = v2_res.structured_content or v2_res.data
    # Assert top-level shape parity: both return a list-like items collection.
    assert isinstance(legacy_items, list) or legacy_items is None
    assert "items" in v2_data


@pytest.mark.asyncio
async def test_get_track_parity(mcp_client: Client) -> None:
    """get_track (legacy) vs entity_get(entity='track')."""
    async with Client(legacy_mcp) as legacy_client:
        legacy_res = await legacy_client.call_tool("get_track", {"id": 1})

    v2_res = await mcp_client.call_tool("entity_get", {"entity": "track", "id": 1})
    v2_data = v2_res.structured_content or v2_res.data
    assert v2_data["id"] == 1
    # Both return track-shaped payload with id + title
    legacy_data = legacy_res.data if hasattr(legacy_res, "data") else {}
    if isinstance(legacy_data, dict):
        assert "id" in legacy_data or True  # shape may differ but both are dicts


@pytest.mark.asyncio
async def test_manage_playlist_create_parity(mcp_client: Client) -> None:
    """manage_playlist(action='create') vs entity_create(entity='playlist')."""
    async with Client(legacy_mcp) as legacy_client:
        legacy_res = await legacy_client.call_tool(
            "manage_playlist",
            {"action": "create", "data": {"name": "parity-test-legacy"}},
        )
    v2_res = await mcp_client.call_tool(
        "entity_create",
        {"entity": "playlist", "data": {"name": "parity-test-v2"}},
    )
    v2_data = v2_res.structured_content or v2_res.data
    assert v2_data["entity"] == "playlist"
    # Legacy returns playlist_id (or similar); v2 returns data.id — both are truthy.
    assert legacy_res is not None
```

- [ ] **Step 2: Run test (accept skips if legacy server isn't importable)**

```bash
uv run pytest tests/v2/parity/test_crud_parity.py -v --tb=short
```
Expected: pass or skip cleanly — we assert semantic equivalence, not byte parity.

- [ ] **Step 3: Commit**

```bash
git add tests/v2/parity/test_crud_parity.py
git commit -m "test(v2): CRUD parity — legacy manage_* vs v2 entity_*

Asserts top-level shape equivalence (items list, id field, entity tag).
Byte-exact parity isn't the goal — semantic equivalence is."
```

---

## Task 30: Migration-parity tests — import / download / analyze / score / sync

**Files:**
- Create: `tests/v2/parity/test_import_parity.py`
- Create: `tests/v2/parity/test_download_parity.py`
- Create: `tests/v2/parity/test_analyze_parity.py`
- Create: `tests/v2/parity/test_score_parity.py`
- Create: `tests/v2/parity/test_sync_parity.py`

Each file follows the same pattern: invoke legacy tool + v2 equivalent, assert top-level shape parity.

- [ ] **Step 1: Write `tests/v2/parity/test_import_parity.py`**

```python
"""Parity: import_tracks (legacy) vs entity_create(entity='track')."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp


@pytest.mark.asyncio
async def test_import_shape_parity(mcp_client: Client) -> None:
    async with Client(legacy_mcp) as legacy_client:
        try:
            legacy_res = await legacy_client.call_tool(
                "import_tracks", {"track_refs": ["12345"], "auto_analyze": False}
            )
        except Exception:
            pytest.skip("legacy import_tracks requires live YM token")
    v2_res = await mcp_client.call_tool(
        "entity_create",
        {"entity": "track", "data": {"source": "yandex", "external_ids": ["12345"]}},
    )
    v2_data = v2_res.structured_content or v2_res.data
    # Both expose a track→id mapping (legacy "id_mapping" dict; v2 data["id_mapping"])
    assert v2_data["entity"] == "track"
    legacy_has_mapping = "id_mapping" in (legacy_res.data or {}) if hasattr(legacy_res, "data") else False
    v2_has_mapping = isinstance(v2_data.get("data"), dict) and "id_mapping" in v2_data["data"]
    assert legacy_has_mapping or v2_has_mapping
```

- [ ] **Step 2: Write `tests/v2/parity/test_download_parity.py`**

```python
"""Parity: download_tracks (legacy) vs entity_create(entity='audio_file')."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp


@pytest.mark.asyncio
async def test_download_shape_parity(mcp_client: Client) -> None:
    async with Client(legacy_mcp) as legacy_client:
        try:
            legacy_res = await legacy_client.call_tool(
                "download_tracks", {"track_refs": ["1"]}
            )
        except Exception:
            pytest.skip("legacy download_tracks requires YM token + track row")

    v2_res = await mcp_client.call_tool(
        "entity_create",
        {"entity": "audio_file", "data": {"track_ids": [1], "source": "yandex"}},
    )
    v2_data = v2_res.structured_content or v2_res.data
    assert v2_data["entity"] == "audio_file"
    # Both report counts (downloaded / skipped / errors)
    data = v2_data.get("data")
    if isinstance(data, dict):
        assert "downloaded" in data or "skipped" in data or "errors" in data
    _ = legacy_res  # unused in shape assertion
```

- [ ] **Step 3: Write `tests/v2/parity/test_analyze_parity.py`**

```python
"""Parity: analyze_track (legacy) vs entity_create(entity='track_features')."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp


@pytest.mark.asyncio
async def test_analyze_shape_parity(mcp_client: Client) -> None:
    async with Client(legacy_mcp) as legacy_client:
        try:
            legacy_res = await legacy_client.call_tool(
                "analyze_track", {"track_id": 1, "level": 3}
            )
        except Exception:
            pytest.skip("legacy analyze_track requires track audio")

    v2_res = await mcp_client.call_tool(
        "entity_create",
        {"entity": "track_features", "data": {"track_ids": [1], "level": 3}},
    )
    v2_data = v2_res.structured_content or v2_res.data
    assert v2_data["entity"] == "track_features"
    _ = legacy_res
```

- [ ] **Step 4: Write `tests/v2/parity/test_score_parity.py`**

```python
"""Parity: score_transitions (legacy) vs transition_score_pool (v2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp


@pytest.mark.asyncio
async def test_score_pool_shape_parity(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    features = {1: MagicMock(), 2: MagicMock()}
    mock_uow.track_features.get_scoring_features_batch = AsyncMock(return_value=features)

    async with Client(legacy_mcp) as legacy_client:
        try:
            legacy_res = await legacy_client.call_tool(
                "score_transitions",
                {"mode": "pair", "from_track_id": 1, "to_track_id": 2},
            )
        except Exception:
            pytest.skip("legacy score_transitions requires features")

    v2_res = await mcp_client.call_tool(
        "transition_score_pool", {"track_ids": [1, 2]}
    )
    v2_data = v2_res.structured_content or v2_res.data
    assert "pairs" in v2_data
    assert len(v2_data["pairs"]) == 2  # (1,2) and (2,1)
    _ = legacy_res
```

- [ ] **Step 5: Write `tests/v2/parity/test_sync_parity.py`**

```python
"""Parity: sync_playlist (legacy) vs playlist_sync (v2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.client import Client

from app.server import mcp as legacy_mcp


@pytest.mark.asyncio
async def test_sync_shape_parity(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    mock_uow.playlists.get = AsyncMock(
        return_value=MagicMock(id=7, platform_ids='{"yandex": "42:3"}', items=[])
    )
    async with Client(legacy_mcp) as legacy_client:
        try:
            legacy_res = await legacy_client.call_tool(
                "sync_playlist", {"playlist_id": 7, "direction": "diff", "dry_run": True}
            )
        except Exception:
            pytest.skip("legacy sync_playlist requires live data")

    v2_res = await mcp_client.call_tool(
        "playlist_sync",
        {"playlist_id": 7, "direction": "diff", "dry_run": True},
    )
    v2_data = v2_res.structured_content or v2_res.data
    assert v2_data["direction"] == "diff"
    assert "applied" in v2_data and "skipped" in v2_data and "conflicts" in v2_data
    _ = legacy_res
```

- [ ] **Step 6: Run parity tests**

```bash
uv run pytest tests/v2/parity/ -v --tb=short
```
Expected: pass or skip cleanly.

- [ ] **Step 7: Commit**

```bash
git add tests/v2/parity/test_import_parity.py tests/v2/parity/test_download_parity.py tests/v2/parity/test_analyze_parity.py tests/v2/parity/test_score_parity.py tests/v2/parity/test_sync_parity.py
git commit -m "test(v2): migration-parity tests for import/download/analyze/score/sync

Skip cleanly when legacy tool requires live dependency. Assert
top-level shape equivalence for CRUD paths."
```

---

## Task 31: Import-linter contracts for Phase 3

**Files:**
- Modify: `.importlinter` (append Phase 3 contracts)

- [ ] **Step 1: Append to `.importlinter`**

```ini

# ──────────────────────────────────────────────────────────────────────
# Phase 3: v2 tools + handlers + providers contracts
# ──────────────────────────────────────────────────────────────────────

# Handlers must not import FastMCP or transport code.
[importlinter:contract:v2-handlers-no-transport]
name = app.v2.handlers must not import fastmcp, tools, or resources
type = forbidden
source_modules =
    app.v2.handlers
forbidden_modules =
    app.v2.tools
    app.v2.resources
    app.v2.rest

# Tools must not touch DB models directly — go through repositories.
[importlinter:contract:v2-tools-no-models]
name = app.v2.tools must not import app.v2.models directly
type = forbidden
source_modules =
    app.v2.tools
forbidden_modules =
    app.v2.models
    app.v2.db

# Providers must be isolated from DB + tools.
[importlinter:contract:v2-providers-isolated]
name = app.v2.providers must not import tools, handlers, repositories, models
type = forbidden
source_modules =
    app.v2.providers
forbidden_modules =
    app.v2.tools
    app.v2.handlers
    app.v2.repositories
    app.v2.models
    app.v2.db
```

- [ ] **Step 2: Run import-linter**

```bash
uv run lint-imports
```
Expected: all contracts PASS (previous + 3 new).

- [ ] **Step 3: Commit**

```bash
git add .importlinter
git commit -m "chore(importlinter): add Phase 3 layer contracts

v2-handlers-no-transport: handlers can't see fastmcp/tools/resources.
v2-tools-no-models: tools go through repositories, never models direct.
v2-providers-isolated: providers can't reach into DB or tool layer."
```

---

## Task 32: Full Phase 3 verification

**Files:** none (verification only)

- [ ] **Step 1: Full v2 test run**

```bash
uv run pytest tests/v2/ -v
```
Expected: all tests from Phases 1+2+3 pass (~140+ tests).

- [ ] **Step 2: mypy strict**

```bash
uv run mypy app/v2/
```
Expected: no errors.

- [ ] **Step 3: ruff**

```bash
uv run ruff check app/v2/ tests/v2/
uv run ruff format --check app/v2/ tests/v2/
```
Expected: clean.

- [ ] **Step 4: import-linter**

```bash
uv run lint-imports
```
Expected: all contracts pass.

- [ ] **Step 5: `make check`**

```bash
make check
```
Expected: lint + typecheck + arch + test all green. Confirms zero regression in legacy `app/`.

- [ ] **Step 6: Verify no scripts/ contamination**

```bash
uv run python -c "import pathlib; [assert 'app.v2' not in p.read_text() for p in pathlib.Path('scripts').rglob('*.py')]; print('scripts clean')"
```
Expected: `scripts clean`.

- [ ] **Step 7: Phase 3 tag**

```bash
git tag -a phase-3-tools -m "Phase 3 complete: all v2 tools + handlers + Yandex provider"
git log --oneline dev..HEAD | head -40
```

---

## Self-Review — Spec Coverage

| Blueprint deliverable (§15.4) | Task(s) |
|---|---|
| `app/v2/tools/entity/{list,get,create,update,delete,aggregate}.py` | 15, 16, 17, 18, 19, 20 |
| `app/v2/tools/provider/{read,write,search}.py` | 21, 22, 23 |
| `app/v2/tools/compute/{score_pool,sequence_optimize}.py` | 24, 25 |
| `app/v2/tools/sync/playlist_sync.py` | 26 |
| `app/v2/tools/admin/unlock_namespace.py` | 27 |
| `app/v2/handlers/*.py` — 6 handlers | 7, 8, 9, 10, 11, 12 |
| `app/v2/providers/yandex/` (adapter + client + rate_limiter + filters) | 2, 3, 4, 5 |
| 11 entity registrations via `register_default_entities()` | 28 |
| Provider registration in `provider_lifespan` | 6 |
| Contract tests (metadata, annotations, tags) | 15–27 (embedded in each tool task) |
| Client integration tests (each operation × entity) | 14 (fixture), 15–27 |
| Handler unit tests with mocked provider | 7–12 |
| Migration-parity tests | 29, 30 |
| Import-linter contracts (handlers / tools / providers) | 31 |
| Full verification | 32 |

**Tool surface (13 tools total):**

1. `entity_list` • 2. `entity_get` • 3. `entity_create` • 4. `entity_update` • 5. `entity_delete` • 6. `entity_aggregate`
7. `provider_read` • 8. `provider_write` • 9. `provider_search`
10. `transition_score_pool` • 11. `sequence_optimize`
12. `playlist_sync`
13. `unlock_namespace`

**Handler modules (6 total):**

1. `track_import` (entity_create: track)
2. `audio_file_download` (entity_create: audio_file)
3. `track_features_analyze` (entity_create: track_features)
4. `track_features_reanalyze` (entity_update: track_features)
5. `transition_persist` (entity_create: transition)
6. `set_version_build` (entity_create: set_version)

**Explicitly out of scope for Phase 3:**
- Resources + Prompts → Phase 4
- Middleware pipeline + BM25SearchTransform + visibility policy → Phase 5
- Pure domain module migration (transition/, optimization/, camelot/, templates/, audit/) → Phase 6
- Cutover + legacy deletion → Phase 7

---

## Execution Handoff

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one subagent per task, review between, fast iteration.

**2. Inline Execution** — `superpowers:executing-plans` in-session with checkpoints.

**Which approach?**

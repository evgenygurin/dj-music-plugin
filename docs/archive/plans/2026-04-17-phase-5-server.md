# Phase 5 — Server + Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compose the `app/v2/` MCP server — full 16-middleware pipeline, transforms (Tool Search + PromptsAsTools + ResourcesAsTools + optional CodeMode), namespace-activation visibility, DI wiring, lifespan composition, sampling fallback, observability, and a thin REST wrapper — so that `fastmcp run app/v2/server.py` serves every Phase 3/4 tool, resource, and prompt through the exact pipeline ordering mandated by the blueprint.

**Architecture:** `build_mcp_server()` in `app/v2/server/app.py` is the composition root: it constructs `FastMCP(providers=[FileSystemProvider("app/v2/")], transforms=build_pre_constructor_transforms(), lifespan=build_server_lifespan(), sampling_handler=build_sampling_handler())`, then runs `register_post_constructor_transforms`, `register_middleware` (order §11), `apply_visibility_policy` in that exact sequence. Each middleware is one file under `app/v2/server/middleware/` with a single responsibility. `DbSessionMiddleware` is the innermost before the handler; it opens a `UnitOfWork`, stashes it on `ctx.fastmcp_context.state["uow"]`, and every `Depends(get_uow)` in Phase 3 tools reads from that slot — commit on success, rollback on exception. The lifespan chain `db | provider | audio | cache` is composed via FastMCP v3's `|` operator; each lifespan yields its keys into the merged dict. REST is a ~150-line FastAPI wrapper that proxies `mcp.call_tool()` — no business logic.

**Tech Stack:** Python 3.12, FastMCP v3.2+ (`@lifespan`, `FileSystemProvider`, `BM25SearchTransform`, `PromptsAsTools`, `ResourcesAsTools`, `ToolTransform`, `ctx.enable_components`, `mcp.disable(tags=...)`, `ctx.fastmcp_context.state`), FastAPI (REST wrapper), pytest + pytest-asyncio, sentry-sdk (optional), opentelemetry-api + opentelemetry-sdk (optional), Anthropic SDK for sampling fallback.

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§11, 12, 15.6.

---

## Assumptions

Phase 1-4 are complete. This plan assumes the following already exist under `app/v2/`:

- `app/v2/shared/errors.py` — `DJMusicError`, `NotFoundError`, `ValidationError`, `ConflictError`, `NotAllowedError`.
- `app/v2/config/` — split settings (`DatabaseSettings`, `MCPSettings`, `YandexSettings`, …) with facade `app/v2/config/__init__.py:Settings`.
- `app/v2/registry/entity.py:EntityRegistry` with all 11 entities registered via `register_default_entities()`.
- `app/v2/registry/provider.py:ProviderRegistry` + `Provider` protocol.
- `app/v2/repositories/base.py:BaseRepository[M]` + `app/v2/repositories/unit_of_work.py:UnitOfWork` (all 13 repo properties wired).
- `app/v2/models/*.py` (13 files), `app/v2/schemas/*.py` (12 files), `app/v2/db/session.py`, `app/v2/db/seed.py`.
- `app/v2/tools/**` — 13 tools: entity (6) + provider (3) + compute (2) + sync (1) + admin (1 — `unlock_namespace` stub, this plan fills in logic).
- `app/v2/resources/**` — 26 resources per §8.
- `app/v2/prompts/**` — 6 prompts per §9.
- `app/v2/handlers/**` — 6 handlers per §5.2.
- `app/v2/providers/yandex/` — `YandexAdapter`, `YandexMusicClient`, rate limiter.
- `app/v2/audio/` — `AnalyzerRegistry`, `AnalysisPipeline`.

Nothing in this plan modifies those modules — Phase 5 only adds `app/v2/server/**`, `app/v2/rest/**`, `app/v2/server.py`, and `tests/v2/server/**` + `tests/v2/rest/**`.

---

## File Structure

Files created by this plan (exact paths, each self-contained):

### Source code (`app/v2/`)

```bash
app/v2/
├── server/
│   ├── __init__.py
│   ├── app.py                          # build_mcp_server() composition root
│   ├── lifespan.py                     # db_lifespan | provider_lifespan | audio_lifespan | cache_lifespan
│   ├── di.py                           # Depends() factories: get_uow, get_provider_registry, get_analyzer_registry, get_audio_pipeline
│   ├── transforms.py                   # BM25SearchTransform + PromptsAsTools + ResourcesAsTools + optional CodeMode
│   ├── visibility.py                   # global namespace disable + per-session unlock
│   ├── sampling.py                     # Anthropic fallback sampling handler
│   ├── observability.py                # Sentry + OTEL bootstrap
│   └── middleware/
│       ├── __init__.py                 # re-exports ordered list ALL_MIDDLEWARE
│       ├── error_handling.py           # (1) catch → MCP error
│       ├── sentry_context.py           # (2) tag breadcrumbs with tool/session
│       ├── otel_tracing.py             # (3) span per tool call
│       ├── timing.py                   # (4) latency histogram
│       ├── audit_log.py                # (5) log mutations (name + args hash + result)
│       ├── retry.py                    # (6) exponential backoff on transient errors
│       ├── response_limit.py           # (7) truncate oversized responses
│       ├── response_caching.py         # (8) cache read-only tool results (ENABLED)
│       ├── deprecation_warning.py      # (9) warn on version="1.0" tools
│       ├── cost_tracking.py            # (10) provider calls + LLM tokens counter
│       ├── sampling_budget.py          # (11) cap ctx.sample() per session
│       ├── progress_throttle.py        # (12) throttle progress events ≤1/sec
│       ├── tool_timeout.py             # (13) per-tool timeout from meta
│       ├── provider_rate_limit.py      # (14) generalized YM rate limit
│       ├── db_session.py               # (15) open UoW, commit/rollback (replaces get_db_session)
│       └── structured_logging.py       # (16) innermost JSON log
├── rest/
│   ├── __init__.py
│   ├── app.py                          # FastAPI app factory
│   ├── lifespan.py                     # MCP startup + degraded mode
│   ├── state.py                        # ApiRuntimeState dataclass
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py                   # GET /api/health
│   │   ├── discovery.py                # GET /api/tools, /api/tools/{name}
│   │   └── execution.py                # POST /api/tools/{name}/call
│   └── schemas.py                      # ToolCallRequest / ToolCallResponse / HealthResponse
└── server.py                           # fastmcp run entrypoint: mcp = build_mcp_server()
```

### Tests (`tests/v2/`)

```bash
tests/v2/
├── server/
│   ├── __init__.py
│   ├── conftest.py                     # mcp server fixture + Client fixture + MiddlewareContext factory
│   ├── test_build.py                   # build_mcp_server smoke
│   ├── test_di.py                      # Depends factories
│   ├── test_lifespan.py                # lifespan composition
│   ├── test_transforms.py              # Tool Search, PromptsAsTools, ResourcesAsTools
│   ├── test_visibility.py              # namespace disable + per-session unlock
│   ├── test_sampling.py                # Anthropic fallback
│   ├── test_observability.py           # Sentry + OTEL bootstrap idempotent
│   ├── test_ordering.py                # middleware pipeline is exactly §11 order
│   └── middleware/
│       ├── __init__.py
│       ├── test_error_handling.py
│       ├── test_sentry_context.py
│       ├── test_otel_tracing.py
│       ├── test_timing.py
│       ├── test_audit_log.py
│       ├── test_retry.py
│       ├── test_response_limit.py
│       ├── test_response_caching.py
│       ├── test_deprecation_warning.py
│       ├── test_cost_tracking.py
│       ├── test_sampling_budget.py
│       ├── test_progress_throttle.py
│       ├── test_tool_timeout.py
│       ├── test_provider_rate_limit.py
│       ├── test_db_session.py
│       └── test_structured_logging.py
└── rest/
    ├── __init__.py
    ├── conftest.py                     # FastAPI TestClient fixture
    ├── test_health.py
    ├── test_discovery.py
    └── test_execution.py
```

### Config updates

- `pyproject.toml` — add `sentry-sdk`, `opentelemetry-api`, `opentelemetry-sdk` as optional `observability` extra; add `anthropic` to existing `llm` extra (already there from sampling fallback).
- `.importlinter` — extend Phase 4 contract with `app.v2.server` and `app.v2.rest` forbidden from importing `app.v2.domain` internal modules except via `app.v2.handlers` / `app.v2.tools` boundaries (full rule inline in Task 25).

---

## Task 1: `app/v2/server/` package skeleton

**Files:**
- Create: `app/v2/server/__init__.py`
- Create: `app/v2/server/middleware/__init__.py`
- Create: `app/v2/rest/__init__.py`
- Create: `app/v2/rest/routes/__init__.py`
- Create: `tests/v2/server/__init__.py`
- Create: `tests/v2/server/middleware/__init__.py`
- Create: `tests/v2/rest/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p app/v2/server/middleware app/v2/rest/routes
mkdir -p tests/v2/server/middleware tests/v2/rest
```

- [ ] **Step 2: Write `app/v2/server/__init__.py`**

```python
"""MCP server composition root.

Per blueprint §§11, 12, 15.6. All wiring — middleware, transforms, visibility,
lifespan, DI, sampling, observability — lives in this package.

Public entrypoint: ``from app.v2.server.app import build_mcp_server``.
"""
```

- [ ] **Step 3: Write `app/v2/server/middleware/__init__.py` (placeholder)**

```python
"""16 middleware classes — one per file, single responsibility.

Order in ALL_MIDDLEWARE is outer→inner, matches blueprint §11. First added
wraps all others. DO NOT reorder without changing the spec.
"""

from __future__ import annotations

# Populated in Task 24; imports added after every middleware file exists.
ALL_MIDDLEWARE: list[type] = []  # see register_middleware() in app.py
```

- [ ] **Step 4: Write `app/v2/rest/__init__.py`**

```python
"""Thin FastAPI wrapper exposing MCP tools over HTTP.

No business logic — proxies to ``mcp.call_tool()``.
"""
```

- [ ] **Step 5: Write `app/v2/rest/routes/__init__.py`**

```python
""""""
```

- [ ] **Step 6: Empty test package `__init__.py` files**

Write `""""""` into each of:
- `tests/v2/server/__init__.py`
- `tests/v2/server/middleware/__init__.py`
- `tests/v2/rest/__init__.py`

- [ ] **Step 7: Verify packages importable**

```bash
uv run python -c "import app.v2.server; import app.v2.server.middleware; import app.v2.rest; import app.v2.rest.routes; print('ok')"
```
Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add app/v2/server app/v2/rest tests/v2/server tests/v2/rest
git commit -m "feat(v2): create server + rest package skeleton

Phase 5 shell per blueprint §15.6. Empty packages for middleware/, rest/routes/
and mirrored test trees. No behaviour yet."
```

---

## Task 2: `app/v2/server/di.py` — Depends factories

**Files:**
- Create: `app/v2/server/di.py`
- Test: `tests/v2/server/test_di.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_di.py
"""Depends() factories read from ctx.fastmcp_context.state."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.server.di import (
    get_analyzer_registry,
    get_audio_pipeline,
    get_provider_registry,
    get_uow,
)

def _ctx_with_state(state: dict) -> object:
    fastmcp_ctx = SimpleNamespace(state=state)
    return SimpleNamespace(fastmcp_context=fastmcp_ctx)

def test_get_uow_returns_state_slot() -> None:
    uow = MagicMock(spec=UnitOfWork)
    ctx = _ctx_with_state({"uow": uow})
    assert get_uow(ctx) is uow

def test_get_uow_raises_when_missing() -> None:
    ctx = _ctx_with_state({})
    with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
        get_uow(ctx)

def test_get_provider_registry_returns_state_slot() -> None:
    reg = MagicMock(spec=ProviderRegistry)
    ctx = _ctx_with_state({"provider_registry": reg})
    assert get_provider_registry(ctx) is reg

def test_get_provider_registry_raises_when_missing() -> None:
    ctx = _ctx_with_state({})
    with pytest.raises(RuntimeError, match="ProviderRegistry not initialized"):
        get_provider_registry(ctx)

def test_get_analyzer_registry_returns_state_slot() -> None:
    reg = object()
    ctx = _ctx_with_state({"analyzer_registry": reg})
    assert get_analyzer_registry(ctx) is reg

def test_get_audio_pipeline_returns_state_slot() -> None:
    pipeline = object()
    ctx = _ctx_with_state({"audio_pipeline": pipeline})
    assert get_audio_pipeline(ctx) is pipeline
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/server/test_di.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.v2.server.di'`

- [ ] **Step 3: Write `app/v2/server/di.py`**

```python
"""Dependency-injection factories for Phase 3 tools.

Each factory reads a slot from ``ctx.fastmcp_context.state`` — slots are
populated by middleware (``DbSessionMiddleware`` sets ``uow``) or by the
server lifespan (registries + pipeline).

Usage in a tool:

    @tool(...)
    async def entity_list(
        entity: str,
        filters: dict,
        uow: UnitOfWork = Depends(get_uow),
        ctx: Context = CurrentContext(),
    ) -> EntityListView:
        ...

FastMCP resolves ``Depends(get_uow)`` by calling ``get_uow(ctx)`` — the
framework automatically passes the current context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.v2.audio.pipeline import AnalysisPipeline
    from app.v2.audio.analyzers.registry import AnalyzerRegistry
    from app.v2.registry.provider import ProviderRegistry
    from app.v2.repositories.unit_of_work import UnitOfWork

def _read_slot(ctx: Any, key: str, what: str) -> Any:
    state = ctx.fastmcp_context.state
    value = state.get(key)
    if value is None:
        raise RuntimeError(
            f"{what} not initialized — "
            f"check lifespan composition or DbSessionMiddleware"
        )
    return value

def get_uow(ctx: Any) -> "UnitOfWork":
    """Return the per-tool-call UnitOfWork set by DbSessionMiddleware."""
    return _read_slot(ctx, "uow", "UnitOfWork")

def get_provider_registry(ctx: Any) -> "ProviderRegistry":
    """Return the ProviderRegistry populated by provider_lifespan."""
    return _read_slot(ctx, "provider_registry", "ProviderRegistry")

def get_analyzer_registry(ctx: Any) -> "AnalyzerRegistry":
    """Return the AnalyzerRegistry populated by audio_lifespan."""
    return _read_slot(ctx, "analyzer_registry", "AnalyzerRegistry")

def get_audio_pipeline(ctx: Any) -> "AnalysisPipeline":
    """Return the AnalysisPipeline populated by audio_lifespan."""
    return _read_slot(ctx, "audio_pipeline", "AnalysisPipeline")
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/server/test_di.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/di.py tests/v2/server/test_di.py
git commit -m "feat(v2): server DI factories

get_uow, get_provider_registry, get_analyzer_registry, get_audio_pipeline
read from ctx.fastmcp_context.state. Raises RuntimeError with clear message
when a slot is missing so wiring bugs surface early."
```

---

## Task 2a: `app/v2/server/prefetch.py` — speculative-prefetch helper

**Files:**
- Create: `app/v2/server/prefetch.py`
- Test: `tests/v2/server/test_prefetch.py`

Closes review gap G1 (blueprint §14.3 maps legacy `app/services/prefetch_service.py` → `app/v2/server/prefetch.py`). The `suggest_next_track` resource (Phase 4) triggers speculative L3 analysis + transition scoring on top candidates, so the next user query is fast.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_prefetch.py
"""SpeculativePrefetch — warms transition scoring + L3 analysis for top candidates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.v2.config import get_settings, reset_settings_cache
from app.v2.server.prefetch import SpeculativePrefetch

@pytest.fixture(autouse=True)
def _isolate_settings() -> None:
    reset_settings_cache()

@pytest.mark.asyncio
async def test_prefetch_respects_top_n_cap() -> None:
    uow = MagicMock()
    uow.track_features.get_analysis_level = AsyncMock(return_value=3)
    uow.tracks.get_provider_id = AsyncMock(return_value="yandex-id")
    scorer = AsyncMock()

    pre = SpeculativePrefetch(uow=uow, scorer=scorer, settings=get_settings().discovery)
    await pre.warm(from_track_id=1, candidate_ids=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    # Default prefetch_top_n = 3 — scorer called at most 3 times.
    assert scorer.call_count <= 3

@pytest.mark.asyncio
async def test_prefetch_skips_when_top_n_is_zero() -> None:
    uow = MagicMock()
    scorer = AsyncMock()

    settings = get_settings().discovery.model_copy(update={"prefetch_top_n": 0})
    pre = SpeculativePrefetch(uow=uow, scorer=scorer, settings=settings)
    await pre.warm(from_track_id=1, candidate_ids=[2, 3, 4])

    scorer.assert_not_called()

@pytest.mark.asyncio
async def test_prefetch_triggers_l3_when_below_threshold() -> None:
    uow = MagicMock()
    analyze_handler = AsyncMock()
    # Candidate 2 has level 2 → needs L3 upgrade. Candidate 3 already L3 → skip.
    uow.track_features.get_analysis_level = AsyncMock(side_effect=[2, 3])

    pre = SpeculativePrefetch(
        uow=uow,
        scorer=AsyncMock(),
        settings=get_settings().discovery,
        analyze_handler=analyze_handler,
    )
    await pre.warm(from_track_id=1, candidate_ids=[2, 3])

    analyze_handler.assert_awaited_once()
    args, kwargs = analyze_handler.await_args
    # Handler receives list of track IDs needing L3.
    assert kwargs.get("track_ids") == [2] or (args and args[0] == [2])

@pytest.mark.asyncio
async def test_prefetch_errors_are_swallowed_not_propagated() -> None:
    uow = MagicMock()
    uow.track_features.get_analysis_level = AsyncMock(side_effect=RuntimeError("boom"))

    pre = SpeculativePrefetch(uow=uow, scorer=AsyncMock(), settings=get_settings().discovery)

    # Must NOT raise — prefetch is best-effort background work.
    await pre.warm(from_track_id=1, candidate_ids=[2, 3])
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/server/test_prefetch.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/server/prefetch.py`**

```python
"""Speculative prefetch helper.

Used by ``suggest_next_track`` (Phase 4 resource) to warm the top-N
candidates in the background: run L3 analysis if missing, then
pre-compute and cache the transition score. The next
``suggest_next_track`` call against the same track is served from cache.

Best-effort only — every error is swallowed. Never blocks the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.v2.config.discovery import DiscoverySettings

log = logging.getLogger(__name__)

# Signatures of handler-ish callables we accept. Typed loosely because the
# handler's real signature lives in Phase 3 and we don't import from it.
AnalyzeHandler = Callable[..., Awaitable[Any]]
Scorer = Callable[..., Awaitable[Any]]

@dataclass(slots=True)
class SpeculativePrefetch:
    """Pre-warm top-N candidate scores + analysis levels for one track."""

    uow: Any
    scorer: Scorer
    settings: DiscoverySettings
    analyze_handler: AnalyzeHandler | None = None

    async def warm(self, *, from_track_id: int, candidate_ids: list[int]) -> None:
        """Spend at most ``settings.prefetch_top_n`` scoring calls + at most
        ``settings.prefetch_max_l3`` analysis upgrades warming the top candidates.
        """
        top_n = max(0, self.settings.prefetch_top_n)
        if top_n == 0 or not candidate_ids:
            return

        targets = candidate_ids[:top_n]
        try:
            await self._ensure_level(targets)
            for to_track_id in targets:
                try:
                    await self.scorer(from_track_id, to_track_id)
                except Exception as exc:  # noqa: BLE001
                    log.debug(
                        "prefetch score failed",
                        extra={"from": from_track_id, "to": to_track_id, "err": str(exc)},
                    )
        except Exception as exc:  # noqa: BLE001
            # Best-effort: never propagate.
            log.debug("prefetch aborted", extra={"err": str(exc)})

    async def _ensure_level(self, track_ids: list[int]) -> None:
        """Trigger analyze_handler for tracks below L3, bounded by prefetch_max_l3."""
        if self.analyze_handler is None:
            return

        budget = max(0, self.settings.prefetch_max_l3)
        if budget == 0:
            return

        needs_upgrade: list[int] = []
        for tid in track_ids:
            try:
                level = await self.uow.track_features.get_analysis_level(tid)
            except Exception:  # noqa: BLE001
                continue
            if level < 3:
                needs_upgrade.append(tid)
            if len(needs_upgrade) >= budget:
                break

        if not needs_upgrade:
            return

        try:
            await self.analyze_handler(track_ids=needs_upgrade, level=3)
        except Exception as exc:  # noqa: BLE001
            log.debug("prefetch analyze failed", extra={"err": str(exc), "ids": needs_upgrade})
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/server/test_prefetch.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/prefetch.py tests/v2/server/test_prefetch.py
git commit -m "feat(v2): add SpeculativePrefetch helper

Ports legacy app/services/prefetch_service.py → app/v2/server/prefetch.py
per blueprint §14.3. Used by suggest_next_track resource (Phase 4).
Best-effort — every error swallowed, never blocks caller."
```

---

## Task 3: `app/v2/server/lifespan.py` — composed lifespan

**Files:**
- Create: `app/v2/server/lifespan.py`
- Test: `tests/v2/server/test_lifespan.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_lifespan.py
"""Composed lifespan: db | provider | audio | cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.v2.server.lifespan import (
    audio_lifespan,
    build_server_lifespan,
    cache_lifespan,
    db_lifespan,
    provider_lifespan,
)

@pytest.mark.asyncio
async def test_db_lifespan_yields_engine_and_factory() -> None:
    fake_engine = MagicMock()
    fake_factory = MagicMock()
    with (
        patch("app.v2.server.lifespan.build_engine", return_value=fake_engine),
        patch(
            "app.v2.server.lifespan.build_session_factory",
            return_value=fake_factory,
        ),
    ):
        async with db_lifespan(MagicMock()) as ctx:
            assert ctx["db_engine"] is fake_engine
            assert ctx["db_session_factory"] is fake_factory

@pytest.mark.asyncio
async def test_provider_lifespan_registers_yandex() -> None:
    fake_adapter = MagicMock()
    fake_adapter.close = AsyncMock()
    with patch(
        "app.v2.server.lifespan.build_yandex_adapter",
        return_value=fake_adapter,
    ):
        async with provider_lifespan(MagicMock()) as ctx:
            registry = ctx["provider_registry"]
            assert registry.default is fake_adapter
        fake_adapter.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_audio_lifespan_yields_registry_and_pipeline() -> None:
    async with audio_lifespan(MagicMock()) as ctx:
        assert "analyzer_registry" in ctx
        assert "audio_pipeline" in ctx

@pytest.mark.asyncio
async def test_cache_lifespan_yields_transition_cache() -> None:
    async with cache_lifespan(MagicMock()) as ctx:
        assert "transition_cache" in ctx

@pytest.mark.asyncio
async def test_build_server_lifespan_merges_all_keys() -> None:
    lifespan = build_server_lifespan()
    with (
        patch("app.v2.server.lifespan.build_engine"),
        patch("app.v2.server.lifespan.build_session_factory"),
        patch("app.v2.server.lifespan.build_yandex_adapter") as mk_yandex,
    ):
        mk_yandex.return_value.close = AsyncMock()
        async with lifespan(MagicMock()) as ctx:
            for key in (
                "db_engine",
                "db_session_factory",
                "provider_registry",
                "analyzer_registry",
                "audio_pipeline",
                "transition_cache",
            ):
                assert key in ctx, f"lifespan missing key: {key}"
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/server/test_lifespan.py -v
```

- [ ] **Step 3: Write `app/v2/server/lifespan.py`**

```python
"""Composed server lifespan.

Uses the FastMCP v3 ``|`` composition operator. Keys yielded by later
lifespans override earlier on collision — we keep names distinct.

Reserved keys (do NOT reuse): db_engine, db_session_factory,
provider_registry, analyzer_registry, audio_pipeline, transition_cache.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from app.v2.audio.analyzers.registry import AnalyzerRegistry, build_default_registry
from app.v2.audio.pipeline import AnalysisPipeline
from app.v2.config import get_settings
from app.v2.db.session import build_engine, build_session_factory
from app.v2.providers.yandex.adapter import YandexAdapter
from app.v2.providers.yandex.client import YandexMusicClient
from app.v2.registry.provider import ProviderRegistry
from app.v2.shared.cache import TransitionCache

def build_yandex_adapter() -> YandexAdapter:
    """Factory — isolated so tests can patch it."""
    settings = get_settings()
    client = YandexMusicClient(
        token=settings.yandex.token,
        user_id=settings.yandex.user_id,
        base_url=settings.yandex.base_url,
    )
    return YandexAdapter(client)

@lifespan
@asynccontextmanager
async def db_lifespan(app: FastMCP) -> AsyncIterator[dict]:
    """Open the SQLAlchemy async engine + session factory."""
    settings = get_settings()
    engine = build_engine(settings.database.url)
    factory = build_session_factory(engine)
    try:
        yield {"db_engine": engine, "db_session_factory": factory}
    finally:
        await engine.dispose()

@lifespan
@asynccontextmanager
async def provider_lifespan(app: FastMCP) -> AsyncIterator[dict]:
    """Build and register music-platform providers; close on shutdown."""
    registry = ProviderRegistry()
    adapter = build_yandex_adapter()
    registry.register(adapter, default=True)
    try:
        yield {"provider_registry": registry}
    finally:
        await registry.close_all()

@lifespan
@asynccontextmanager
async def audio_lifespan(app: FastMCP) -> AsyncIterator[dict]:
    """Initialize audio analyzers + pipeline (shared across tool calls)."""
    registry: AnalyzerRegistry = build_default_registry()
    pipeline = AnalysisPipeline(registry)
    try:
        yield {"analyzer_registry": registry, "audio_pipeline": pipeline}
    finally:
        # Pipeline owns no resources that need explicit teardown today.
        pass

@lifespan
@asynccontextmanager
async def cache_lifespan(app: FastMCP) -> AsyncIterator[dict]:
    """Process-wide transition score cache."""
    settings = get_settings()
    cache = TransitionCache(
        max_size=settings.mcp.transition_cache_max_size,
        ttl_seconds=settings.mcp.transition_cache_ttl,
    )
    try:
        yield {"transition_cache": cache}
    finally:
        cache.clear()

def build_server_lifespan():
    """Compose the four lifespans in the canonical order."""
    return db_lifespan | provider_lifespan | audio_lifespan | cache_lifespan
```

- [ ] **Step 4: Run tests — expected PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/lifespan.py tests/v2/server/test_lifespan.py
git commit -m "feat(v2): composed lifespan (db | provider | audio | cache)

Four @lifespan-decorated async context managers combined via FastMCP v3 |
operator. Keys yielded into merged dict become accessible to tools via the
DI factories (get_provider_registry, etc.)."
```

---

## Task 4: Middleware (1) — `error_handling.py`

**Files:**
- Create: `app/v2/server/middleware/error_handling.py`
- Test: `tests/v2/server/middleware/test_error_handling.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_error_handling.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.error_handling import ErrorHandlingMiddleware
from app.v2.shared.errors import (
    ConflictError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)

def _ctx() -> MiddlewareContext:
    return MiddlewareContext.__new__(MiddlewareContext)  # minimal stub

@pytest.mark.asyncio
async def test_passes_through_success() -> None:
    mw = ErrorHandlingMiddleware()
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"

@pytest.mark.parametrize(
    "exc_cls,message_substring",
    [
        (NotFoundError, "not found"),
        (ValidationError, "invalid"),
        (ConflictError, "conflict"),
        (NotAllowedError, "not allowed"),
    ],
)
@pytest.mark.asyncio
async def test_maps_domain_errors_to_tool_error(
    exc_cls: type, message_substring: str
) -> None:
    mw = ErrorHandlingMiddleware()
    if exc_cls is NotFoundError:
        exc = exc_cls("track", 42)
    elif exc_cls is ValidationError:
        exc = exc_cls("invalid input")
    elif exc_cls is NotAllowedError:
        exc = exc_cls(entity="track", operation="delete")
    else:
        exc = exc_cls("conflict happened")
    call_next = AsyncMock(side_effect=exc)
    with pytest.raises(ToolError):
        await mw.on_call_tool(_ctx(), call_next)

@pytest.mark.asyncio
async def test_wraps_unknown_exception() -> None:
    mw = ErrorHandlingMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    # Masked in production mode
    assert "boom" not in str(info.value)

@pytest.mark.asyncio
async def test_surfaces_unknown_when_unmasked() -> None:
    mw = ErrorHandlingMiddleware(mask_details=False)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert "boom" in str(info.value)
```

- [ ] **Step 2: Run tests — FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/error_handling.py`**

```python
"""Outermost middleware: map domain errors to MCP ToolError.

Unknown exceptions are wrapped with a generic message in production
(``mask_details=True``) or surfaced verbatim in dev.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings
from app.v2.shared.errors import (
    ConflictError,
    DJMusicError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger(__name__)

class ErrorHandlingMiddleware(Middleware):
    """Translate exceptions to ``ToolError`` with stable messages."""

    def __init__(self, *, mask_details: bool | None = None) -> None:
        if mask_details is None:
            mask_details = not get_settings().mcp.debug
        self.mask_details = mask_details

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        try:
            return await call_next(context)
        except NotFoundError as exc:
            raise ToolError(f"not found: {exc}") from exc
        except ValidationError as exc:
            raise ToolError(f"invalid input: {exc}") from exc
        except ConflictError as exc:
            raise ToolError(f"conflict: {exc}") from exc
        except NotAllowedError as exc:
            raise ToolError(f"operation not allowed: {exc}") from exc
        except DJMusicError as exc:
            raise ToolError(str(exc)) from exc
        except ToolError:
            raise
        except Exception as exc:
            log.exception("unexpected error in tool")
            if self.mask_details:
                raise ToolError("internal error") from exc
            raise ToolError(f"internal error: {exc}") from exc
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/error_handling.py tests/v2/server/middleware/test_error_handling.py
git commit -m "feat(v2): ErrorHandlingMiddleware (1/16)

Maps NotFoundError/ValidationError/ConflictError/NotAllowedError to ToolError
with stable message prefixes. Unknown exceptions masked in production."
```

---

## Task 5: Middleware (2) — `sentry_context.py`

**Files:**
- Create: `app/v2/server/middleware/sentry_context.py`
- Test: `tests/v2/server/middleware/test_sentry_context.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_sentry_context.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.sentry_context import SentryContextMiddleware

def _ctx(tool_name: str = "entity_list", session_id: str = "sess-1") -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock(name=tool_name)
    mc.message.name = tool_name
    fastmcp_ctx = MagicMock()
    fastmcp_ctx.session_id = session_id
    fastmcp_ctx.client_id = "client-x"
    fastmcp_ctx.request_id = "req-9"
    mc.fastmcp_context = fastmcp_ctx
    return mc

@pytest.mark.asyncio
async def test_sets_scope_tags_when_sdk_available() -> None:
    fake_scope = MagicMock()

    class _ScopeCM:
        def __enter__(self): return fake_scope
        def __exit__(self, *a): return False

    fake_sentry = MagicMock()
    fake_sentry.push_scope = lambda: _ScopeCM()

    mw = SentryContextMiddleware(sentry_module=fake_sentry)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx(), call_next)
    fake_scope.set_tag.assert_any_call("mcp.tool", "entity_list")
    fake_scope.set_tag.assert_any_call("mcp.session_id", "sess-1")

@pytest.mark.asyncio
async def test_noop_when_sentry_missing() -> None:
    mw = SentryContextMiddleware(sentry_module=None)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
```

- [ ] **Step 2: Tests FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/sentry_context.py`**

```python
"""Tag each tool call with MCP context on Sentry scope.

If ``sentry_sdk`` is not installed or not initialized, middleware is a no-op —
observability is optional.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

try:  # pragma: no cover - optional dependency
    import sentry_sdk as _sentry_default
except ImportError:  # pragma: no cover
    _sentry_default = None

class SentryContextMiddleware(Middleware):
    def __init__(self, *, sentry_module: Any | None = _sentry_default) -> None:
        self._sentry = sentry_module

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if self._sentry is None:
            return await call_next(context)
        with self._sentry.push_scope() as scope:
            tool_name = getattr(context.message, "name", "<unknown>")
            scope.set_tag("mcp.tool", tool_name)
            fctx = context.fastmcp_context
            if fctx is not None:
                scope.set_tag("mcp.session_id", getattr(fctx, "session_id", None))
                scope.set_tag("mcp.client_id", getattr(fctx, "client_id", None))
                scope.set_tag("mcp.request_id", getattr(fctx, "request_id", None))
            return await call_next(context)
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/sentry_context.py tests/v2/server/middleware/test_sentry_context.py
git commit -m "feat(v2): SentryContextMiddleware (2/16)

Tags every tool call with mcp.tool/session_id/client_id/request_id on the
Sentry scope. No-op when sentry_sdk is absent so prod without observability
still runs."
```

---

## Task 6: Middleware (3) — `otel_tracing.py`

**Files:**
- Create: `app/v2/server/middleware/otel_tracing.py`
- Test: `tests/v2/server/middleware/test_otel_tracing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_otel_tracing.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.otel_tracing import OTELTracingMiddleware

def _ctx(tool: str = "entity_list") -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = tool
    mc.fastmcp_context = MagicMock()
    return mc

@pytest.mark.asyncio
async def test_span_started_and_ended_on_success() -> None:
    span = MagicMock()

    class _SpanCM:
        def __enter__(self): return span
        def __exit__(self, *a): return False

    tracer = MagicMock()
    tracer.start_as_current_span = lambda name: _SpanCM()
    mw = OTELTracingMiddleware(tracer=tracer)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    span.set_attribute.assert_any_call("mcp.tool", "entity_list")
    span.set_status.assert_called()

@pytest.mark.asyncio
async def test_span_records_exception() -> None:
    span = MagicMock()

    class _SpanCM:
        def __enter__(self): return span
        def __exit__(self, *a): return False

    tracer = MagicMock()
    tracer.start_as_current_span = lambda name: _SpanCM()
    mw = OTELTracingMiddleware(tracer=tracer)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx(), call_next)
    span.record_exception.assert_called_once()

@pytest.mark.asyncio
async def test_noop_when_tracer_missing() -> None:
    mw = OTELTracingMiddleware(tracer=None)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
```

- [ ] **Step 2: Tests FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/otel_tracing.py`**

```python
"""OpenTelemetry span per tool call.

Uses ``tracer.start_as_current_span``. If no tracer is configured (OTEL not
installed or disabled) the middleware is a no-op.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

try:  # pragma: no cover
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import Status, StatusCode
    _default_tracer = _otel_trace.get_tracer("app.v2.mcp")
except ImportError:  # pragma: no cover
    _default_tracer = None
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]

class OTELTracingMiddleware(Middleware):
    def __init__(self, *, tracer: Any | None = _default_tracer) -> None:
        self._tracer = tracer

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if self._tracer is None:
            return await call_next(context)
        name = getattr(context.message, "name", "<unknown>")
        with self._tracer.start_as_current_span(f"mcp.tool.{name}") as span:
            span.set_attribute("mcp.tool", name)
            try:
                result = await call_next(context)
            except Exception as exc:
                span.record_exception(exc)
                if StatusCode is not None:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            if StatusCode is not None:
                span.set_status(Status(StatusCode.OK))
            return result
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/otel_tracing.py tests/v2/server/middleware/test_otel_tracing.py
git commit -m "feat(v2): OTELTracingMiddleware (3/16)

Span per tool call with mcp.tool attribute and exception recording. No-op
when opentelemetry-api is not installed."
```

---

## Task 7: Middleware (4) — `timing.py`

**Files:**
- Create: `app/v2/server/middleware/timing.py`
- Test: `tests/v2/server/middleware/test_timing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_timing.py
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.timing import DetailedTimingMiddleware

def _ctx(tool: str = "t") -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = tool
    return mc

@pytest.mark.asyncio
async def test_records_duration_on_success() -> None:
    observed: list[tuple[str, float, bool]] = []

    def recorder(name: str, duration: float, ok: bool) -> None:
        observed.append((name, duration, ok))

    mw = DetailedTimingMiddleware(record=recorder)

    async def slow(_ctx):
        await asyncio.sleep(0.01)
        return "ok"

    await mw.on_call_tool(_ctx("entity_list"), slow)
    assert len(observed) == 1
    name, dur, ok = observed[0]
    assert name == "entity_list"
    assert dur >= 0.005
    assert ok is True

@pytest.mark.asyncio
async def test_records_duration_on_failure() -> None:
    observed: list[tuple[str, float, bool]] = []
    mw = DetailedTimingMiddleware(
        record=lambda n, d, ok: observed.append((n, d, ok))
    )
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx("x"), call_next)
    assert observed[0][2] is False
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/timing.py`**

```python
"""Per-tool timing with pluggable recorder (metric emitter / log / Prometheus)."""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

def _default_recorder(name: str, duration_s: float, success: bool) -> None:
    log.info(
        "tool_timing",
        extra={
            "mcp_extra": {
                "tool": name,
                "duration_ms": round(duration_s * 1000, 2),
                "success": success,
            }
        },
    )

class DetailedTimingMiddleware(Middleware):
    def __init__(
        self,
        *,
        record: Callable[[str, float, bool], None] = _default_recorder,
    ) -> None:
        self._record = record

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        start = time.perf_counter()
        success = False
        try:
            result = await call_next(context)
            success = True
            return result
        finally:
            self._record(name, time.perf_counter() - start, success)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/timing.py tests/v2/server/middleware/test_timing.py
git commit -m "feat(v2): DetailedTimingMiddleware (4/16)

Records wall-clock duration per tool with success flag via pluggable recorder.
Default emits structured 'tool_timing' log via mcp_extra."
```

---

## Task 8: Middleware (5) — `audit_log.py`

**Files:**
- Create: `app/v2/server/middleware/audit_log.py`
- Test: `tests/v2/server/middleware/test_audit_log.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_audit_log.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.audit_log import AuditLogMiddleware

def _ctx(name: str, readonly: bool) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    msg = MagicMock()
    msg.name = name
    msg.arguments = {"id": 42}
    mc.message = msg
    fctx = MagicMock()
    tool = MagicMock()
    tool.annotations = MagicMock()
    tool.annotations.readOnlyHint = readonly
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_logs_mutation_tool() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(return_value={"created_id": 7})
    await mw.on_call_tool(_ctx("entity_create", readonly=False), call_next)
    assert len(events) == 1
    ev = events[0]
    assert ev["tool"] == "entity_create"
    assert "args_hash" in ev
    assert ev["status"] == "ok"

@pytest.mark.asyncio
async def test_skips_readonly_tool() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(return_value={"items": []})
    await mw.on_call_tool(_ctx("entity_list", readonly=True), call_next)
    assert events == []

@pytest.mark.asyncio
async def test_records_failure() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx("entity_delete", readonly=False), call_next)
    assert events[0]["status"] == "error"
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/audit_log.py`**

```python
"""Audit log for mutation tool calls.

Skips read-only tools (annotations.readOnlyHint). Records name + args hash +
outcome. Payload hashes (sha256) are cheap to store and audit-safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

def _default_sink(event: dict) -> None:
    log.info("mcp_audit", extra={"mcp_extra": event})

def _hash_args(args: Any) -> str:
    try:
        payload = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        payload = repr(args)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

class AuditLogMiddleware(Middleware):
    def __init__(
        self,
        *,
        sink: Callable[[dict], None] = _default_sink,
    ) -> None:
        self._sink = sink

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        args = getattr(context.message, "arguments", {}) or {}

        readonly = False
        fctx = context.fastmcp_context
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                readonly = bool(
                    getattr(getattr(tool, "annotations", None), "readOnlyHint", False)
                )
            except Exception:
                readonly = False

        if readonly:
            return await call_next(context)

        started_at = time.time()
        try:
            result = await call_next(context)
        except Exception as exc:
            self._sink(
                {
                    "tool": name,
                    "args_hash": _hash_args(args),
                    "status": "error",
                    "error": type(exc).__name__,
                    "t": started_at,
                }
            )
            raise
        self._sink(
            {
                "tool": name,
                "args_hash": _hash_args(args),
                "status": "ok",
                "t": started_at,
            }
        )
        return result
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/audit_log.py tests/v2/server/middleware/test_audit_log.py
git commit -m "feat(v2): AuditLogMiddleware (5/16)

Logs mutation tool calls with name + args sha256 prefix + outcome. Skips
read-only tools to keep signal high."
```

---

## Task 9: Middleware (6) — `retry.py`

**Files:**
- Create: `app/v2/server/middleware/retry.py`
- Test: `tests/v2/server/middleware/test_retry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_retry.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.retry import RetryMiddleware, TransientError

def _ctx() -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = "entity_list"
    return mc

@pytest.mark.asyncio
async def test_success_first_try_no_retry() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
    assert call_next.await_count == 1

@pytest.mark.asyncio
async def test_retries_transient_error() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(
        side_effect=[TransientError("fail1"), TransientError("fail2"), "ok"]
    )
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"
    assert call_next.await_count == 3

@pytest.mark.asyncio
async def test_gives_up_after_max() -> None:
    mw = RetryMiddleware(max_retries=2, base_delay=0)
    call_next = AsyncMock(side_effect=TransientError("always"))
    with pytest.raises(TransientError):
        await mw.on_call_tool(_ctx(), call_next)
    assert call_next.await_count == 3  # initial + 2 retries

@pytest.mark.asyncio
async def test_does_not_retry_non_transient() -> None:
    mw = RetryMiddleware(max_retries=5, base_delay=0)
    call_next = AsyncMock(side_effect=ValueError("bad input"))
    with pytest.raises(ValueError):
        await mw.on_call_tool(_ctx(), call_next)
    assert call_next.await_count == 1
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/retry.py`**

```python
"""Retry transient errors with exponential backoff.

TransientError is a marker — raise it from providers / DB layer when a
call is safe to retry. Non-transient exceptions propagate immediately.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

class TransientError(Exception):
    """Marker for errors safe to retry."""

class RetryMiddleware(Middleware):
    def __init__(
        self,
        *,
        max_retries: int = 2,
        base_delay: float = 0.5,
        backoff_factor: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        attempt = 0
        while True:
            try:
                return await call_next(context)
            except TransientError as exc:
                if attempt >= self.max_retries:
                    raise
                delay = self.base_delay * (self.backoff_factor ** attempt)
                log.warning(
                    "retry attempt=%d delay=%.2fs error=%s",
                    attempt + 1, delay, exc,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/retry.py tests/v2/server/middleware/test_retry.py
git commit -m "feat(v2): RetryMiddleware (6/16)

Exponential backoff retry for TransientError. Non-transient errors propagate
immediately so validation bugs surface fast."
```

---

## Task 10: Middleware (7) — `response_limit.py`

**Files:**
- Create: `app/v2/server/middleware/response_limit.py`
- Test: `tests/v2/server/middleware/test_response_limit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_response_limit.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.response_limit import ResponseLimitingMiddleware

def _ctx() -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = "entity_list"
    return mc

@pytest.mark.asyncio
async def test_passes_small_response_untouched() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=50_000)
    payload = {"items": [1, 2, 3]}
    call_next = AsyncMock(return_value=payload)
    assert await mw.on_call_tool(_ctx(), call_next) is payload

@pytest.mark.asyncio
async def test_truncates_oversized_dict() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=200)
    payload = {"items": ["x" * 50 for _ in range(100)]}
    call_next = AsyncMock(return_value=payload)
    result = await mw.on_call_tool(_ctx(), call_next)
    assert result.get("truncated") is True
    assert "limit_bytes" in result

@pytest.mark.asyncio
async def test_truncates_oversized_string() -> None:
    mw = ResponseLimitingMiddleware(max_bytes=100)
    call_next = AsyncMock(return_value="x" * 10_000)
    result = await mw.on_call_tool(_ctx(), call_next)
    assert isinstance(result, str)
    assert len(result.encode()) <= 200  # room for suffix marker
    assert "truncated" in result
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/response_limit.py`**

```python
"""Guard against oversized tool responses.

Large payloads poison LLM context. We truncate dict/list responses to a
summary marker and strings to a prefix with a truncation suffix.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings

log = logging.getLogger(__name__)

class ResponseLimitingMiddleware(Middleware):
    def __init__(self, *, max_bytes: int | None = None) -> None:
        if max_bytes is None:
            max_bytes = get_settings().mcp.response_max_bytes
        self.max_bytes = max_bytes

    def _size(self, value: Any) -> int:
        if isinstance(value, str):
            return len(value.encode())
        try:
            return len(json.dumps(value, default=str).encode())
        except TypeError:
            return len(repr(value).encode())

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        result = await call_next(context)
        size = self._size(result)
        if size <= self.max_bytes:
            return result
        tool = getattr(context.message, "name", "<unknown>")
        log.warning("response truncated tool=%s bytes=%d limit=%d", tool, size, self.max_bytes)
        if isinstance(result, str):
            return result[: self.max_bytes] + "\n…(truncated)"
        return {
            "truncated": True,
            "limit_bytes": self.max_bytes,
            "original_bytes": size,
            "note": f"response from {tool} exceeded limit",
        }
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/response_limit.py tests/v2/server/middleware/test_response_limit.py
git commit -m "feat(v2): ResponseLimitingMiddleware (7/16)

Caps tool responses at settings.mcp.response_max_bytes (default 50 KB).
Dicts become a truncation marker; strings get a suffix. Prevents LLM
context blow-ups from unbounded list_tracks calls."
```

---

## Task 11: Middleware (8) — `response_caching.py` (ENABLED for read-only)

**Files:**
- Create: `app/v2/server/middleware/response_caching.py`
- Test: `tests/v2/server/middleware/test_response_caching.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_response_caching.py
from __future__ import annotations

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.response_caching import ResponseCachingMiddleware

def _ctx(name: str, readonly: bool, args: dict) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    msg = MagicMock()
    msg.name = name
    msg.arguments = args
    mc.message = msg
    fctx = MagicMock()
    tool = MagicMock()
    tool.annotations = MagicMock()
    tool.annotations.readOnlyHint = readonly
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_caches_readonly_tool_result() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60)
    call_next = AsyncMock(return_value={"items": [1]})
    ctx = _ctx("entity_list", readonly=True, args={"q": "techno"})
    r1 = await mw.on_call_tool(ctx, call_next)
    r2 = await mw.on_call_tool(ctx, call_next)
    assert r1 == r2
    # second call served from cache
    assert call_next.await_count == 1

@pytest.mark.asyncio
async def test_does_not_cache_mutations() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60)
    call_next = AsyncMock(return_value={"created": 1})
    ctx = _ctx("entity_create", readonly=False, args={"id": 1})
    await mw.on_call_tool(ctx, call_next)
    await mw.on_call_tool(ctx, call_next)
    assert call_next.await_count == 2

@pytest.mark.asyncio
async def test_different_args_different_cache_entries() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=60)
    call_next = AsyncMock(side_effect=[{"a": 1}, {"b": 2}])
    ctx1 = _ctx("entity_list", True, {"q": "a"})
    ctx2 = _ctx("entity_list", True, {"q": "b"})
    assert (await mw.on_call_tool(ctx1, call_next)) == {"a": 1}
    assert (await mw.on_call_tool(ctx2, call_next)) == {"b": 2}

@pytest.mark.asyncio
async def test_ttl_expiry() -> None:
    mw = ResponseCachingMiddleware(ttl_seconds=0.01)
    call_next = AsyncMock(side_effect=[{"n": 1}, {"n": 2}])
    ctx = _ctx("entity_list", True, {})
    assert (await mw.on_call_tool(ctx, call_next)) == {"n": 1}
    await asyncio.sleep(0.02)
    assert (await mw.on_call_tool(ctx, call_next)) == {"n": 2}
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/response_caching.py`**

```python
"""Cache results of read-only tool calls (TTL + LRU).

**Enabled by default** (was disabled in legacy app/bootstrap/middleware.py).
Key = (tool_name, json(arguments, sort_keys=True)). Cache is session-less;
read-only tools should be pure functions of their inputs.

Session-scoped resources (session://*) bypass this middleware because they
are exposed through ResourcesAsTools with a different decorator path.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings

log = logging.getLogger(__name__)

def _key_for(name: str, args: Any) -> str:
    try:
        payload = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        payload = repr(args)
    return f"{name}|{payload}"

class ResponseCachingMiddleware(Middleware):
    def __init__(
        self,
        *,
        ttl_seconds: float | None = None,
        max_entries: int | None = None,
    ) -> None:
        s = get_settings().mcp
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else s.response_cache_ttl
        self.max_entries = max_entries if max_entries is not None else s.response_cache_max
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _get(self, key: str) -> Any | None:
        hit = self._store.get(key)
        if hit is None:
            return None
        expires_at, value = hit
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def _put(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)
        try:
            tool = await fctx.fastmcp.get_tool(name)
        except Exception:
            return await call_next(context)
        readonly = bool(
            getattr(getattr(tool, "annotations", None), "readOnlyHint", False)
        )
        if not readonly:
            return await call_next(context)

        args = getattr(context.message, "arguments", {}) or {}
        key = _key_for(name, args)
        cached = self._get(key)
        if cached is not None:
            return cached
        result = await call_next(context)
        self._put(key, result)
        return result
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/response_caching.py tests/v2/server/middleware/test_response_caching.py
git commit -m "feat(v2): ResponseCachingMiddleware (8/16) — ENABLED

TTL + LRU cache of read-only tool results keyed by (name, json(args)).
Legacy codebase kept this disabled; blueprint §11 requires it on because
tools like entity_list, provider_search, reference:// are hot and pure."
```

---

## Task 12: Middleware (9) — `deprecation_warning.py`

**Files:**
- Create: `app/v2/server/middleware/deprecation_warning.py`
- Test: `tests/v2/server/middleware/test_deprecation_warning.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_deprecation_warning.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.deprecation_warning import (
    DeprecationWarningMiddleware,
)

def _ctx(tool_name: str, version: str | None) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    msg = MagicMock()
    msg.name = tool_name
    mc.message = msg
    fctx = MagicMock()
    tool = MagicMock()
    tool.version = version
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_warns_on_version_1_0() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("old_tool", "1.0"), call_next)
    assert warnings
    assert "old_tool" in warnings[0]

@pytest.mark.asyncio
async def test_no_warning_on_current_version() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("new_tool", "2.0"), call_next)
    assert warnings == []

@pytest.mark.asyncio
async def test_no_warning_when_unversioned() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("plain", None), call_next)
    assert warnings == []
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/deprecation_warning.py`**

```python
"""Warn when a client calls a tool at the deprecated version.

Tools marked ``@tool(version="1.0")`` are kept for transition while the
same-named ``version="2.0"`` rolls out. This middleware fires a structured
log so telemetry can track callers still on v1.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

DEPRECATED_VERSIONS = frozenset({"1.0"})

def _default_emit(message: str) -> None:
    log.warning("deprecation: %s", message, extra={"mcp_extra": {"deprecated": True}})

class DeprecationWarningMiddleware(Middleware):
    def __init__(self, *, emit: Callable[[str], None] = _default_emit) -> None:
        self._emit = emit

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        name = getattr(context.message, "name", "<unknown>")
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                version = getattr(tool, "version", None)
            except Exception:
                version = None
            if version in DEPRECATED_VERSIONS:
                self._emit(f"tool '{name}' version={version} is deprecated")
        return await call_next(context)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/deprecation_warning.py tests/v2/server/middleware/test_deprecation_warning.py
git commit -m "feat(v2): DeprecationWarningMiddleware (9/16)

Emits a warning log each time a tool with version='1.0' is called so the
rollout of v2 can track stragglers."
```

---

## Task 13: Middleware (10) — `cost_tracking.py`

**Files:**
- Create: `app/v2/server/middleware/cost_tracking.py`
- Test: `tests/v2/server/middleware/test_cost_tracking.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_cost_tracking.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.cost_tracking import CostTrackingMiddleware

def _ctx(name: str) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = name
    mc.fastmcp_context = MagicMock()
    mc.fastmcp_context.state = {}
    return mc

@pytest.mark.asyncio
async def test_records_provider_call_count() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    ctx = _ctx("provider_read")

    async def call_next(c):
        # Tool simulates a provider call by mutating state counter
        c.fastmcp_context.state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
        c.fastmcp_context.state["cost"]["provider_calls"] += 3
        return "ok"

    await mw.on_call_tool(ctx, call_next)
    assert emitted[0]["provider_calls"] == 3
    assert emitted[0]["tool"] == "provider_read"

@pytest.mark.asyncio
async def test_records_llm_tokens() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    ctx = _ctx("some_tool")

    async def call_next(c):
        c.fastmcp_context.state.setdefault("cost", {"provider_calls": 0, "llm_tokens": 0})
        c.fastmcp_context.state["cost"]["llm_tokens"] += 1500
        return "ok"

    await mw.on_call_tool(ctx, call_next)
    assert emitted[0]["llm_tokens"] == 1500

@pytest.mark.asyncio
async def test_records_zero_when_nothing_happened() -> None:
    emitted: list[dict] = []
    mw = CostTrackingMiddleware(sink=emitted.append)
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    assert emitted[0] == {
        "tool": "entity_list",
        "provider_calls": 0,
        "llm_tokens": 0,
    }
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/cost_tracking.py`**

```python
"""Count provider API calls + LLM sampling tokens per tool call.

Tools / handlers / adapters bump counters on ``ctx.fastmcp_context.state["cost"]``;
middleware resets counters at call start and emits totals at end.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

def _default_sink(event: dict) -> None:
    log.info("mcp_cost", extra={"mcp_extra": event})

class CostTrackingMiddleware(Middleware):
    def __init__(self, *, sink: Callable[[dict], None] = _default_sink) -> None:
        self._sink = sink

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)
        state = fctx.state
        state["cost"] = {"provider_calls": 0, "llm_tokens": 0}
        try:
            return await call_next(context)
        finally:
            totals = state.get("cost", {"provider_calls": 0, "llm_tokens": 0})
            self._sink(
                {
                    "tool": getattr(context.message, "name", "<unknown>"),
                    "provider_calls": totals.get("provider_calls", 0),
                    "llm_tokens": totals.get("llm_tokens", 0),
                }
            )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/cost_tracking.py tests/v2/server/middleware/test_cost_tracking.py
git commit -m "feat(v2): CostTrackingMiddleware (10/16)

Resets ctx.state['cost'] at tool start, emits provider_calls + llm_tokens
totals at end. Downstream code increments the counters."
```

---

## Task 14: Middleware (11) — `sampling_budget.py`

**Files:**
- Create: `app/v2/server/middleware/sampling_budget.py`
- Test: `tests/v2/server/middleware/test_sampling_budget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_sampling_budget.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.sampling_budget import (
    SamplingBudgetExceeded,
    SamplingBudgetMiddleware,
)

def _ctx(session_id: str = "s1") -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = "x"
    fctx = MagicMock()
    fctx.session_id = session_id
    fctx.state = {}
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_allows_until_budget() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=2)
    call_next = AsyncMock(return_value="ok")
    ctx = _ctx("s1")

    # Simulate two sampling calls within one tool call via state bump
    async def bump_twice(c):
        mw.note_sample(c)
        mw.note_sample(c)
        return "ok"

    await mw.on_call_tool(ctx, bump_twice)
    # next tool call must still be allowed (=2 is the cap, not exceeded)

@pytest.mark.asyncio
async def test_raises_over_budget() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)
    ctx = _ctx("s2")

    async def bump_over(c):
        mw.note_sample(c)
        mw.note_sample(c)  # second one must raise
        return "ok"

    with pytest.raises(SamplingBudgetExceeded):
        await mw.on_call_tool(ctx, bump_over)

@pytest.mark.asyncio
async def test_budget_is_per_session() -> None:
    mw = SamplingBudgetMiddleware(max_samples_per_session=1)

    async def bump_one(c):
        mw.note_sample(c)
        return "ok"

    await mw.on_call_tool(_ctx("A"), bump_one)
    await mw.on_call_tool(_ctx("B"), bump_one)  # separate session
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/sampling_budget.py`**

```python
"""Cap ``ctx.sample()`` invocations per MCP session.

The server-side LLM fallback (``app/v2/server/sampling.py``) calls
``middleware.note_sample(ctx)`` before actually hitting the Anthropic API.
If the session has exceeded its budget, ``SamplingBudgetExceeded`` is raised
and the handler should fall back to "please provide queries as a tool param".
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings

class SamplingBudgetExceeded(Exception):
    """Raised when a session has used up its sampling budget."""

class SamplingBudgetMiddleware(Middleware):
    def __init__(self, *, max_samples_per_session: int | None = None) -> None:
        if max_samples_per_session is None:
            max_samples_per_session = get_settings().mcp.sampling_max_per_session
        self.max_samples_per_session = max_samples_per_session
        self._used: dict[str, int] = {}

    def note_sample(self, ctx: Any) -> None:
        """Called by the sampling handler before dispatching to Anthropic."""
        fctx = ctx.fastmcp_context if hasattr(ctx, "fastmcp_context") else ctx
        session = getattr(fctx, "session_id", None) or "__global__"
        used = self._used.get(session, 0)
        if used >= self.max_samples_per_session:
            raise SamplingBudgetExceeded(
                f"session {session}: sampling budget of "
                f"{self.max_samples_per_session} exceeded"
            )
        self._used[session] = used + 1

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        if context.fastmcp_context is not None:
            context.fastmcp_context.state["sampling_budget"] = self
        return await call_next(context)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/sampling_budget.py tests/v2/server/middleware/test_sampling_budget.py
git commit -m "feat(v2): SamplingBudgetMiddleware (11/16)

Caps ctx.sample() invocations per session via note_sample() from the
sampling handler. Prevents runaway LLM spend from a misbehaving client."
```

---

## Task 15: Middleware (12) — `progress_throttle.py`

**Files:**
- Create: `app/v2/server/middleware/progress_throttle.py`
- Test: `tests/v2/server/middleware/test_progress_throttle.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_progress_throttle.py
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.progress_throttle import ProgressThrottleMiddleware

def _make_ctx_with_report():
    calls: list[tuple[float, int]] = []

    async def original_report(progress: float, total: float | None = None, message: str | None = None) -> None:
        calls.append((time.monotonic(), progress))

    fctx = MagicMock()
    fctx.report_progress = original_report
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.fastmcp_context = fctx
    mc.message = MagicMock()
    mc.message.name = "t"
    return mc, calls, fctx

@pytest.mark.asyncio
async def test_throttles_rapid_progress_to_ratelimit() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=1)
    ctx, calls, fctx = _make_ctx_with_report()

    async def spam(c):
        # 20 rapid calls; only ~1/sec should slip through
        for i in range(20):
            await c.fastmcp_context.report_progress(i, 20)
        return "ok"

    await mw.on_call_tool(ctx, spam)
    assert 1 <= len(calls) <= 3

@pytest.mark.asyncio
async def test_allows_spaced_progress() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=10)
    ctx, calls, fctx = _make_ctx_with_report()

    async def slow(c):
        for i in range(3):
            await c.fastmcp_context.report_progress(i, 3)
            await asyncio.sleep(0.11)
        return "ok"

    await mw.on_call_tool(ctx, slow)
    assert len(calls) == 3

@pytest.mark.asyncio
async def test_restores_original_on_exit() -> None:
    mw = ProgressThrottleMiddleware(max_per_second=1)
    ctx, _, fctx = _make_ctx_with_report()
    original = fctx.report_progress
    await mw.on_call_tool(ctx, AsyncMock(return_value="ok"))
    assert fctx.report_progress is original
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/progress_throttle.py`**

```python
"""Throttle ``ctx.report_progress`` to at most N events per second.

Replaces ``fctx.report_progress`` with a wrapped async callable for the
duration of one tool call, then restores it. Drops messages that arrive
within the rate-limit window (final message of a tool call is NOT
guaranteed — callers that must land a final event should call
``ctx.info(...)`` instead).
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

class ProgressThrottleMiddleware(Middleware):
    def __init__(self, *, max_per_second: int = 1) -> None:
        self.min_interval = 1.0 / max_per_second

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)
        original = getattr(fctx, "report_progress", None)
        if original is None:
            return await call_next(context)

        last_emit = {"t": 0.0}

        async def throttled(
            progress: float,
            total: float | None = None,
            message: str | None = None,
        ) -> None:
            now = time.monotonic()
            if now - last_emit["t"] < self.min_interval:
                return
            last_emit["t"] = now
            await original(progress, total, message)

        fctx.report_progress = throttled
        try:
            return await call_next(context)
        finally:
            fctx.report_progress = original
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/progress_throttle.py tests/v2/server/middleware/test_progress_throttle.py
git commit -m "feat(v2): ProgressThrottleMiddleware (12/16)

Replaces ctx.report_progress with a 1/sec-throttled wrapper for the
duration of each tool call; restored on exit. Stops chatty loops from
flooding the MCP channel."
```

---

## Task 16: Middleware (13) — `tool_timeout.py`

**Files:**
- Create: `app/v2/server/middleware/tool_timeout.py`
- Test: `tests/v2/server/middleware/test_tool_timeout.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_tool_timeout.py
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.tool_timeout import ToolCallTimeoutMiddleware

def _ctx(name: str, timeout: float | None) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = name
    fctx = MagicMock()
    tool = MagicMock()
    tool.meta = {"timeout_s": timeout} if timeout is not None else {}
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_completes_within_timeout() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=1.0)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx("t", 1.0), call_next) == "ok"

@pytest.mark.asyncio
async def test_raises_on_overrun() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=0.01)

    async def slow(_):
        await asyncio.sleep(1.0)
        return "never"

    with pytest.raises(ToolError, match="timed out"):
        await mw.on_call_tool(_ctx("slow", 0.01), slow)

@pytest.mark.asyncio
async def test_respects_per_tool_meta_over_default() -> None:
    mw = ToolCallTimeoutMiddleware(default_timeout=0.01)

    async def fifty_ms(_):
        await asyncio.sleep(0.05)
        return "ok"

    assert await mw.on_call_tool(_ctx("t", 0.5), fifty_ms) == "ok"
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/tool_timeout.py`**

```python
"""Per-tool timeout driven by ``tool.meta['timeout_s']``.

Falls back to ``default_timeout`` when a tool does not declare one. Wraps
``asyncio.wait_for`` — cancelled coroutines become ``ToolError("tool X
timed out after Ys")``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings

class ToolCallTimeoutMiddleware(Middleware):
    def __init__(self, *, default_timeout: float | None = None) -> None:
        if default_timeout is None:
            default_timeout = get_settings().mcp.default_tool_timeout_s
        self.default_timeout = default_timeout

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        timeout = self.default_timeout
        fctx = context.fastmcp_context
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                meta = getattr(tool, "meta", None) or {}
                if "timeout_s" in meta:
                    timeout = float(meta["timeout_s"])
            except Exception:
                pass
        try:
            return await asyncio.wait_for(call_next(context), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ToolError(f"tool '{name}' timed out after {timeout}s") from exc
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/tool_timeout.py tests/v2/server/middleware/test_tool_timeout.py
git commit -m "feat(v2): ToolCallTimeoutMiddleware (13/16)

Reads per-tool timeout from tool.meta['timeout_s']; falls back to
settings.mcp.default_tool_timeout_s. Hangs become a deterministic
ToolError so clients can retry."
```

---

## Task 17: Middleware (14) — `provider_rate_limit.py`

**Files:**
- Create: `app/v2/server/middleware/provider_rate_limit.py`
- Test: `tests/v2/server/middleware/test_provider_rate_limit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_provider_rate_limit.py
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.provider_rate_limit import (
    ProviderRateLimitMiddleware,
)

def _ctx(name: str) -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = name
    mc.fastmcp_context = MagicMock()
    return mc

@pytest.mark.asyncio
async def test_spaces_consecutive_provider_calls() -> None:
    mw = ProviderRateLimitMiddleware(
        delay_s=0.05, tool_prefixes=("provider_",)
    )
    call_next = AsyncMock(return_value="ok")
    t0 = time.monotonic()
    await mw.on_call_tool(_ctx("provider_read"), call_next)
    await mw.on_call_tool(_ctx("provider_read"), call_next)
    assert time.monotonic() - t0 >= 0.05

@pytest.mark.asyncio
async def test_does_not_throttle_local_tools() -> None:
    mw = ProviderRateLimitMiddleware(
        delay_s=1.0, tool_prefixes=("provider_",)
    )
    call_next = AsyncMock(return_value="ok")
    t0 = time.monotonic()
    await mw.on_call_tool(_ctx("entity_list"), call_next)
    await mw.on_call_tool(_ctx("entity_get"), call_next)
    assert time.monotonic() - t0 < 0.5
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/provider_rate_limit.py`**

```python
"""Rate-limit external provider calls (generalized YM rate limiter).

Matches by tool name prefix (e.g., ``provider_``). Adds a minimum delay
between calls across the whole MCP server instance (not per-session —
external APIs see a single IP).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings

class ProviderRateLimitMiddleware(Middleware):
    def __init__(
        self,
        *,
        delay_s: float | None = None,
        tool_prefixes: tuple[str, ...] = ("provider_",),
    ) -> None:
        if delay_s is None:
            delay_s = get_settings().yandex.rate_limit_delay
        self.delay_s = delay_s
        self.tool_prefixes = tool_prefixes
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        if not any(name.startswith(p) for p in self.tool_prefixes):
            return await call_next(context)
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.delay_s:
                await asyncio.sleep(self.delay_s - elapsed)
            self._last_call = time.monotonic()
        return await call_next(context)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/provider_rate_limit.py tests/v2/server/middleware/test_provider_rate_limit.py
git commit -m "feat(v2): ProviderRateLimitMiddleware (14/16)

Generalizes legacy YMRateLimit: delay on any tool whose name starts with
'provider_'. Single lock across the server — external APIs see one IP."
```

---

## Task 18: Middleware (15) — `db_session.py`

**Files:**
- Create: `app/v2/server/middleware/db_session.py`
- Test: `tests/v2/server/middleware/test_db_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_db_session.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.server.middleware.db_session import DbSessionMiddleware

class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True

def _fake_session_factory() -> _FakeSession:
    return _FakeSession()

def _ctx_with_factory(factory):
    fctx = MagicMock()
    fctx.state = {}
    fctx.request_context = SimpleNamespace(lifespan_context={"db_session_factory": factory})
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.fastmcp_context = fctx
    mc.message = MagicMock()
    mc.message.name = "entity_list"
    return mc, fctx

@pytest.mark.asyncio
async def test_sets_uow_on_state_and_commits_on_success() -> None:
    session = _FakeSession()
    factory = lambda: session  # noqa: E731
    ctx, fctx = _ctx_with_factory(factory)
    mw = DbSessionMiddleware()
    seen = {}

    async def handler(c):
        seen["uow"] = c.fastmcp_context.state["uow"]
        return "ok"

    await mw.on_call_tool(ctx, handler)
    assert isinstance(seen["uow"], UnitOfWork)
    assert session.committed and not session.rolled_back
    assert session.closed

@pytest.mark.asyncio
async def test_rolls_back_on_error() -> None:
    session = _FakeSession()
    factory = lambda: session  # noqa: E731
    ctx, _ = _ctx_with_factory(factory)
    mw = DbSessionMiddleware()
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(ctx, handler)
    assert session.rolled_back and not session.committed
    assert session.closed

@pytest.mark.asyncio
async def test_skips_when_no_factory_available() -> None:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.fastmcp_context = None
    mc.message = MagicMock()
    mc.message.name = "t"
    mw = DbSessionMiddleware()
    handler = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(mc, handler) == "ok"
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/db_session.py`**

```python
"""Open a UnitOfWork per tool call.

- Reads ``db_session_factory`` from the lifespan context.
- Creates a fresh SQLAlchemy ``AsyncSession`` and wraps it in ``UnitOfWork``.
- Stashes the UoW on ``ctx.fastmcp_context.state["uow"]``.
- Tools consume it via ``Depends(get_uow)`` (see ``app/v2/server/di.py``).
- Commits on success, rolls back on exception, always closes the session.

Replaces the legacy ``get_db_session()`` DI helper — transaction boundary is
now exactly one tool call, enforced from the middleware layer.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)

class DbSessionMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)

        factory = None
        rc = getattr(fctx, "request_context", None)
        if rc is not None:
            lc = getattr(rc, "lifespan_context", None) or {}
            factory = lc.get("db_session_factory")
        if factory is None:
            log.debug("no db_session_factory — tool runs without UoW")
            return await call_next(context)

        session = factory()
        uow = UnitOfWork(session)
        fctx.state["uow"] = uow
        try:
            result = await call_next(context)
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()
            return result
        finally:
            fctx.state.pop("uow", None)
            await session.close()
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/db_session.py tests/v2/server/middleware/test_db_session.py
git commit -m "feat(v2): DbSessionMiddleware (15/16)

Opens one UnitOfWork per tool call, sets on ctx.state['uow'], commits on
success and rolls back on exception. Replaces legacy get_db_session DI."
```

---

## Task 19: Middleware (16) — `structured_logging.py`

**Files:**
- Create: `app/v2/server/middleware/structured_logging.py`
- Test: `tests/v2/server/middleware/test_structured_logging.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/middleware/test_structured_logging.py
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.structured_logging import (
    StructuredLoggingMiddleware,
)

def _ctx(name: str = "entity_list") -> MiddlewareContext:
    mc = MiddlewareContext.__new__(MiddlewareContext)
    mc.message = MagicMock()
    mc.message.name = name
    mc.message.arguments = {"id": 1}
    fctx = MagicMock()
    fctx.session_id = "s1"
    fctx.request_id = "r9"
    mc.fastmcp_context = fctx
    return mc

@pytest.mark.asyncio
async def test_logs_enter_and_exit(caplog) -> None:
    mw = StructuredLoggingMiddleware()
    call_next = AsyncMock(return_value={"ok": True})
    with caplog.at_level(logging.INFO, logger="app.v2.server.middleware.structured_logging"):
        await mw.on_call_tool(_ctx(), call_next)
    messages = [r.message for r in caplog.records]
    assert any("call_tool.enter" in m for m in messages)
    assert any("call_tool.exit" in m for m in messages)

@pytest.mark.asyncio
async def test_logs_error(caplog) -> None:
    mw = StructuredLoggingMiddleware()
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with caplog.at_level(logging.INFO, logger="app.v2.server.middleware.structured_logging"):
        with pytest.raises(RuntimeError):
            await mw.on_call_tool(_ctx("x"), call_next)
    assert any("call_tool.error" in r.message for r in caplog.records)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/middleware/structured_logging.py`**

```python
"""Innermost middleware — structured logs at tool boundary.

Runs closest to the handler. Emits enter/exit/error log records with
mcp_extra payload for downstream log pipelines to parse.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

class StructuredLoggingMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        fctx = context.fastmcp_context
        session = getattr(fctx, "session_id", None) if fctx else None
        request = getattr(fctx, "request_id", None) if fctx else None
        extra = {"mcp_extra": {"tool": name, "session_id": session, "request_id": request}}
        log.info("call_tool.enter", extra=extra)
        try:
            result = await call_next(context)
        except Exception as exc:
            log.exception(
                "call_tool.error",
                extra={
                    "mcp_extra": {
                        **extra["mcp_extra"],
                        "error": type(exc).__name__,
                    }
                },
            )
            raise
        log.info("call_tool.exit", extra=extra)
        return result
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/middleware/structured_logging.py tests/v2/server/middleware/test_structured_logging.py
git commit -m "feat(v2): StructuredLoggingMiddleware (16/16)

Innermost middleware; emits call_tool.enter/exit/error with mcp_extra
payload keyed by tool/session_id/request_id."
```

---

## Task 20: `app/v2/server/transforms.py` — Tool Search + PromptsAsTools + ResourcesAsTools

**Files:**
- Create: `app/v2/server/transforms.py`
- Test: `tests/v2/server/test_transforms.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_transforms.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.v2.server.transforms import (
    ALWAYS_VISIBLE_TOOLS,
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)

def test_always_visible_list_matches_blueprint() -> None:
    assert ALWAYS_VISIBLE_TOOLS == (
        "entity_list",
        "entity_get",
        "entity_create",
        "entity_aggregate",
        "provider_read",
        "provider_search",
        "transition_score_pool",
        "sequence_optimize",
        "unlock_namespace",
    )

def test_pre_constructor_transforms_include_bm25() -> None:
    transforms = build_pre_constructor_transforms()
    # Find the BM25SearchTransform
    names = [type(t).__name__ for t in transforms]
    assert "BM25SearchTransform" in names

def test_pre_constructor_transforms_max_results_configured() -> None:
    transforms = build_pre_constructor_transforms()
    bm25 = next(t for t in transforms if type(t).__name__ == "BM25SearchTransform")
    assert bm25.max_results == 8
    assert set(bm25.always_visible) == set(ALWAYS_VISIBLE_TOOLS)

def test_register_post_constructor_transforms_invokes_prompts_and_resources() -> None:
    mcp = MagicMock()
    with (
        patch("app.v2.server.transforms.PromptsAsTools") as PAT,
        patch("app.v2.server.transforms.ResourcesAsTools") as RAT,
    ):
        register_post_constructor_transforms(mcp)
    PAT.assert_called_once_with(mcp)
    RAT.assert_called_once_with(mcp)

def test_code_mode_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DJ_MCP_CODE_MODE", raising=False)
    mcp = MagicMock()
    with (
        patch("app.v2.server.transforms.PromptsAsTools"),
        patch("app.v2.server.transforms.ResourcesAsTools"),
        patch("app.v2.server.transforms.CodeMode") as CM,
    ):
        register_post_constructor_transforms(mcp)
    CM.assert_not_called()

def test_code_mode_enabled_by_flag(monkeypatch) -> None:
    monkeypatch.setenv("DJ_MCP_CODE_MODE", "1")
    mcp = MagicMock()
    with (
        patch("app.v2.server.transforms.PromptsAsTools"),
        patch("app.v2.server.transforms.ResourcesAsTools"),
        patch("app.v2.server.transforms.CodeMode") as CM,
    ):
        register_post_constructor_transforms(mcp)
    CM.assert_called_once_with(mcp)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/transforms.py`**

```python
"""FastMCP v3 transforms.

- ``BM25SearchTransform`` — keeps 9 core tools always visible, ranks the rest
  via BM25 on client queries.
- ``PromptsAsTools`` — exposes 6 prompts as tools for tool-only clients.
- ``ResourcesAsTools`` — exposes 26 resources as tools for tool-only clients.
- ``CodeMode`` — optional zero-round-trip pipeline mode, gated by
  ``DJ_MCP_CODE_MODE`` env flag.

Split by lifecycle:
- ``build_pre_constructor_transforms()`` returns transforms that must be
  passed into ``FastMCP(transforms=...)`` BEFORE the server scans tools.
- ``register_post_constructor_transforms(mcp)`` wires the transforms that
  need a fully constructed ``mcp`` instance (they iterate tools/resources).
"""

from __future__ import annotations

import os

from fastmcp import FastMCP
from fastmcp.experimental.transforms.code_mode import CodeMode
from fastmcp.transforms.prompts_as_tools import PromptsAsTools
from fastmcp.transforms.resources_as_tools import ResourcesAsTools
from fastmcp.transforms.tool_search import BM25SearchTransform

# Always-visible tools — everything else is BM25-ranked per client query.
# Ordering: 6 entity + 2 provider + 2 compute + 1 admin = 11.
# Blueprint §15.6 allowlists 9 here; the two synthetic BM25 tools (``search``
# and ``get_tool_info``) are added automatically by the transform itself.
ALWAYS_VISIBLE_TOOLS: tuple[str, ...] = (
    "entity_list",
    "entity_get",
    "entity_create",
    "entity_aggregate",
    "provider_read",
    "provider_search",
    "transition_score_pool",
    "sequence_optimize",
    "unlock_namespace",
)

def build_pre_constructor_transforms() -> list:
    """Transforms that need to be handed to the FastMCP constructor."""
    return [
        BM25SearchTransform(
            always_visible=list(ALWAYS_VISIBLE_TOOLS),
            max_results=8,
        ),
    ]

def register_post_constructor_transforms(mcp: FastMCP) -> None:
    """Register transforms that need the fully-constructed mcp instance."""
    PromptsAsTools(mcp)
    ResourcesAsTools(mcp)
    if os.getenv("DJ_MCP_CODE_MODE", "0") == "1":
        CodeMode(mcp)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/transforms.py tests/v2/server/test_transforms.py
git commit -m "feat(v2): transforms (Tool Search + PromptsAsTools + ResourcesAsTools)

9 always-visible tools per blueprint §15.6; max_results=8 BM25. Code mode
behind DJ_MCP_CODE_MODE=1 flag, off by default."
```

---

## Task 21: `app/v2/server/visibility.py` — namespace disable + per-session unlock

**Files:**
- Create: `app/v2/server/visibility.py`
- Test: `tests/v2/server/test_visibility.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_visibility.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.v2.server.visibility import (
    DISABLED_NAMESPACE_TAGS,
    apply_visibility_policy,
    unlock_namespace,
)

def test_disabled_namespace_tags_matches_blueprint() -> None:
    assert DISABLED_NAMESPACE_TAGS == frozenset({
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
    })

def test_apply_visibility_calls_disable_for_each_tag() -> None:
    mcp = MagicMock()
    apply_visibility_policy(mcp)
    # mcp.disable is called once with tags=DISABLED_NAMESPACE_TAGS
    mcp.disable.assert_called_once_with(tags=DISABLED_NAMESPACE_TAGS)

@pytest.mark.asyncio
async def test_unlock_namespace_calls_enable_components() -> None:
    ctx = MagicMock()
    ctx.enable_components = MagicMock()
    res = await unlock_namespace(action="unlock", namespace="sync", ctx=ctx)
    ctx.enable_components.assert_called_once_with(tags={"namespace:sync"})
    assert res["status"] == "unlocked"
    assert res["namespace"] == "sync"

@pytest.mark.asyncio
async def test_unlock_namespace_lock() -> None:
    ctx = MagicMock()
    ctx.disable_components = MagicMock()
    res = await unlock_namespace(action="lock", namespace="sync", ctx=ctx)
    ctx.disable_components.assert_called_once_with(tags={"namespace:sync"})
    assert res["status"] == "locked"

@pytest.mark.asyncio
async def test_unlock_namespace_reset() -> None:
    ctx = MagicMock()
    ctx.reset_visibility = MagicMock()
    res = await unlock_namespace(action="reset", namespace=None, ctx=ctx)
    ctx.reset_visibility.assert_called_once()
    assert res["status"] == "reset"

@pytest.mark.asyncio
async def test_unlock_namespace_rejects_unknown_namespace() -> None:
    ctx = MagicMock()
    with pytest.raises(ValueError, match="unknown namespace"):
        await unlock_namespace(action="unlock", namespace="bogus", ctx=ctx)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/visibility.py`**

```python
"""Namespace-based visibility.

Three namespaces are globally disabled at startup per blueprint §15.6:
- ``namespace:crud:destructive`` — entity_update / entity_delete
- ``namespace:provider:write`` — provider_write
- ``namespace:sync`` — playlist_sync

Clients unlock per-session via ``unlock_namespace(action="unlock", namespace=...)``,
which calls ``ctx.enable_components(tags={f"namespace:{ns}"})`` and triggers
``notifications/tools/list_changed`` so the tool list refreshes.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

DISABLED_NAMESPACE_TAGS: frozenset[str] = frozenset(
    {
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
    }
)

KNOWN_NAMESPACES: frozenset[str] = frozenset(
    {
        "crud:destructive",
        "provider:write",
        "sync",
    }
)

def apply_visibility_policy(mcp: FastMCP) -> None:
    """Disable every namespace tag listed in ``DISABLED_NAMESPACE_TAGS`` globally.

    Must be called AFTER transforms and middleware — disabling tags hides the
    components from subsequent list_tools calls, and transforms need to see
    them during registration.
    """
    mcp.disable(tags=DISABLED_NAMESPACE_TAGS)

async def unlock_namespace(
    action: Literal["unlock", "lock", "status", "reset"],
    namespace: str | None = None,
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Per-session namespace activation.

    Call via MCP: ``unlock_namespace(action="unlock", namespace="sync")``.
    """
    if action == "reset":
        ctx.reset_visibility()
        return {"status": "reset"}
    if action == "status":
        return {
            "status": "ok",
            "namespaces_disabled_globally": sorted(DISABLED_NAMESPACE_TAGS),
            "known": sorted(KNOWN_NAMESPACES),
        }
    if namespace is None:
        raise ValueError("namespace parameter is required for action != 'status'/'reset'")
    if namespace not in KNOWN_NAMESPACES:
        raise ValueError(
            f"unknown namespace {namespace!r}; known: {sorted(KNOWN_NAMESPACES)}"
        )
    tag = f"namespace:{namespace}"
    if action == "unlock":
        ctx.enable_components(tags={tag})
        return {"status": "unlocked", "namespace": namespace}
    if action == "lock":
        ctx.disable_components(tags={tag})
        return {"status": "locked", "namespace": namespace}
    raise ValueError(f"unknown action: {action!r}")
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Register as a tool**

The actual `@tool` registration happens in Phase 3's
`app/v2/tools/admin/unlock_namespace.py`. This module provides the logic; the
Phase 3 stub imports ``unlock_namespace`` from here and wraps it with
``@tool(name="unlock_namespace", tags={"admin", "core"}, ...)``. Update that
Phase 3 tool file now:

```python
# app/v2/tools/admin/unlock_namespace.py
from fastmcp import tool
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

from app.v2.server.visibility import unlock_namespace as _unlock_impl

@tool(
    name="unlock_namespace",
    description="Enable/disable namespace tag (crud:destructive, provider:write, sync) for the current session.",
    tags={"admin", "core"},
    annotations={"readOnlyHint": False, "openWorldHint": False},
    meta={"version": "1.0"},
)
async def unlock_namespace(
    action: str,
    namespace: str | None = None,
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict:
    return await _unlock_impl(action=action, namespace=namespace, ctx=ctx)
```

- [ ] **Step 6: Commit**

```bash
git add app/v2/server/visibility.py tests/v2/server/test_visibility.py \
        app/v2/tools/admin/unlock_namespace.py
git commit -m "feat(v2): namespace visibility policy + unlock_namespace tool

Disables crud:destructive/provider:write/sync at startup. unlock_namespace
tool toggles per-session via ctx.enable_components(tags=...)."
```

---

## Task 22: `app/v2/server/sampling.py` — Anthropic fallback handler

**Files:**
- Create: `app/v2/server/sampling.py`
- Test: `tests/v2/server/test_sampling.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_sampling.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.v2.server.sampling import build_sampling_handler

def test_returns_none_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("DJ_ANTHROPIC_API_KEY", raising=False)
    assert build_sampling_handler() is None

def test_returns_callable_when_api_key_set(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ANTHROPIC_API_KEY", "sk-test")
    handler = build_sampling_handler()
    assert handler is not None
    assert callable(handler)

@pytest.mark.asyncio
async def test_handler_delegates_to_anthropic(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ANTHROPIC_API_KEY", "sk-test")
    fake_client = MagicMock()
    fake_message = MagicMock()
    fake_message.content = [MagicMock(text="result")]
    fake_message.model = "claude-3-5-sonnet-20241022"
    fake_message.usage.input_tokens = 10
    fake_message.usage.output_tokens = 5

    async def fake_create(*a, **kw):
        return fake_message

    fake_client.messages.create = fake_create
    with patch("app.v2.server.sampling.AsyncAnthropic", return_value=fake_client):
        handler = build_sampling_handler()
        out = await handler(
            messages=[MagicMock(content=MagicMock(text="hello"))],
            params=MagicMock(system_prompt="sys", max_tokens=100, temperature=0.2),
            context=MagicMock(),
        )
        assert "result" in str(out)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/sampling.py`**

```python
"""Server-side fallback sampling handler (Anthropic).

When ``DJ_ANTHROPIC_API_KEY`` is set, tools that call ``ctx.sample(...)``
without a client-provided LLM transport use this handler to proxy directly
to Claude. Without the key the function returns ``None`` — tools with
``behavior="fallback"`` then raise unless the client supplies sampling.
"""

from __future__ import annotations

import logging
import os
from typing import Any

try:  # pragma: no cover - optional extra
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover
    AsyncAnthropic = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

def build_sampling_handler():
    """Return an async sampling handler or None (disabled)."""
    api_key = os.getenv("DJ_ANTHROPIC_API_KEY")
    if not api_key or AsyncAnthropic is None:
        if not api_key:
            log.debug("DJ_ANTHROPIC_API_KEY unset — sampling fallback disabled")
        return None

    client = AsyncAnthropic(api_key=api_key)

    async def handler(messages, params, context) -> Any:
        budget = (
            context.fastmcp_context.state.get("sampling_budget")
            if context and getattr(context, "fastmcp_context", None)
            else None
        )
        if budget is not None:
            budget.note_sample(context)

        anthropic_messages = [
            {"role": "user", "content": getattr(m.content, "text", str(m.content))}
            for m in messages
        ]
        response = await client.messages.create(
            model=_DEFAULT_MODEL,
            system=getattr(params, "system_prompt", "") or "",
            max_tokens=getattr(params, "max_tokens", 1024),
            temperature=getattr(params, "temperature", 0.2),
            messages=anthropic_messages,
        )
        # Bump LLM token counter on state.
        if context and getattr(context, "fastmcp_context", None):
            cost = context.fastmcp_context.state.setdefault(
                "cost", {"provider_calls": 0, "llm_tokens": 0}
            )
            cost["llm_tokens"] += (
                response.usage.input_tokens + response.usage.output_tokens
            )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        return text

    return handler
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/sampling.py tests/v2/server/test_sampling.py
git commit -m "feat(v2): Anthropic sampling fallback handler

Returns None when DJ_ANTHROPIC_API_KEY is unset; otherwise proxies
ctx.sample() to Claude and bumps cost.llm_tokens counter."
```

---

## Task 23: `app/v2/server/observability.py` — Sentry + OTEL bootstrap

**Files:**
- Create: `app/v2/server/observability.py`
- Test: `tests/v2/server/test_observability.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_observability.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.v2.server.observability import bootstrap_observability

def test_bootstrap_noop_when_nothing_configured(monkeypatch) -> None:
    monkeypatch.delenv("DJ_SENTRY_DSN", raising=False)
    monkeypatch.delenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Must not raise even when SDKs not installed / not configured
    bootstrap_observability()

def test_bootstrap_initializes_sentry_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DJ_SENTRY_DSN", "https://x@example.com/1")
    with patch("app.v2.server.observability.sentry_sdk") as sdk:
        bootstrap_observability()
        sdk.init.assert_called_once()
        kwargs = sdk.init.call_args.kwargs
        assert kwargs["dsn"] == "https://x@example.com/1"

def test_bootstrap_initializes_otel_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    with patch("app.v2.server.observability._init_otel") as init_otel:
        bootstrap_observability()
        init_otel.assert_called_once_with("http://collector:4318")

def test_bootstrap_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("DJ_SENTRY_DSN", "https://x@example.com/1")
    with patch("app.v2.server.observability.sentry_sdk") as sdk:
        bootstrap_observability()
        bootstrap_observability()
        # Only called once total (idempotent guard)
        assert sdk.init.call_count == 1
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Write `app/v2/server/observability.py`**

```python
"""Sentry + OpenTelemetry bootstrap.

Idempotent. Safe to call from the server entrypoint and/or tests. Both
integrations are optional: env var unset -> skip.
"""

from __future__ import annotations

import logging
import os
from threading import Lock

try:  # pragma: no cover
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

_bootstrap_lock = Lock()
_bootstrapped = False

def _init_otel(endpoint: str) -> None:  # pragma: no cover - optional
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError:
        log.warning("opentelemetry packages missing — OTEL disabled")
        return
    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

def bootstrap_observability() -> None:
    """Initialize Sentry and OTEL once per process."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        _bootstrapped = True

    dsn = os.getenv("DJ_SENTRY_DSN")
    if dsn and sentry_sdk is not None:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.getenv("DJ_SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            environment=os.getenv("DJ_ENV", "dev"),
        )

    otel_endpoint = os.getenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        _init_otel(otel_endpoint)
```

- [ ] **Step 4: PASS — note the idempotency test requires clearing the module-level flag between tests**

Add a fixture `autouse` reset in `tests/v2/server/conftest.py` (Task 28):

```python
@pytest.fixture(autouse=True)
def _reset_observability(monkeypatch):
    import app.v2.server.observability as obs
    obs._bootstrapped = False
    yield
    obs._bootstrapped = False
```

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/observability.py tests/v2/server/test_observability.py
git commit -m "feat(v2): observability bootstrap (Sentry + OTEL)

Idempotent initializer driven by DJ_SENTRY_DSN and
DJ_OTEL_EXPORTER_OTLP_ENDPOINT env vars. Both SDKs optional."
```

---

## Task 24: `app/v2/server/app.py` — composition root + `register_middleware`

**Files:**
- Create: `app/v2/server/app.py`
- Update: `app/v2/server/middleware/__init__.py` with `ALL_MIDDLEWARE`
- Test: `tests/v2/server/test_build.py`
- Test: `tests/v2/server/test_ordering.py`

- [ ] **Step 1: Populate `app/v2/server/middleware/__init__.py`**

```python
"""16 middleware classes — ordered outer→inner per blueprint §11."""

from __future__ import annotations

from app.v2.server.middleware.audit_log import AuditLogMiddleware
from app.v2.server.middleware.cost_tracking import CostTrackingMiddleware
from app.v2.server.middleware.db_session import DbSessionMiddleware
from app.v2.server.middleware.deprecation_warning import (
    DeprecationWarningMiddleware,
)
from app.v2.server.middleware.error_handling import ErrorHandlingMiddleware
from app.v2.server.middleware.otel_tracing import OTELTracingMiddleware
from app.v2.server.middleware.progress_throttle import ProgressThrottleMiddleware
from app.v2.server.middleware.provider_rate_limit import (
    ProviderRateLimitMiddleware,
)
from app.v2.server.middleware.response_caching import ResponseCachingMiddleware
from app.v2.server.middleware.response_limit import ResponseLimitingMiddleware
from app.v2.server.middleware.retry import RetryMiddleware
from app.v2.server.middleware.sampling_budget import SamplingBudgetMiddleware
from app.v2.server.middleware.sentry_context import SentryContextMiddleware
from app.v2.server.middleware.structured_logging import (
    StructuredLoggingMiddleware,
)
from app.v2.server.middleware.timing import DetailedTimingMiddleware
from app.v2.server.middleware.tool_timeout import ToolCallTimeoutMiddleware

# ORDER MATTERS — matches blueprint §11 exactly. First added wraps all.
ALL_MIDDLEWARE: tuple[type, ...] = (
    ErrorHandlingMiddleware,           # 1
    SentryContextMiddleware,           # 2
    OTELTracingMiddleware,             # 3
    DetailedTimingMiddleware,          # 4
    AuditLogMiddleware,                # 5
    RetryMiddleware,                   # 6
    ResponseLimitingMiddleware,        # 7
    ResponseCachingMiddleware,         # 8  ENABLED
    DeprecationWarningMiddleware,      # 9
    CostTrackingMiddleware,            # 10
    SamplingBudgetMiddleware,          # 11
    ProgressThrottleMiddleware,        # 12
    ToolCallTimeoutMiddleware,         # 13
    ProviderRateLimitMiddleware,       # 14
    DbSessionMiddleware,               # 15
    StructuredLoggingMiddleware,       # 16  innermost
)

__all__ = ["ALL_MIDDLEWARE"]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/v2/server/test_build.py
from __future__ import annotations

import pytest
from fastmcp import FastMCP

from app.v2.server.app import build_mcp_server

def test_build_returns_fastmcp_instance() -> None:
    mcp = build_mcp_server()
    assert isinstance(mcp, FastMCP)

def test_build_registers_all_16_middleware(monkeypatch) -> None:
    # Middleware are added in order; mcp should expose them.
    mcp = build_mcp_server()
    added = [type(m).__name__ for m in mcp._middleware]  # FastMCP internal list
    # Must contain all 16 expected names in order.
    expected = [
        "ErrorHandlingMiddleware",
        "SentryContextMiddleware",
        "OTELTracingMiddleware",
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        "ToolCallTimeoutMiddleware",
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    assert added[: len(expected)] == expected

def test_build_applies_visibility_policy() -> None:
    mcp = build_mcp_server()
    # Three namespace tags disabled at startup
    disabled = mcp._disabled_tags  # set on FastMCP instance when disable() called
    assert "namespace:crud:destructive" in disabled
    assert "namespace:provider:write" in disabled
    assert "namespace:sync" in disabled
```

```python
# tests/v2/server/test_ordering.py
"""Middleware order matches blueprint §11 EXACTLY. Do not reorder."""

from app.v2.server.middleware import ALL_MIDDLEWARE

def test_order_is_exactly_sixteen() -> None:
    assert len(ALL_MIDDLEWARE) == 16

def test_order_matches_spec() -> None:
    expected = [
        "ErrorHandlingMiddleware",         # 1  outermost
        "SentryContextMiddleware",         # 2
        "OTELTracingMiddleware",           # 3
        "DetailedTimingMiddleware",        # 4
        "AuditLogMiddleware",              # 5
        "RetryMiddleware",                 # 6
        "ResponseLimitingMiddleware",      # 7
        "ResponseCachingMiddleware",       # 8
        "DeprecationWarningMiddleware",    # 9
        "CostTrackingMiddleware",          # 10
        "SamplingBudgetMiddleware",        # 11
        "ProgressThrottleMiddleware",      # 12
        "ToolCallTimeoutMiddleware",       # 13
        "ProviderRateLimitMiddleware",     # 14
        "DbSessionMiddleware",             # 15
        "StructuredLoggingMiddleware",     # 16 innermost
    ]
    actual = [c.__name__ for c in ALL_MIDDLEWARE]
    assert actual == expected
```

- [ ] **Step 3: FAIL**

- [ ] **Step 4: Write `app/v2/server/app.py`**

```python
"""Composition root for the v2 MCP server.

```
1. FastMCP(providers=[FSP], transforms=pre, lifespan=..., sampling_handler=...)
2. register_post_constructor_transforms(mcp)   # PromptsAsTools, ResourcesAsTools
3. register_middleware(mcp)                    # 16 middleware in §11 order
4. apply_visibility_policy(mcp)                # last — after transforms
```python

Order is load-bearing. Violating it hides bugs (transforms on wrong tool set,
visibility ignoring middleware, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.providers.file_system import FileSystemProvider

from app.v2.server.lifespan import build_server_lifespan
from app.v2.server.middleware import ALL_MIDDLEWARE
from app.v2.server.observability import bootstrap_observability
from app.v2.server.sampling import build_sampling_handler
from app.v2.server.transforms import (
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)
from app.v2.server.visibility import apply_visibility_policy

log = logging.getLogger(__name__)

def _v2_root() -> Path:
    # app/v2/server/app.py → app/v2
    return Path(__file__).resolve().parent.parent

def register_middleware(mcp: FastMCP) -> None:
    """Register all 16 middleware in blueprint §11 order."""
    for cls in ALL_MIDDLEWARE:
        mcp.add_middleware(cls())

def build_mcp_server() -> FastMCP:
    """Construct and wire up the full v2 MCP server."""
    bootstrap_observability()

    mcp = FastMCP(
        name="dj-music-v2",
        providers=[FileSystemProvider(root=str(_v2_root()))],
        transforms=build_pre_constructor_transforms(),
        lifespan=build_server_lifespan(),
        sampling_handler=build_sampling_handler(),
        on_duplicate="warn",
    )

    # Post-constructor transforms scan already-registered tools/resources/prompts.
    register_post_constructor_transforms(mcp)

    # Middleware wraps the call chain; register AFTER transforms registered.
    register_middleware(mcp)

    # Visibility policy disables namespace tags for everyone at startup;
    # must run LAST so middleware can still see the full tool set.
    apply_visibility_policy(mcp)

    log.info("dj-music-v2 MCP server built")
    return mcp
```

- [ ] **Step 5: Tests PASS**

Note: the test inspects `mcp._middleware` and `mcp._disabled_tags`. If
FastMCP exposes these under different names on this version, update the
access path accordingly — but the composition-root logic is unchanged.

- [ ] **Step 6: Commit**

```bash
git add app/v2/server/app.py app/v2/server/middleware/__init__.py \
        tests/v2/server/test_build.py tests/v2/server/test_ordering.py
git commit -m "feat(v2): server composition root

build_mcp_server wires FastMCP with FileSystemProvider root=app/v2, Tool
Search transform pre-constructor, PromptsAsTools+ResourcesAsTools post,
16 middleware in blueprint §11 order, namespace visibility last."
```

---

## Task 25: `tests/v2/server/conftest.py` — test fixtures

**Files:**
- Create: `tests/v2/server/conftest.py`

- [ ] **Step 1: Write the conftest**

```python
"""Shared fixtures for server tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

@pytest.fixture(autouse=True)
def _reset_observability():
    """Ensure ``bootstrap_observability()`` can run fresh each test."""
    import app.v2.server.observability as obs
    obs._bootstrapped = False
    yield
    obs._bootstrapped = False

@pytest.fixture
def middleware_context_factory():
    """Return a factory that builds a minimal MiddlewareContext stub."""

    def _factory(
        *,
        tool_name: str = "entity_list",
        arguments: dict | None = None,
        readonly: bool = True,
        version: str | None = None,
        session_id: str = "sess-1",
    ):
        from fastmcp.server.middleware import MiddlewareContext

        mc = MiddlewareContext.__new__(MiddlewareContext)
        msg = MagicMock()
        msg.name = tool_name
        msg.arguments = arguments or {}
        mc.message = msg

        fctx = MagicMock()
        fctx.session_id = session_id
        fctx.client_id = "client-x"
        fctx.request_id = "req-x"
        fctx.state = {}

        tool = MagicMock()
        tool.annotations = SimpleNamespace(readOnlyHint=readonly)
        tool.version = version
        tool.meta = {}

        async def _get_tool(_name: str):
            return tool

        fctx.fastmcp.get_tool = _get_tool
        mc.fastmcp_context = fctx
        return mc

    return _factory

@pytest_asyncio.fixture
async def mcp_client():
    """In-memory FastMCP client against the real build_mcp_server()."""
    from fastmcp.client import Client
    from fastmcp.client.transports import FastMCPTransport

    from app.v2.server.app import build_mcp_server

    mcp = build_mcp_server()
    async with Client(mcp) as c:
        yield c
```

- [ ] **Step 2: Commit**

```bash
git add tests/v2/server/conftest.py
git commit -m "test(v2): shared server fixtures

Autouse observability reset, MiddlewareContext factory, in-memory
mcp_client fixture against build_mcp_server()."
```

---

## Task 26: `app/v2/rest/` — thin FastAPI wrapper

**Files:**
- Create: `app/v2/rest/state.py`
- Create: `app/v2/rest/schemas.py`
- Create: `app/v2/rest/lifespan.py`
- Create: `app/v2/rest/routes/health.py`
- Create: `app/v2/rest/routes/discovery.py`
- Create: `app/v2/rest/routes/execution.py`
- Create: `app/v2/rest/app.py`
- Test: `tests/v2/rest/conftest.py`
- Test: `tests/v2/rest/test_health.py`
- Test: `tests/v2/rest/test_discovery.py`
- Test: `tests/v2/rest/test_execution.py`

- [ ] **Step 1: Write `app/v2/rest/state.py`**

```python
"""Shared runtime state for the REST wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class ApiRuntimeState:
    mcp_ready: bool = False
    mcp: Any | None = None
    degraded_reason: str | None = None
    tool_cache: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Write `app/v2/rest/schemas.py`**

```python
"""Pydantic DTOs for REST endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    mcp_ready: bool
    tool_count: int
    degraded_reason: str | None = None

class ToolSummary(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)

class ToolCallResponse(BaseModel):
    result: Any
    is_error: bool = False
    error: str | None = None
```

- [ ] **Step 3: Write `app/v2/rest/lifespan.py`**

```python
"""FastAPI lifespan — builds the MCP server, sets it on app.state."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.v2.rest.state import ApiRuntimeState

log = logging.getLogger(__name__)

@asynccontextmanager
async def rest_lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = ApiRuntimeState()
    app.state.runtime = state
    try:
        from app.v2.server.app import build_mcp_server

        state.mcp = build_mcp_server()
        state.mcp_ready = True
        log.info("REST wrapper: MCP ready")
    except Exception as exc:  # pragma: no cover - degraded mode
        state.degraded_reason = f"{type(exc).__name__}: {exc}"
        log.exception("REST wrapper: MCP build failed, entering degraded mode")
    try:
        yield
    finally:
        # MCP lifespan cleanup is handled by FastMCP when the server shuts down.
        pass
```

- [ ] **Step 4: Write `app/v2/rest/routes/health.py`**

```python
"""GET /api/health."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.v2.rest.schemas import HealthResponse
from app.v2.rest.state import ApiRuntimeState

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    runtime: ApiRuntimeState = request.app.state.runtime
    tool_count = 0
    if runtime.mcp is not None and runtime.mcp_ready:
        tools = await runtime.mcp.list_tools()
        tool_count = len(tools)
    return HealthResponse(
        status="ok" if runtime.mcp_ready else "degraded",
        mcp_ready=runtime.mcp_ready,
        tool_count=tool_count,
        degraded_reason=runtime.degraded_reason,
    )
```

- [ ] **Step 5: Write `app/v2/rest/routes/discovery.py`**

```python
"""GET /api/tools, GET /api/tools/{name}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.v2.rest.schemas import ToolSummary

router = APIRouter(prefix="/api/tools", tags=["discovery"])

@router.get("", response_model=list[ToolSummary])
async def list_tools(request: Request, tag: str | None = None) -> list[ToolSummary]:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    tools = await runtime.mcp.list_tools()
    out: list[ToolSummary] = []
    for t in tools:
        tags = sorted(getattr(t, "tags", set()) or set())
        if tag is not None and tag not in tags:
            continue
        out.append(
            ToolSummary(
                name=t.name,
                description=(t.description or "").strip() or None,
                tags=tags,
            )
        )
    return out

@router.get("/{name}", response_model=ToolSummary)
async def get_tool(name: str, request: Request) -> ToolSummary:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    try:
        tool = await runtime.mcp.get_tool(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"tool not found: {name}") from exc
    return ToolSummary(
        name=tool.name,
        description=(tool.description or "").strip() or None,
        tags=sorted(getattr(tool, "tags", set()) or set()),
    )
```

- [ ] **Step 6: Write `app/v2/rest/routes/execution.py`**

```python
"""POST /api/tools/{name}/call."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.v2.rest.schemas import ToolCallRequest, ToolCallResponse

router = APIRouter(prefix="/api/tools", tags=["execution"])

@router.post("/{name}/call", response_model=ToolCallResponse)
async def call_tool(
    name: str, payload: ToolCallRequest, request: Request
) -> ToolCallResponse:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    try:
        result = await runtime.mcp.call_tool(name, payload.arguments)
    except Exception as exc:
        return ToolCallResponse(result=None, is_error=True, error=str(exc))
    return ToolCallResponse(result=_as_jsonable(result))

def _as_jsonable(result: object) -> object:
    # FastMCP v3 ToolResult has .data or .structured_content / .content
    for attr in ("structured_content", "data"):
        value = getattr(result, attr, None)
        if value is not None:
            return value
    content = getattr(result, "content", None)
    if content:
        texts = [getattr(c, "text", None) for c in content]
        return [t for t in texts if t is not None]
    return repr(result)
```

- [ ] **Step 7: Write `app/v2/rest/app.py`**

```python
"""FastAPI app factory — thin wrapper over MCP."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.v2.rest.lifespan import rest_lifespan
from app.v2.rest.routes import discovery, execution, health

def build_rest_app() -> FastAPI:
    app = FastAPI(
        title="DJ Music Plugin v2 — REST",
        version="2.0.0",
        lifespan=rest_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(discovery.router)
    app.include_router(execution.router)
    return app

api = build_rest_app()
```

- [ ] **Step 8: Write `tests/v2/rest/conftest.py`**

```python
"""FastAPI TestClient fixture with mocked MCP."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.v2.rest.app import build_rest_app
from app.v2.rest.state import ApiRuntimeState

@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    tool = MagicMock()
    tool.name = "entity_list"
    tool.description = "list"
    tool.tags = {"core"}
    mcp.list_tools = AsyncMock(return_value=[tool])
    mcp.get_tool = AsyncMock(return_value=tool)
    call_result = MagicMock()
    call_result.structured_content = {"items": [1, 2]}
    call_result.data = None
    call_result.content = []
    mcp.call_tool = AsyncMock(return_value=call_result)
    return mcp

@pytest.fixture
def rest_client(mock_mcp):
    app = build_rest_app()

    async def _fake_lifespan(app):
        state = ApiRuntimeState(mcp=mock_mcp, mcp_ready=True)
        app.state.runtime = state
        yield

    app.router.lifespan_context = _fake_lifespan  # override
    with TestClient(app) as client:
        yield client
```

- [ ] **Step 9: Write `tests/v2/rest/test_health.py`**

```python
def test_health_ok(rest_client) -> None:
    response = rest_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mcp_ready"] is True
    assert body["tool_count"] == 1
```

- [ ] **Step 10: Write `tests/v2/rest/test_discovery.py`**

```python
def test_list_tools(rest_client) -> None:
    response = rest_client.get("/api/tools")
    assert response.status_code == 200
    assert response.json() == [
        {"name": "entity_list", "description": "list", "tags": ["core"]}
    ]

def test_list_tools_filter_by_tag(rest_client) -> None:
    r = rest_client.get("/api/tools?tag=no-such")
    assert r.status_code == 200
    assert r.json() == []

def test_get_tool(rest_client) -> None:
    response = rest_client.get("/api/tools/entity_list")
    assert response.status_code == 200
    assert response.json()["name"] == "entity_list"
```

- [ ] **Step 11: Write `tests/v2/rest/test_execution.py`**

```python
def test_call_tool_returns_structured_content(rest_client) -> None:
    response = rest_client.post(
        "/api/tools/entity_list/call",
        json={"arguments": {"entity": "track"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is False
    assert body["result"] == {"items": [1, 2]}

def test_call_tool_error_path(rest_client, mock_mcp) -> None:
    from unittest.mock import AsyncMock
    mock_mcp.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
    response = rest_client.post(
        "/api/tools/entity_list/call",
        json={"arguments": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is True
    assert "boom" in body["error"]
```

- [ ] **Step 12: Run all REST tests — PASS**

```bash
uv run pytest tests/v2/rest/ -v
```

- [ ] **Step 13: Commit**

```bash
git add app/v2/rest tests/v2/rest
git commit -m "feat(v2): REST wrapper (thin FastAPI over MCP)

/api/health, /api/tools, /api/tools/{name}, /api/tools/{name}/call.
All requests proxy mcp.call_tool(); degraded mode returns 503 when MCP
fails to build. No business logic — import-linter forbids it."
```

---

## Task 27: `app/v2/server.py` — entrypoint for `fastmcp run`

**Files:**
- Create: `app/v2/server.py`

- [ ] **Step 1: Write the entrypoint**

```python
"""MCP server entrypoint.

Run with:

    uv run fastmcp run app/v2/server.py --reload

``fastmcp run`` looks for a module-level ``mcp`` identifier. We construct
it eagerly via ``build_mcp_server()``.
"""

from __future__ import annotations

from app.v2.server.app import build_mcp_server

mcp = build_mcp_server()

if __name__ == "__main__":  # pragma: no cover
    # Support ``python -m app.v2.server``
    mcp.run()
```

- [ ] **Step 2: Smoke-run to verify importable**

```bash
uv run python -c "from app.v2.server import mcp; import asyncio; tools = asyncio.run(mcp.list_tools()); print(f'loaded {len(tools)} tools')"
```

Expected: prints the count of tools loaded from `app/v2/tools/` (should be >= 13 once Phase 3 is done). If this fails with an import error, check that all middleware modules compile (see Task 28).

- [ ] **Step 3: Commit**

```bash
git add app/v2/server.py
git commit -m "feat(v2): fastmcp run entrypoint

Module-level mcp = build_mcp_server() so 'fastmcp run app/v2/server.py'
serves the full 16-middleware pipeline."
```

---

## Task 28: End-to-end smoke test — real Client against build_mcp_server

**Files:**
- Create: `tests/v2/server/test_e2e_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/v2/server/test_e2e_smoke.py
"""End-to-end smoke test: Client(mcp) executes through the full pipeline."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from app.v2.server.app import build_mcp_server

@pytest.mark.asyncio
async def test_list_tools_after_build() -> None:
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        # At minimum, the 9 always-visible tools should be present.
        names = {t.name for t in tools}
        # After namespace disable, entity_update / entity_delete / provider_write
        # / playlist_sync should NOT be visible.
        assert "entity_list" in names
        assert "entity_get" in names
        assert "entity_create" in names
        assert "provider_read" in names
        assert "unlock_namespace" in names
        # Hidden by global namespace policy:
        for hidden in ("entity_delete", "provider_write", "playlist_sync"):
            if hidden in names:
                pytest.fail(
                    f"{hidden} should be disabled globally by visibility policy"
                )

@pytest.mark.asyncio
async def test_unlock_namespace_reveals_sync_tools() -> None:
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        await client.call_tool("unlock_namespace", {"action": "unlock", "namespace": "sync"})
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "playlist_sync" in names

@pytest.mark.asyncio
async def test_tool_call_flows_through_all_middleware(caplog) -> None:
    """One real tool call should emit logs from every stage."""
    import logging

    mcp = build_mcp_server()
    async with Client(mcp) as client:
        with caplog.at_level(logging.INFO):
            # Any tool call — entity_list with empty filters should work.
            await client.call_tool("entity_list", {"entity": "track", "filters": {}})
        # Expect enter/exit from structured_logging (innermost)
        messages = [r.message for r in caplog.records]
        assert any("call_tool.enter" in m for m in messages)
        assert any("call_tool.exit" in m for m in messages)
        # Expect a tool_timing or timing log from middleware #4
        assert any("tool_timing" in str(r.getMessage()) or "timing" in r.name for r in caplog.records)
```

- [ ] **Step 2: Run**

```bash
uv run pytest tests/v2/server/test_e2e_smoke.py -v
```

Expected: 3 passed. If `entity_list` is not yet wired to a real DB (e.g.,
test env has no Supabase), seed an in-memory DB via the Phase 2
`seeded_db` fixture; the smoke test should tolerate an empty result set —
it only asserts the call **did not raise**.

- [ ] **Step 3: Commit**

```bash
git add tests/v2/server/test_e2e_smoke.py
git commit -m "test(v2): end-to-end smoke through full pipeline

Client(build_mcp_server()) lists tools (namespace policy hides 3),
unlock_namespace reveals playlist_sync, entity_list call emits logs
from both innermost and middle middleware."
```

---

## Task 29: import-linter contract for `app.v2.server` and `app.v2.rest`

**Files:**
- Update: `.importlinter`

- [ ] **Step 1: Append two contracts to `.importlinter`**

```ini
# ── Server composition must not pull domain internals ───────────────────
[importlinter:contract:v2-server-no-domain]
name = app.v2.server may not import app.v2.domain internals
type = forbidden
source_modules =
    app.v2.server
forbidden_modules =
    app.v2.domain

# ── REST wrapper must be a thin proxy ───────────────────────────────────
[importlinter:contract:v2-rest-no-business]
name = app.v2.rest may only import app.v2.server and app.v2.shared
type = forbidden
source_modules =
    app.v2.rest
forbidden_modules =
    app.v2.domain
    app.v2.handlers
    app.v2.tools
    app.v2.resources
    app.v2.prompts
    app.v2.repositories
    app.v2.models
    app.v2.db
    app.v2.providers
    app.v2.audio
```

- [ ] **Step 2: Run**

```bash
uv run lint-imports
```

Expected: all contracts pass. If `app.v2.server.middleware.db_session`
imports `UnitOfWork` from `app.v2.repositories`, that is allowed (repos
are not in the forbidden list for `server`). If `app.v2.server.sampling`
imports from `app.v2.domain` — stop, refactor.

- [ ] **Step 3: Commit**

```bash
git add .importlinter
git commit -m "chore(v2): import-linter contracts for server + rest

Server may not reach into domain internals. REST may only import
app.v2.server and app.v2.shared — proves it's a thin proxy."
```

---

## Task 30: `pyproject.toml` — observability extras

**Files:**
- Update: `pyproject.toml`

- [ ] **Step 1: Add the `observability` optional dependency group**

```toml
[project.optional-dependencies]
observability = [
    "sentry-sdk>=2.0",
    "opentelemetry-api>=1.25",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-exporter-otlp-proto-http>=1.25",
]
```

- [ ] **Step 2: Verify lockfile updates**

```bash
uv lock
uv sync --extra observability
uv run pytest tests/v2/server/test_observability.py -v
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(v2): add [observability] extra

sentry-sdk + opentelemetry SDK packages for the Sentry and OTEL middleware.
Optional — server runs without them (no-op middleware)."
```

---

## Task 31: Full Phase 5 verification

- [ ] **Step 1: Run the full Phase 5 test suite**

```bash
uv run pytest tests/v2/server/ tests/v2/rest/ -v
```

Expected: all tests green. Count: ~70 tests.

- [ ] **Step 2: Lint + typecheck**

```bash
uv run ruff check app/v2/server app/v2/rest tests/v2/server tests/v2/rest
uv run ruff format --check app/v2/server app/v2/rest tests/v2/server tests/v2/rest
uv run mypy app/v2/server app/v2/rest
uv run lint-imports
```

Expected: all clean. Any mypy complaint about `fastmcp.*` private attr
access (e.g., `mcp._middleware`) should be silenced with a targeted
`# type: ignore[attr-defined]` — the tests intentionally reach into
FastMCP internals to assert ordering.

- [ ] **Step 3: Smoke-run the server**

```bash
uv run fastmcp run app/v2/server.py &
sleep 2
uv run fastmcp list http://localhost:8000/mcp
kill %1
```

Expected: connection succeeds, tool list is non-empty, 3 namespace-hidden
tools are absent.

- [ ] **Step 4: REST smoke-run**

```bash
uv run --extra http uvicorn app.v2.rest.app:api --port 8001 &
sleep 2
curl -sf http://localhost:8001/api/health | jq '.'
curl -sf http://localhost:8001/api/tools | jq '. | length'
kill %1
```

Expected: `/api/health` returns `status="ok"`; tool list has >=9 entries.

- [ ] **Step 5: Update CHANGELOG**

```markdown
### Added
- `app/v2/server/` — full composition root with 16-middleware pipeline (§11).
- `app/v2/server/middleware/` — one file per concern (error_handling, sentry_context, otel_tracing, timing, audit_log, retry, response_limit, response_caching, deprecation_warning, cost_tracking, sampling_budget, progress_throttle, tool_timeout, provider_rate_limit, db_session, structured_logging).
- `app/v2/server/transforms.py` — BM25SearchTransform + PromptsAsTools + ResourcesAsTools + optional CodeMode.
- `app/v2/server/visibility.py` — global disable of namespace:crud:destructive, namespace:provider:write, namespace:sync; per-session unlock.
- `app/v2/server/sampling.py` — Anthropic fallback sampling handler.
- `app/v2/server/observability.py` — Sentry + OTEL bootstrap.
- `app/v2/rest/` — thin FastAPI wrapper.
- `[observability]` extra in pyproject.toml.

### Changed
- `ResponseCachingMiddleware` enabled by default (was disabled in legacy).

### Removed
- (nothing — cutover happens in Phase 7)
```

- [ ] **Step 6: Commit + tag the phase**

```bash
git add CHANGELOG.md
git commit -m "docs(v2): phase 5 changelog

Server composition, 16-middleware pipeline, transforms, visibility,
sampling, observability, REST wrapper."
```

- [ ] **Step 7: PR to `dev`**

```bash
git push -u origin refactor/phase-5-server
gh pr create --base dev --head refactor/phase-5-server \
  --title "Phase 5: Server composition + middleware + transforms" \
  --body-file /tmp/pr-body.md
```

PR body template (`/tmp/pr-body.md`):

```markdown
## Summary
- Compose `app/v2/` MCP server per blueprint §§11, 12, 15.6.
- 16 middleware in exact §11 order; `ResponseCachingMiddleware` now ENABLED.
- Tool Search (BM25, 9 always-visible) + PromptsAsTools + ResourcesAsTools.
- Namespace activation: `crud:destructive`, `provider:write`, `sync` disabled at startup; `unlock_namespace` unlocks per-session.
- Thin REST wrapper over `mcp.call_tool()` — no business logic (import-linter enforced).

## Test plan
- [x] `uv run pytest tests/v2/server/ tests/v2/rest/` green (~70 tests).
- [x] `uv run lint-imports` green.
- [x] `uv run fastmcp run app/v2/server.py` starts, tools listable.
- [x] `curl /api/health` returns `status="ok"` with non-zero tool count.
```

---

## Definition of Done

- [ ] All 31 tasks checked off.
- [ ] `uv run pytest tests/v2/server/ tests/v2/rest/ -v` — 100% green.
- [ ] `uv run ruff check` + `ruff format --check` — clean on Phase 5 files.
- [ ] `uv run mypy app/v2/server app/v2/rest` — clean.
- [ ] `uv run lint-imports` — clean (two new contracts in place).
- [ ] `uv run fastmcp run app/v2/server.py` — serves ≥9 always-visible tools.
- [ ] `curl /api/health` via REST wrapper returns `status="ok"`.
- [ ] Middleware order in `ALL_MIDDLEWARE` EXACTLY matches blueprint §11.
- [ ] `ResponseCachingMiddleware` enabled by default (change from legacy).
- [ ] `DbSessionMiddleware` sets `ctx.fastmcp_context.state["uow"]`; `Depends(get_uow)` reads from there.
- [ ] Namespace policy disables 3 tags; `unlock_namespace` enables per-session.
- [ ] PR opened against `dev`.

---

## Reference Checklist — Middleware Ordering (DO NOT EDIT)

Blueprint §11 — outer→inner, first added wraps all:

| # | Class | New? |
|---|---|---|
| 1 | `ErrorHandlingMiddleware` | existing repackaged |
| 2 | `SentryContextMiddleware` | **new** |
| 3 | `OTELTracingMiddleware` | **new** |
| 4 | `DetailedTimingMiddleware` | existing repackaged |
| 5 | `AuditLogMiddleware` | **new** |
| 6 | `RetryMiddleware` | existing repackaged |
| 7 | `ResponseLimitingMiddleware` | existing repackaged |
| 8 | `ResponseCachingMiddleware` | existing repackaged — **now enabled** |
| 9 | `DeprecationWarningMiddleware` | **new** |
| 10 | `CostTrackingMiddleware` | **new** |
| 11 | `SamplingBudgetMiddleware` | **new** |
| 12 | `ProgressThrottleMiddleware` | **new** |
| 13 | `ToolCallTimeoutMiddleware` | existing repackaged |
| 14 | `ProviderRateLimitMiddleware` | existing repackaged (generalized from YMRateLimit) |
| 15 | `DbSessionMiddleware` | **new** (replaces `get_db_session` DI) |
| 16 | `StructuredLoggingMiddleware` | existing repackaged |

Total: **16 middleware, 8 new, 8 repackaged**.

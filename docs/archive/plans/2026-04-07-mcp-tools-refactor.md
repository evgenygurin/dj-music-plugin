# MCP Tools Layer Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `app/mcp/tools/` into vertical-slice domains with shared utilities, apply Command pattern to multi-action tools, and split 4 god-files in `app/services/` — all while keeping the 50 MCP tool contracts (names, schemas, behavior) byte-stable.

**Architecture:** Vertical-slice layout (`library/`, `sets/`, `audio/`, `curation/`, `discovery/`, `integrations/`, `admin/`) with private `_shared/` package for cross-cutting helpers (resolvers, response builder, error mapper, lifespan registry). Multi-action tools (`manage_playlist`, `manage_tracks`, `ym_playlists`, `ym_likes`) refactored from `if/elif` chains to GoF Command pattern with action registries. Service god-files split into facade + 3-4 narrow modules following the existing `services/set/*` pattern.

**Tech Stack:** Python 3.12+, FastMCP v3.1 (FileSystemProvider, standalone `@tool`, `Depends()` DI), SQLAlchemy 2.0 async, Pydantic v2, pytest + pytest-asyncio, ruff + mypy strict.

**Spec:** `docs/superpowers/specs/2026-04-07-mcp-tools-refactor-design.md`

---

## Working assumptions

- **Branch**: work happens in a worktree off `main`. Branch name suggestion: `refactor/mcp-tools-layout`.
- **Regression gate**: `make check` (lint + typecheck + test) must pass after every Task before commit.
- **Snapshot fixture**: tool catalog snapshot is the contract — any diff against baseline at the end is a bug.
- **No behavior changes**: this plan is *purely structural*. If a task requires changing observable behavior to make a test pass, stop and escalate.
- **Stable DI factory names**: `get_track_service`, `get_set_service`, etc. must keep their names — `app/mcp/dependencies.py` is consumed by `serve_http.py` and indirectly by the panel.
- **Open question dispositions** (from spec §11):
  1. Trailing underscore for `services/import_/` and `services/discovery_/` → **YES** (default applied)
  2. Snapshot location → `tests/test_mcp/fixtures/tool_catalog_baseline.json`
  3. Service refactor (Stages 3-4) happens **before** tool reorg (Stage 5)

---

## File structure (target)

### New files in `app/mcp/tools/`

```text
app/mcp/tools/
├── CLAUDE.md                          (rewrite, currently empty)
├── _shared/
│   ├── __init__.py                    (re-exports)
│   ├── resolvers.py                   (resolve_track_id, resolve_playlist, resolve_set, validate_id_or_query)
│   ├── responses.py                   (ResponseBuilder)
│   ├── errors.py                      (@map_errors decorator)
│   ├── lifespan.py                    (LifespanRegistry)
│   ├── parsing.py                     (re-export ensure_list/ensure_dict + tool-specific helpers)
│   ├── progress.py                    (ProgressReporter)
│   └── elicitation.py                 (safe_elicit + confirm_destructive, choose_one, confirm_with_warnings)
├── library/
│   ├── __init__.py
│   ├── tracks_query.py
│   ├── tracks_command.py
│   ├── playlists_query.py
│   ├── playlists_command.py
│   ├── search.py
│   └── _commands/
│       ├── __init__.py
│       ├── base.py                    (ToolCommand ABC)
│       ├── track_commands.py
│       └── playlist_commands.py
├── sets/
│   ├── __init__.py
│   ├── crud.py
│   ├── building.py
│   ├── scoring.py
│   ├── reasoning.py
│   └── delivery.py
├── audio/
│   ├── __init__.py
│   ├── analysis.py
│   ├── stems.py
│   └── _atomic.py
├── curation/
│   ├── __init__.py
│   ├── classification.py
│   ├── audit.py
│   ├── distribution.py
│   └── stats.py
├── discovery/
│   ├── __init__.py
│   ├── similar.py
│   ├── expansion.py
│   └── ingestion.py
├── integrations/
│   ├── __init__.py
│   ├── ym/
│   │   ├── __init__.py
│   │   ├── search.py
│   │   ├── catalog.py
│   │   ├── playlists.py
│   │   ├── likes.py
│   │   └── _commands/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── playlist_commands.py
│   │       └── like_commands.py
│   └── sync.py
└── admin/
    ├── __init__.py
    ├── visibility.py
    └── platforms.py
```

### Files removed from `app/mcp/tools/`

```text
admin.py, audio.py, audio_atomic.py, crud.py, curation.py, delivery.py,
discovery.py, import_download.py, playlists.py, reasoning.py,
sampling_models.py, search.py, sets.py, sync.py, tracks.py, ym.py,
_helpers.py
```

(`sampling_models.py` content moves into `discovery/similar.py` since only that tool uses it.)

### New files in `app/services/`

```text
app/services/
├── import_/
│   ├── __init__.py                    (re-export ImportService)
│   ├── facade.py
│   ├── downloader.py
│   ├── enricher.py
│   └── linker.py
├── discovery_/
│   ├── __init__.py
│   ├── facade.py
│   ├── ym_recommender.py
│   ├── llm_strategy.py
│   └── feedback_filter.py
├── metadata/
│   ├── __init__.py
│   ├── facade.py
│   ├── cache.py
│   └── enricher.py
└── sync/
    ├── __init__.py
    ├── facade.py
    ├── push.py
    ├── pull.py
    └── conflict_resolver.py
```

### Files removed from `app/services/`

```text
import_service.py, discovery_service.py, metadata_service.py, sync_service.py
```

### New tests in `tests/`

```text
tests/test_mcp/
├── fixtures/
│   └── tool_catalog_baseline.json     (Stage 0)
├── test_tool_catalog_snapshot.py      (Stage 0)
└── tools/
    ├── _shared/
    │   ├── test_resolvers.py
    │   ├── test_responses.py
    │   ├── test_errors.py
    │   ├── test_lifespan.py
    │   └── test_elicitation.py
    └── (existing tests moved to mirror new tool layout — Stage 5b)
```

---

## Stages overview

| # | Stage | Risk | Test gate | Independence |
|---|---|---|---|---|
| 0 | Snapshot baseline | Low | New snapshot test | Blocker for all |
| 1 | Build `_shared/` package (TDD) | Low | Unit tests on `_shared` | None |
| 2 | Write tools `CLAUDE.md` | Low | — | None |
| 3 | Split `import_service.py` → `services/import_/` | Med | Existing tests | None |
| 4a | Split `discovery_service.py` → `services/discovery_/` | Med | Existing tests | After 3 (lint baseline) |
| 4b | Split `metadata_service.py` → `services/metadata/` | Med | Existing tests | None |
| 4c | Split `sync_service.py` → `services/sync/` | Med | Existing tests | None |
| 5a | Create new domain dirs, move tool files (no logic changes) | High | Snapshot + full suite | After 1-4 |
| 5b | Update test imports to mirror new layout | Low | Full suite | After 5a |
| 6 | Apply `@map_errors` decorator across tools | Low | Existing tests | After 5 |
| 7 | Apply `ResponseBuilder` across list-tools | Low | Existing tests | After 5 |
| 8 | Command pattern: `manage_tracks` | Med | New command unit tests | After 5 |
| 9 | Command pattern: `manage_playlist` | Med | New command unit tests | After 5 |
| 10 | Command pattern: `ym_playlists` | Med | New command unit tests | After 5 |
| 11 | Command pattern: `ym_likes` | Low | New command unit tests | After 5 |
| 12 | Hardcoded values audit + `LifespanRegistry` wiring | Low | Existing tests | After 5 |
| 13 | Final audit, snapshot diff verification | Low | Full `make check` + snapshot diff = 0 | After all |

Stages 4a/4b/4c are independent of each other and could run in parallel. Stages 8-11 are independent. Stage 5 is the only blocker step that touches almost every file.

---

## Stage 0: Snapshot baseline

**Purpose:** Lock in the current tool catalog so we can prove zero regression at the end.

### Task 0.1: Capture current tool catalog as JSON fixture

**Files:**
- Create: `tests/test_mcp/fixtures/tool_catalog_baseline.json`
- Create: `tests/test_mcp/test_tool_catalog_snapshot.py`

- [ ] **Step 1: Write a one-shot script to dump tool catalog**

Create temp script `/tmp/dump_catalog.py`:

```python
import asyncio
import json
from pathlib import Path

from app.server import mcp

async def main():
    tools = await mcp.get_tools()
    catalog = {}
    for name, tool in sorted(tools.items()):
        catalog[name] = {
            "name": tool.name,
            "description": (tool.description or "").strip(),
            "tags": sorted(tool.tags or []),
            "annotations": dict(tool.annotations or {}),
            "input_schema": tool.input_schema,
        }
    out = Path("tests/test_mcp/fixtures/tool_catalog_baseline.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"Wrote {len(catalog)} tools to {out}")

asyncio.run(main())
```

- [ ] **Step 2: Run the dump script**

```bash
cd /Users/laptop/dev/dj-music-plugin
uv run python /tmp/dump_catalog.py
```

Expected: `Wrote 50 tools to tests/test_mcp/fixtures/tool_catalog_baseline.json`. If the count differs, capture whatever number it is — that becomes the contract. **Do not edit the JSON manually.**

- [ ] **Step 3: Write the snapshot regression test**

Create `tests/test_mcp/test_tool_catalog_snapshot.py`:

```python
"""Regression: tool catalog must remain byte-stable across the refactor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.server import mcp

BASELINE_PATH = Path(__file__).parent / "fixtures" / "tool_catalog_baseline.json"

@pytest.mark.asyncio
async def test_tool_catalog_matches_baseline() -> None:
    baseline = json.loads(BASELINE_PATH.read_text())
    tools = await mcp.get_tools()

    current: dict[str, dict] = {}
    for name, tool in sorted(tools.items()):
        current[name] = {
            "name": tool.name,
            "description": (tool.description or "").strip(),
            "tags": sorted(tool.tags or []),
            "annotations": dict(tool.annotations or {}),
            "input_schema": tool.input_schema,
        }

    assert sorted(current.keys()) == sorted(baseline.keys()), (
        f"Tool set changed. Added: {set(current) - set(baseline)}, "
        f"removed: {set(baseline) - set(current)}"
    )

    for name in baseline:
        assert current[name] == baseline[name], (
            f"Tool '{name}' contract changed. Refusing to drift."
        )
```

- [ ] **Step 4: Run the snapshot test, expect PASS**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS.

- [ ] **Step 5: Clean up temp script and commit**

```bash
rm /tmp/dump_catalog.py
git add tests/test_mcp/fixtures/tool_catalog_baseline.json tests/test_mcp/test_tool_catalog_snapshot.py
git commit -F /tmp/commit-msg.txt
```

Where `/tmp/commit-msg.txt` contains:

```bash
test(mcp): add tool catalog regression snapshot

Captures the 50-tool contract (names, descriptions, tags, annotations,
input schemas) as a baseline fixture. This is the regression gate for
the upcoming structural refactor — any drift from this snapshot is a bug.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Stage 1: Build `_shared/` package (TDD)

**Purpose:** Build the shared utilities first, with tests, so subsequent stages can rely on them.

### Task 1.1: Create `_shared` package skeleton

**Files:**
- Create: `app/mcp/tools/_shared/__init__.py`
- Create: `tests/test_mcp/tools/__init__.py`
- Create: `tests/test_mcp/tools/_shared/__init__.py`

- [ ] **Step 1: Create empty `__init__.py` files**

```bash
mkdir -p app/mcp/tools/_shared tests/test_mcp/tools/_shared
touch app/mcp/tools/_shared/__init__.py tests/test_mcp/tools/__init__.py tests/test_mcp/tools/_shared/__init__.py
```

- [ ] **Step 2: Verify FastMCP still loads (no `_shared` discovery)**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS. (Confirms `_`-prefix dirs are ignored by FileSystemProvider.)

- [ ] **Step 3: Commit**

```bash
git add app/mcp/tools/_shared/ tests/test_mcp/tools/
git commit -m "$(cat <<'EOF'
chore(mcp): scaffold _shared/ package and test dirs

Empty __init__.py files for the upcoming shared utilities. FastMCP
ignores _-prefixed directories, so this is invisible to the tool
catalog snapshot test (verified).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.2: `_shared/resolvers.py` (TDD)

**Files:**
- Create: `app/mcp/tools/_shared/resolvers.py`
- Create: `tests/test_mcp/tools/_shared/test_resolvers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mcp/tools/_shared/test_resolvers.py`:

```python
"""Tests for _shared.resolvers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from app.mcp.tools._shared.resolvers import (
    resolve_entity,
    resolve_track_id,
    validate_id_or_query,
)

def test_validate_id_or_query_raises_when_both_none() -> None:
    with pytest.raises(ToolError, match="Provide track id or query"):
        validate_id_or_query(None, None, "track")

def test_validate_id_or_query_passes_when_id_given() -> None:
    validate_id_or_query(42, None, "track")  # no exception

def test_validate_id_or_query_passes_when_query_given() -> None:
    validate_id_or_query(None, "Amelie Lens", "track")  # no exception

@pytest.mark.asyncio
async def test_resolve_entity_by_id() -> None:
    entity = object()
    get_by_id = AsyncMock(return_value=entity)
    search = AsyncMock(return_value=None)

    result = await resolve_entity(
        id=7, query=None, entity_name="Track",
        get_by_id=get_by_id, search_by_query=search,
    )

    assert result is entity
    get_by_id.assert_awaited_once_with(7)
    search.assert_not_awaited()

@pytest.mark.asyncio
async def test_resolve_entity_by_query() -> None:
    entity = object()
    get_by_id = AsyncMock(return_value=None)
    search = AsyncMock(return_value=entity)

    result = await resolve_entity(
        id=None, query="hello", entity_name="Track",
        get_by_id=get_by_id, search_by_query=search,
    )

    assert result is entity
    search.assert_awaited_once_with("hello")
    get_by_id.assert_not_awaited()

@pytest.mark.asyncio
async def test_resolve_entity_not_found_raises() -> None:
    get_by_id = AsyncMock(return_value=None)
    search = AsyncMock(return_value=None)

    with pytest.raises(ToolError, match="Track not found: 99"):
        await resolve_entity(
            id=99, query=None, entity_name="Track",
            get_by_id=get_by_id, search_by_query=search,
        )

@pytest.mark.asyncio
async def test_resolve_track_id_returns_id_directly() -> None:
    svc = AsyncMock()
    result = await resolve_track_id(id=42, query=None, svc=svc)
    assert result == 42
    svc.search.assert_not_awaited()

@pytest.mark.asyncio
async def test_resolve_track_id_searches_when_only_query() -> None:
    found = type("T", (), {"id": 17})()
    svc = AsyncMock()
    svc.search = AsyncMock(return_value=[found])

    result = await resolve_track_id(id=None, query="bicep", svc=svc)

    assert result == 17
    svc.search.assert_awaited_once_with("bicep", limit=1)

@pytest.mark.asyncio
async def test_resolve_track_id_raises_when_query_no_match() -> None:
    svc = AsyncMock()
    svc.search = AsyncMock(return_value=[])

    with pytest.raises(ToolError, match="Track not found: nope"):
        await resolve_track_id(id=None, query="nope", svc=svc)
```

- [ ] **Step 2: Run tests, expect ImportError / FAIL**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_resolvers.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement `_shared/resolvers.py`**

Create `app/mcp/tools/_shared/resolvers.py`:

```python
"""Entity resolution helpers for MCP tools.

Single source of truth for resolving tracks/playlists/sets by either
numeric ID or text query. Tools should never roll their own resolution.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError

def validate_id_or_query(
    id: int | None,
    query: str | None,
    entity_name: str = "entity",
) -> None:
    """Raise ToolError if neither id nor query is provided."""
    if id is None and query is None:
        raise ToolError(f"Provide {entity_name} id or query")

async def resolve_entity(
    *,
    id: int | None,
    query: str | None,
    entity_name: str,
    get_by_id: Callable[[int], Awaitable[Any]],
    search_by_query: Callable[[str], Awaitable[Any]],
) -> Any:
    """Resolve an entity by ID (preferred) or text query.

    Raises:
        ToolError: if neither id/query provided, or no match found.
    """
    validate_id_or_query(id, query, entity_name.lower())

    entity = await get_by_id(id) if id is not None else await search_by_query(query)  # type: ignore[arg-type]

    if entity is None:
        raise ToolError(f"{entity_name} not found: {id if id is not None else query}")

    return entity

async def resolve_track_id(
    *,
    id: int | None,
    query: str | None,
    svc: Any,
) -> int:
    """Return a numeric track id, resolving via TrackService.search if needed."""
    validate_id_or_query(id, query, "track")

    if id is not None:
        return id

    results = await svc.search(query, limit=1)
    if not results:
        raise ToolError(f"Track not found: {query}")
    return int(results[0].id)
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_resolvers.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check app/mcp/tools/_shared/ tests/test_mcp/tools/_shared/
uv run mypy app/mcp/tools/_shared/resolvers.py
git add app/mcp/tools/_shared/resolvers.py tests/test_mcp/tools/_shared/test_resolvers.py
git commit -m "$(cat <<'EOF'
feat(mcp): add _shared/resolvers for entity resolution

Single source of truth for resolve_track_id, resolve_entity, and
validate_id_or_query. Replaces three duplicate copies that exist
across audio.py, curation.py, and the legacy _helpers.py.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.3: `_shared/responses.py` (TDD)

**Files:**
- Create: `app/mcp/tools/_shared/responses.py`
- Create: `tests/test_mcp/tools/_shared/test_responses.py`

- [ ] **Step 1: Read existing schema definitions to match types**

```bash
uv run python -c "from app.core.schemas import PaginatedResponse, TrackBrief; help(PaginatedResponse)"
```

Note the actual constructor signature — the test below assumes `PaginatedResponse(items, next_cursor, total)`. Adjust if the real signature differs.

- [ ] **Step 2: Write failing tests**

Create `tests/test_mcp/tools/_shared/test_responses.py`:

```python
"""Tests for _shared.responses.ResponseBuilder."""

from __future__ import annotations

from app.core.schemas import PaginatedResponse, TrackBrief
from app.mcp.tools._shared.responses import ResponseBuilder

def test_paginated_returns_paginated_response() -> None:
    items = [TrackBrief(id=1, title="A", artist_names=["X"])]
    result = ResponseBuilder.paginated(
        items=items, next_cursor="abc", total=1, item_type=TrackBrief,
    )
    assert isinstance(result, PaginatedResponse)
    assert result.items == items
    assert result.next_cursor == "abc"
    assert result.total == 1

def test_paginated_handles_empty_list() -> None:
    result = ResponseBuilder.paginated(
        items=[], next_cursor=None, total=0, item_type=TrackBrief,
    )
    assert result.items == []
    assert result.next_cursor is None
    assert result.total == 0

def test_mutation_result_shape() -> None:
    result = ResponseBuilder.mutation_result(entity_id=42, action="archive")
    assert result == {"id": 42, "action": "archive", "status": "ok"}

def test_mutation_result_custom_status() -> None:
    result = ResponseBuilder.mutation_result(
        entity_id=42, action="delete", status="dry_run",
    )
    assert result["status"] == "dry_run"
```

- [ ] **Step 3: Run tests, expect FAIL**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_responses.py -v
```

Expected: FAIL (import error).

- [ ] **Step 4: Implement `_shared/responses.py`**

Create `app/mcp/tools/_shared/responses.py`:

```python
"""Response builders for MCP tools.

Centralized factory for typed responses (paginated lists, mutation
results, brief lists). Tools must use these instead of constructing
PaginatedResponse[T] directly.
"""

from __future__ import annotations

from typing import Any, TypeVar

from app.core.schemas import PaginatedResponse

T = TypeVar("T")

class ResponseBuilder:
    """Factory for typed MCP tool responses."""

    @staticmethod
    def paginated(
        *,
        items: list[T],
        next_cursor: str | None,
        total: int,
        item_type: type[T],  # noqa: ARG004 — kept for explicit typing intent
    ) -> PaginatedResponse[T]:
        """Build a PaginatedResponse[T] from items + cursor info."""
        return PaginatedResponse[item_type](  # type: ignore[valid-type]
            items=items,
            next_cursor=next_cursor,
            total=total,
        )

    @staticmethod
    def mutation_result(
        *,
        entity_id: int,
        action: str,
        status: str = "ok",
        **extra: Any,
    ) -> dict[str, Any]:
        """Standard mutation acknowledgement payload."""
        return {"id": entity_id, "action": action, "status": status, **extra}
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_responses.py -v
```

Expected: 4 PASS. If the `PaginatedResponse[item_type]` syntax doesn't work in your Pydantic v2 setup, fall back to constructing without parameterization (Pydantic v2 generic models accept either form).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check app/mcp/tools/_shared/responses.py tests/test_mcp/tools/_shared/test_responses.py
uv run mypy app/mcp/tools/_shared/responses.py
git add app/mcp/tools/_shared/responses.py tests/test_mcp/tools/_shared/test_responses.py
git commit -m "$(cat <<'EOF'
feat(mcp): add _shared/responses ResponseBuilder

Centralizes PaginatedResponse[T] construction and mutation result
payloads. Replaces ad-hoc response building scattered across ~10
list-tool locations.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.4: `_shared/errors.py` (TDD)

**Files:**
- Create: `app/mcp/tools/_shared/errors.py`
- Create: `tests/test_mcp/tools/_shared/test_errors.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mcp/tools/_shared/test_errors.py`:

```python
"""Tests for _shared.errors.map_errors decorator."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.mcp.tools._shared.errors import map_errors

@pytest.mark.asyncio
async def test_passthrough_on_success() -> None:
    @map_errors
    async def f(x: int) -> int:
        return x * 2

    assert await f(3) == 6

@pytest.mark.asyncio
async def test_maps_not_found_error() -> None:
    @map_errors
    async def f() -> None:
        raise NotFoundError(entity_type="Track", identifier=99)

    with pytest.raises(ToolError, match="Track not found: 99"):
        await f()

@pytest.mark.asyncio
async def test_maps_validation_error() -> None:
    @map_errors
    async def f() -> None:
        raise ValidationError("must be positive", field="bpm", value=-1)

    with pytest.raises(ToolError, match="bpm"):
        await f()

@pytest.mark.asyncio
async def test_maps_conflict_error() -> None:
    @map_errors
    async def f() -> None:
        raise ConflictError("version mismatch")

    with pytest.raises(ToolError, match="version mismatch"):
        await f()

@pytest.mark.asyncio
async def test_passes_through_tool_error() -> None:
    @map_errors
    async def f() -> None:
        raise ToolError("explicit boundary error")

    with pytest.raises(ToolError, match="explicit boundary error"):
        await f()

@pytest.mark.asyncio
async def test_does_not_swallow_unrelated_exceptions() -> None:
    @map_errors
    async def f() -> None:
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError, match="unexpected"):
        await f()
```

- [ ] **Step 2: Run tests, expect FAIL**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_errors.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Inspect actual error class field names**

```bash
uv run python -c "from app.core.errors import NotFoundError, ValidationError; print(NotFoundError.__init__.__doc__); e = NotFoundError(entity_type='Track', identifier=1); print(vars(e))"
```

Note the actual attribute names — adjust the implementation below if `entity_type` is something else (e.g. `entity`).

- [ ] **Step 4: Implement `_shared/errors.py`**

Create `app/mcp/tools/_shared/errors.py`:

```python
"""Error mapping decorator for MCP tools.

@map_errors converts domain exceptions (NotFoundError, ValidationError,
ConflictError) into ToolError so individual tool functions don't need
to repeat try/except boilerplate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastmcp.exceptions import ToolError

from app.core.errors import ConflictError, NotFoundError, ValidationError

P = ParamSpec("P")
R = TypeVar("R")

def map_errors(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Decorator: map domain exceptions to ToolError.

    Apply to every @tool function. ToolError and unrelated exceptions
    propagate unchanged — only known domain errors are translated.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except ToolError:
            raise
        except NotFoundError as exc:
            raise ToolError(f"{exc.entity_type} not found: {exc.identifier}") from exc
        except ValidationError as exc:
            field = getattr(exc, "field", None)
            msg = f"Invalid {field}: {exc}" if field else f"Invalid input: {exc}"
            raise ToolError(msg) from exc
        except ConflictError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_errors.py -v
```

Expected: 6 PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check app/mcp/tools/_shared/errors.py tests/test_mcp/tools/_shared/test_errors.py
uv run mypy app/mcp/tools/_shared/errors.py
git add app/mcp/tools/_shared/errors.py tests/test_mcp/tools/_shared/test_errors.py
git commit -m "$(cat <<'EOF'
feat(mcp): add _shared/errors @map_errors decorator

Removes per-tool try/except boilerplate by mapping domain errors
(NotFoundError, ValidationError, ConflictError) to ToolError once
at the boundary.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.5: `_shared/lifespan.py` (TDD)

**Files:**
- Create: `app/mcp/tools/_shared/lifespan.py`
- Create: `tests/test_mcp/tools/_shared/test_lifespan.py`

- [ ] **Step 1: Inspect current lifespan key strings**

```bash
uv run rg "lifespan_context\[" app/mcp/ -n
```

Note the exact string keys (e.g. `"ym_client"`, `"analyzer_registry"`, `"transition_cache"`, `"db_session_factory"`).

- [ ] **Step 2: Write failing tests**

Create `tests/test_mcp/tools/_shared/test_lifespan.py`:

```python
"""Tests for _shared.lifespan.LifespanRegistry."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.mcp.tools._shared.lifespan import LifespanRegistry

def _ctx(**values: object) -> SimpleNamespace:
    return SimpleNamespace(lifespan_context=dict(values))

def test_ym_client_returns_value() -> None:
    client = MagicMock(name="YandexMusicClient")
    ctx = _ctx(ym_client=client)
    assert LifespanRegistry.ym_client(ctx) is client

def test_analyzer_registry_returns_value() -> None:
    reg = MagicMock(name="AnalyzerRegistry")
    ctx = _ctx(analyzer_registry=reg)
    assert LifespanRegistry.analyzer_registry(ctx) is reg

def test_transition_cache_returns_value() -> None:
    cache = MagicMock(name="TransitionCache")
    ctx = _ctx(transition_cache=cache)
    assert LifespanRegistry.transition_cache(ctx) is cache

def test_missing_key_raises_keyerror() -> None:
    ctx = _ctx()
    with pytest.raises(KeyError):
        LifespanRegistry.ym_client(ctx)
```

- [ ] **Step 3: Run tests, expect FAIL**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_lifespan.py -v
```

Expected: FAIL (import error).

- [ ] **Step 4: Implement `_shared/lifespan.py`**

Create `app/mcp/tools/_shared/lifespan.py`:

```python
"""Type-safe accessors for lifespan context objects.

Replaces magic-string `ctx.lifespan_context["ym_client"]` access with
classmethods that document the expected type. Used internally by
dependencies.py and any tool that needs raw lifespan objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.audio.analyzers.base import AnalyzerRegistry
    from app.core.cache import TransitionCache
    from app.ym.client import YandexMusicClient

class _HasLifespan(Protocol):
    lifespan_context: dict[str, Any]

class LifespanRegistry:
    """Type-safe accessors for objects stored in MCP lifespan context."""

    @staticmethod
    def ym_client(ctx: _HasLifespan) -> YandexMusicClient:
        return ctx.lifespan_context["ym_client"]

    @staticmethod
    def analyzer_registry(ctx: _HasLifespan) -> AnalyzerRegistry:
        return ctx.lifespan_context["analyzer_registry"]

    @staticmethod
    def transition_cache(ctx: _HasLifespan) -> TransitionCache:
        return ctx.lifespan_context["transition_cache"]
```

If the actual key strings differ from those above (verified in Step 1), update them here.

- [ ] **Step 5: Run tests, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_lifespan.py -v
```

Expected: 4 PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check app/mcp/tools/_shared/lifespan.py tests/test_mcp/tools/_shared/test_lifespan.py
uv run mypy app/mcp/tools/_shared/lifespan.py
git add app/mcp/tools/_shared/lifespan.py tests/test_mcp/tools/_shared/test_lifespan.py
git commit -m "$(cat <<'EOF'
feat(mcp): add _shared/lifespan LifespanRegistry

Type-safe accessors for ym_client, analyzer_registry, and
transition_cache. Wiring into dependencies.py happens later
(Stage 12) to keep this commit narrow.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.6: `_shared/parsing.py`, `progress.py`, `elicitation.py` (thin wrappers)

**Files:**
- Create: `app/mcp/tools/_shared/parsing.py`
- Create: `app/mcp/tools/_shared/progress.py`
- Create: `app/mcp/tools/_shared/elicitation.py`

These are thin facades over existing modules — full TDD is overkill. One small test per module.

- [ ] **Step 1: Write `_shared/parsing.py`**

```python
"""JSON parameter parsing for MCP tools.

Re-exports the canonical helpers from app.core.parsing so tools
import from the _shared boundary instead of reaching into core.
"""

from __future__ import annotations

from app.core.parsing import ensure_dict, ensure_list

__all__ = ["ensure_dict", "ensure_list"]
```

- [ ] **Step 2: Write `_shared/progress.py`**

```python
"""Progress reporting wrapper for long-running tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.context import Context

class ProgressReporter:
    """Report progress for batch operations.

    Usage:
        reporter = ProgressReporter(ctx, total=len(items))
        for item in items:
            ...
            await reporter.tick(f"Processed {item.name}")
    """

    def __init__(self, ctx: "Context | None", *, total: int) -> None:
        self._ctx = ctx
        self._total = total
        self._current = 0

    async def tick(self, message: str | None = None) -> None:
        self._current += 1
        if self._ctx is None:
            return
        await self._ctx.report_progress(self._current, self._total)
        if message:
            await self._ctx.info(message)
```

- [ ] **Step 3: Write `_shared/elicitation.py`**

```python
"""Typed elicitation prompts for MCP tools.

Wrappers over ctx.elicit() for the most common patterns:
- confirm_destructive: yes/no on a risky operation
- confirm_with_warnings: confirm in the presence of warnings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp.server.context import Context

async def confirm_destructive(ctx: "Context | None", message: str) -> bool:
    """Ask the user to confirm a destructive action. Defaults to False if no ctx."""
    if ctx is None:
        return False
    result = await ctx.elicit(message, response_type=None)
    return getattr(result, "action", "") == "accept"

async def confirm_with_warnings(
    ctx: "Context | None",
    *,
    headline: str,
    warnings: list[str],
) -> bool:
    """Surface warnings and ask the user to proceed."""
    if ctx is None:
        return False
    body = headline + "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings)
    result = await ctx.elicit(body, response_type=None)
    return getattr(result, "action", "") == "accept"
```

- [ ] **Step 4: Write smoke test**

Create `tests/test_mcp/tools/_shared/test_thin_wrappers.py`:

```python
"""Smoke tests for thin _shared wrappers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.mcp.tools._shared.elicitation import (
    confirm_destructive,
    confirm_with_warnings,
)
from app.mcp.tools._shared.parsing import ensure_dict, ensure_list
from app.mcp.tools._shared.progress import ProgressReporter

def test_parsing_reexports_callable() -> None:
    assert callable(ensure_list)
    assert callable(ensure_dict)

@pytest.mark.asyncio
async def test_progress_reporter_no_ctx() -> None:
    reporter = ProgressReporter(None, total=3)
    await reporter.tick("hello")  # no exception

@pytest.mark.asyncio
async def test_progress_reporter_with_ctx() -> None:
    ctx = AsyncMock()
    reporter = ProgressReporter(ctx, total=3)
    await reporter.tick("step 1")
    ctx.report_progress.assert_awaited_once_with(1, 3)
    ctx.info.assert_awaited_once_with("step 1")

@pytest.mark.asyncio
async def test_confirm_destructive_no_ctx_returns_false() -> None:
    assert await confirm_destructive(None, "Delete everything?") is False

@pytest.mark.asyncio
async def test_confirm_destructive_accept() -> None:
    ctx = AsyncMock()
    ctx.elicit = AsyncMock(return_value=type("R", (), {"action": "accept"})())
    assert await confirm_destructive(ctx, "Proceed?") is True

@pytest.mark.asyncio
async def test_confirm_with_warnings_decline() -> None:
    ctx = AsyncMock()
    ctx.elicit = AsyncMock(return_value=type("R", (), {"action": "decline"})())
    result = await confirm_with_warnings(ctx, headline="Hi", warnings=["a", "b"])
    assert result is False
```

- [ ] **Step 5: Run tests + lint**

```bash
uv run pytest tests/test_mcp/tools/_shared/test_thin_wrappers.py -v
uv run ruff check app/mcp/tools/_shared/parsing.py app/mcp/tools/_shared/progress.py app/mcp/tools/_shared/elicitation.py
uv run mypy app/mcp/tools/_shared/parsing.py app/mcp/tools/_shared/progress.py app/mcp/tools/_shared/elicitation.py
```

Expected: 6 PASS, lint clean.

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/_shared/parsing.py app/mcp/tools/_shared/progress.py app/mcp/tools/_shared/elicitation.py tests/test_mcp/tools/_shared/test_thin_wrappers.py
git commit -m "$(cat <<'EOF'
feat(mcp): add _shared parsing/progress/elicitation wrappers

Thin facades over app.core.parsing and ctx.elicit for the common
batch-progress and destructive-confirm patterns. Tools will use
these instead of reaching into core directly.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 1.7: `_shared/__init__.py` re-exports

**Files:**
- Modify: `app/mcp/tools/_shared/__init__.py`

- [ ] **Step 1: Populate `__init__.py` with curated re-exports**

```python
"""Shared utilities for MCP tools (private — FastMCP ignores _-prefix)."""

from __future__ import annotations

from app.mcp.tools._shared.elicitation import (
    confirm_destructive,
    confirm_with_warnings,
)
from app.mcp.tools._shared.errors import map_errors
from app.mcp.tools._shared.lifespan import LifespanRegistry
from app.mcp.tools._shared.parsing import ensure_dict, ensure_list
from app.mcp.tools._shared.progress import ProgressReporter
from app.mcp.tools._shared.resolvers import (
    resolve_entity,
    resolve_track_id,
    validate_id_or_query,
)
from app.mcp.tools._shared.responses import ResponseBuilder

__all__ = [
    "LifespanRegistry",
    "ProgressReporter",
    "ResponseBuilder",
    "confirm_destructive",
    "confirm_with_warnings",
    "ensure_dict",
    "ensure_list",
    "map_errors",
    "resolve_entity",
    "resolve_track_id",
    "validate_id_or_query",
]
```

- [ ] **Step 2: Run full _shared test suite + snapshot**

```bash
uv run pytest tests/test_mcp/tools/_shared/ tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: all PASS, snapshot still matches baseline.

- [ ] **Step 3: Commit**

```bash
git add app/mcp/tools/_shared/__init__.py
git commit -m "$(cat <<'EOF'
feat(mcp): export _shared public API

Curated re-exports so tools can `from app.mcp.tools._shared import ...`
without reaching into individual submodules.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 2: Tools layer CLAUDE.md

### Task 2.1: Write `app/mcp/tools/CLAUDE.md`

**Files:**
- Modify: `app/mcp/tools/CLAUDE.md` (currently empty/placeholder)

- [ ] **Step 1: Replace contents**

Overwrite `app/mcp/tools/CLAUDE.md`:

```markdown
# MCP Tools Layer

Tools are the public surface of the MCP server. Each tool is a thin
adapter: validate input → resolve entities → call a service → format
the response. No business logic lives here.

## Layout (vertical slices by domain)

```text
tools/
├── _shared/             private utilities (FastMCP ignores _-prefix)
├── library/             tracks, playlists, search
├── sets/                set CRUD, building, scoring, reasoning, delivery
├── audio/               analysis (visible) + _atomic (hidden)
├── curation/            mood, audit, distribution, library stats
├── discovery/           similar, expansion, ingestion
├── integrations/ym/     Yandex Music API wrappers
├── integrations/        sync (cross-platform)
└── admin/               visibility, platforms
```

## Conventions

- **One file = one topic.** Target ≤200 lines, hard cap 250. If a file
  grows past 250, split it.
- **`*_query.py` / `*_command.py` split** is used only in `library/`
  where read and mutation operations were tangled. Other domains use
  topic-based filenames (`building.py`, `scoring.py`, etc.).
- **Standalone `@tool`**, never `@mcp.tool`. FastMCP FileSystemProvider
  auto-discovers.
- **Tags are required**: `tags={"core" | "sets" | "audio" | ...}`.
- **`readOnlyHint` annotation** is required for read-only tools.

## Imports — what tools may use

✅ `from app.mcp.dependencies import get_*_service` (DI factories)
✅ `from app.mcp.tools._shared import ...` (helpers)
✅ `from app.core.schemas import ...` (response types)
✅ `from app.core.constants import ...` (enums)
✅ `from app.services.<domain> import <Service>` (for type hints only;
   the instance comes via Depends)

❌ `from app.repositories.*` (services own repos)
❌ `from app.mcp.tools.<other_domain>` (cross-domain coupling)
❌ `from app.audio.*` directly (go through services)

## Patterns

### Error handling
Apply `@map_errors` from `_shared.errors` to every `@tool`. Do not
write per-tool `try/except NotFoundError` boilerplate.

```python
from app.mcp.tools._shared import map_errors

@tool(tags={"core"}, annotations={"readOnlyHint": True})
@map_errors
async def get_track(...):
    ...
```

### Pagination
Build paginated responses through `ResponseBuilder.paginated`. Do not
construct `PaginatedResponse[T]` inline.

```python
from app.mcp.tools._shared import ResponseBuilder

return ResponseBuilder.paginated(
    items=tracks, next_cursor=page.next_cursor, total=page.total,
    item_type=TrackBrief,
)
```

### Entity resolution
Use `resolve_track_id`, `resolve_entity`, or `validate_id_or_query`
from `_shared.resolvers`. Never roll your own.

### Multi-action tools
Tools with an `action: Literal[...]` parameter use the Command pattern.
Each action is a class in a sibling `_commands/` directory; the tool
function dispatches via a registry dict. See
`library/_commands/playlist_commands.py` for the canonical example.

### File size cap
If you find yourself writing the 250th line in a file, split it.
This is non-negotiable — large files defeat the layout's purpose.

## Tests

Tests mirror tool layout:
`tests/test_mcp/tools/<domain>/test_<file>.py`

Run for the slice you touched:
```bash
uv run pytest tests/test_mcp/tools/library/ -v
```

The catalog snapshot test (`tests/test_mcp/test_tool_catalog_snapshot.py`)
gates structural drift — if you change a tool's name, schema, tags, or
description, update the baseline fixture in the same commit and explain
why.
```text

- [ ] **Step 2: Verify snapshot still passes**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/mcp/tools/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(mcp): write tools layer CLAUDE.md

Layout map, conventions, allowed imports, and the canonical patterns
for error handling, pagination, resolution, and multi-action tools.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 3: Split `import_service.py` → `services/import_/`

**Purpose:** Decompose the 342-line god-file before tools land on top of it.

### Task 3.1: Read and understand the current file

- [ ] **Step 1: Inventory current public API**

```bash
uv run rg "from app\.services\.import_service import" -l
uv run rg "^class |^    (async )?def " app/services/import_service.py -n
```

Note every public class, every public method, every external import site. **The public API of `ImportService` must remain identical** — only internals are reorganized.

### Task 3.2: Identify cohesive sub-modules

- [ ] **Step 1: Manually classify each method into one of**
  - `downloader.py` — methods orchestrating YM track downloads
  - `enricher.py` — methods enriching tracks with YM metadata
  - `linker.py` — methods linking downloaded files to DB rows
  - `facade.py` — `ImportService` class that composes the three above

Write the classification as a markdown table in your scratch buffer; the executor will refer to it during the actual move.

### Task 3.3: Create the new package skeleton

**Files:**
- Create: `app/services/import_/__init__.py`
- Create: `app/services/import_/facade.py`
- Create: `app/services/import_/downloader.py`
- Create: `app/services/import_/enricher.py`
- Create: `app/services/import_/linker.py`

- [ ] **Step 1: Create directory and empty modules**

```bash
mkdir -p app/services/import_
touch app/services/import_/__init__.py
```

- [ ] **Step 2: Move methods into their target submodules**

Cut each group of methods from `app/services/import_service.py` into the corresponding new file. Each submodule defines a small helper class (e.g. `Downloader`, `Enricher`, `Linker`) holding the methods. The facade composes them:

```python
# app/services/import_/facade.py
from __future__ import annotations

from app.repositories.track import TrackRepository
from app.repositories.metadata import MetadataRepository
# ... whatever the original imports were

from app.services.import_.downloader import Downloader
from app.services.import_.enricher import Enricher
from app.services.import_.linker import Linker

class ImportService:
    """Facade for track import operations.

    Composes Downloader, Enricher, and Linker. Public API matches the
    pre-refactor ImportService 1:1.
    """

    def __init__(
        self,
        track_repo: TrackRepository,
        metadata_repo: MetadataRepository,
        # ... same constructor signature as before
    ) -> None:
        self._downloader = Downloader(...)
        self._enricher = Enricher(...)
        self._linker = Linker(...)

    # Re-export every public method that the old ImportService had,
    # delegating to the appropriate sub-component. Example:
    async def import_tracks(self, *args, **kwargs):
        return await self._downloader.import_tracks(*args, **kwargs)

    # ... etc, one delegation per public method
```

Each submodule (`downloader.py`, `enricher.py`, `linker.py`) holds a single class with the moved methods. Target ≤150 lines per submodule.

- [ ] **Step 3: Wire `__init__.py`**

```python
# app/services/import_/__init__.py
"""Track import services — download, enrich, link."""

from app.services.import_.facade import ImportService

__all__ = ["ImportService"]
```

- [ ] **Step 4: Delete the old file**

```bash
git rm app/services/import_service.py
```

- [ ] **Step 5: Update import sites**

```bash
uv run rg "from app\.services\.import_service import" -l
```

For every file in the result (likely `app/mcp/dependencies.py` and possibly tools), change the import:

```python
# before
from app.services.import_service import ImportService

# after
from app.services.import_ import ImportService
```

- [ ] **Step 6: Run full check**

```bash
uv run ruff check app/services/import_/ app/mcp/
uv run mypy app/services/import_/
uv run pytest tests/ -v -x
```

Expected: all PASS. If any test fails because of an internal method that an existing test was calling directly, either re-expose it on the facade or update the test to call the public method.

- [ ] **Step 7: Commit**

```bash
git add app/services/import_/ app/mcp/
git commit -m "$(cat <<'EOF'
refactor(services): split import_service into import_/ package

342-line god-file decomposed into facade + downloader + enricher +
linker. Public ImportService API unchanged (verified by passing
existing test suite). Same constructor, same methods, same
behavior — only internal layout changed.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 4: Split remaining service god-files

Three independent sub-stages. Each follows the **exact same template** as Stage 3 — only the names change. They can be done in parallel.

### Task 4a: Split `discovery_service.py` → `services/discovery_/`

**Files:**
- Create: `app/services/discovery_/{__init__,facade,ym_recommender,llm_strategy,feedback_filter}.py`
- Delete: `app/services/discovery_service.py`

- [ ] **Step 1: Inventory** — `uv run rg "^class |^    (async )?def " app/services/discovery_service.py -n` and `uv run rg "from app\.services\.discovery_service import" -l`

- [ ] **Step 2: Classify methods** into:
  - `ym_recommender.py` — calls into YM `get_similar`, `get_recommendations`
  - `llm_strategy.py` — client-driven LLM workflows (`search_queries` param path)
  - `feedback_filter.py` — like/dislike filtering
  - `facade.py` — `DiscoveryService` composing the above

- [ ] **Step 3: Create files, move methods, build facade with delegation**

Same template as Stage 3 Task 3.3 Step 2 — each submodule holds one class, facade composes and re-exports public API.

- [ ] **Step 4: `__init__.py` re-exports `DiscoveryService`**

```python
"""Discovery services — YM recommendations, LLM strategies, feedback filters."""

from app.services.discovery_.facade import DiscoveryService

__all__ = ["DiscoveryService"]
```

- [ ] **Step 5: Update import sites**

```bash
uv run rg "from app\.services\.discovery_service import" -l
# replace with: from app.services.discovery_ import DiscoveryService
```

- [ ] **Step 6: `git rm app/services/discovery_service.py`, run `make check`**

- [ ] **Step 7: Commit**

```text
refactor(services): split discovery_service into discovery_/ package

341-line god-file → facade + ym_recommender + llm_strategy +
feedback_filter. Public DiscoveryService API unchanged.
```

### Task 4b: Split `metadata_service.py` → `services/metadata/`

**Files:**
- Create: `app/services/metadata/{__init__,facade,cache,enricher}.py`
- Delete: `app/services/metadata_service.py`

- [ ] **Step 1: Inventory** — `uv run rg "^class |^    (async )?def " app/services/metadata_service.py -n` and find all import sites.

- [ ] **Step 2: Classify methods** into:
  - `cache.py` — `raw_provider_responses` reads/writes
  - `enricher.py` — YM payload → local model field mapping
  - `facade.py` — `MetadataService`

⚠️ **Naming collision check**: there may already be a `app/repositories/metadata.py`. Confirm the new package is `app/services/metadata/` not `app/services/metadata.py`. The imports differ:

```python
# repository (unchanged)
from app.repositories.metadata import MetadataRepository

# new service location
from app.services.metadata import MetadataService
```

- [ ] **Step 3: Create files, move methods, build facade with delegation**

- [ ] **Step 4: `__init__.py` re-exports**

```python
"""Metadata services — cache + enricher for provider metadata."""

from app.services.metadata.facade import MetadataService

__all__ = ["MetadataService"]
```

- [ ] **Step 5: Update import sites**

```bash
uv run rg "from app\.services\.metadata_service import" -l
# replace with: from app.services.metadata import MetadataService
```

- [ ] **Step 6: `git rm app/services/metadata_service.py`, `make check`**

- [ ] **Step 7: Commit**

```text
refactor(services): split metadata_service into metadata/ package

315-line god-file → facade + cache + enricher. Public
MetadataService API unchanged.
```

### Task 4c: Split `sync_service.py` → `services/sync/`

**Files:**
- Create: `app/services/sync/{__init__,facade,push,pull,conflict_resolver}.py`
- Delete: `app/services/sync_service.py`

- [ ] **Step 1: Inventory** — `uv run rg "^class |^    (async )?def " app/services/sync_service.py -n` and find all import sites.

- [ ] **Step 2: Classify methods** into:
  - `push.py` — local → YM
  - `pull.py` — YM → local
  - `conflict_resolver.py` — diff/merge logic
  - `facade.py` — `SyncService`

- [ ] **Step 3: Create files, move methods, build facade with delegation**

- [ ] **Step 4: `__init__.py` re-exports**

```python
"""Sync services — push, pull, conflict resolution."""

from app.services.sync.facade import SyncService

__all__ = ["SyncService"]
```

- [ ] **Step 5: Update import sites**

```bash
uv run rg "from app\.services\.sync_service import" -l
# replace with: from app.services.sync import SyncService
```

- [ ] **Step 6: `git rm app/services/sync_service.py`, `make check`**

- [ ] **Step 7: Commit**

```text
refactor(services): split sync_service into sync/ package

310-line god-file → facade + push + pull + conflict_resolver. Public
SyncService API unchanged.
```

### Task 4d: Verify nothing depends on the old import paths

- [ ] **Step 1: Repo-wide grep**

```bash
uv run rg "from app\.services\.(import|discovery|metadata|sync)_service" .
```

Expected: empty result.

- [ ] **Step 2: Run full check**

```bash
make check
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: all green, snapshot matches.

- [ ] **Step 3: No commit** — this is a verification gate, not a code change.

---

## Stage 5: Move tool files into vertical-slice layout

**This is the highest-risk stage** because it touches every tool file. The rule is **zero behavior changes** — pure file moves and import updates.

### Task 5.1: Create domain directories

**Files:**
- Create: `app/mcp/tools/{library,sets,audio,curation,discovery,integrations,integrations/ym,admin}/__init__.py`

- [ ] **Step 1: Create dirs and empty `__init__.py`**

```bash
cd /Users/laptop/dev/dj-music-plugin
for d in library sets audio curation discovery integrations integrations/ym admin; do
  mkdir -p "app/mcp/tools/$d"
  touch "app/mcp/tools/$d/__init__.py"
done
```

- [ ] **Step 2: Verify FastMCP still loads cleanly**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS — empty `__init__.py` files don't add any tools.

- [ ] **Step 3: Commit**

```bash
git add app/mcp/tools/library/ app/mcp/tools/sets/ app/mcp/tools/audio/ app/mcp/tools/curation/ app/mcp/tools/discovery/ app/mcp/tools/integrations/ app/mcp/tools/admin/
git commit -m "$(cat <<'EOF'
chore(mcp): scaffold domain directories under tools/

Empty __init__.py for library/, sets/, audio/, curation/, discovery/,
integrations/{,ym}/, and admin/. Tool files move in next.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 5.2: Move file mapping reference

The executor uses this table for the next several tasks. **Each row is a `git mv` followed by an in-file rewrite of imports — no logic changes.**

| Old path | New path | Notes |
|---|---|---|
| `tools/admin.py` | `tools/admin/visibility.py` (split) | `unlock_tools` here |
| `tools/admin.py` | `tools/admin/platforms.py` (split) | `list_platforms` here |
| `tools/audio.py` | `tools/audio/analysis.py` (split) | `analyze_track`, `analyze_batch` |
| `tools/audio.py` | `tools/audio/stems.py` (split) | `separate_stems` |
| `tools/audio_atomic.py` | `tools/audio/_atomic.py` | rename + move |
| `tools/crud.py` | `tools/sets/crud.py` | (this file is set CRUD) |
| `tools/curation.py` | `tools/curation/classification.py` (split) | `classify_mood` |
| `tools/curation.py` | `tools/curation/audit.py` (split) | `audit_playlist`, `review_set_quality` |
| `tools/curation.py` | `tools/curation/distribution.py` (split) | `distribute_to_subgenres` |
| `tools/curation.py` | `tools/curation/stats.py` (split) | `get_library_stats` |
| `tools/delivery.py` | `tools/sets/delivery.py` | move |
| `tools/discovery.py` | `tools/discovery/similar.py` (split) | `find_similar_tracks` |
| `tools/discovery.py` | `tools/discovery/expansion.py` (split) | `expand_playlist_ym`, `filter_by_feedback` |
| `tools/import_download.py` | `tools/discovery/ingestion.py` | `import_tracks`, `download_tracks` |
| `tools/playlists.py` | `tools/library/playlists_query.py` (split) | `list_playlists`, `get_playlist` |
| `tools/playlists.py` | `tools/library/playlists_command.py` (split) | `manage_playlist` |
| `tools/reasoning.py` | `tools/sets/reasoning.py` | move |
| `tools/sampling_models.py` | merge into `tools/discovery/similar.py` | only consumer |
| `tools/search.py` | `tools/library/search.py` | move |
| `tools/sets.py` | `tools/sets/building.py` (split) | `build_set`, `rebuild_set` |
| `tools/sets.py` | `tools/sets/scoring.py` (split) | `score_transitions`, `get_set_cheat_sheet` |
| `tools/sync.py` | `tools/integrations/sync.py` | move |
| `tools/tracks.py` | `tools/library/tracks_query.py` (split) | `list_tracks`, `get_track`, `get_track_features` |
| `tools/tracks.py` | `tools/library/tracks_command.py` (split) | `manage_tracks` |
| `tools/ym.py` | `tools/integrations/ym/search.py` (split) | `ym_search`, `ym_get_tracks` |
| `tools/ym.py` | `tools/integrations/ym/catalog.py` (split) | `ym_get_album`, `ym_artist_tracks` |
| `tools/ym.py` | `tools/integrations/ym/playlists.py` (split) | `ym_playlists` |
| `tools/ym.py` | `tools/integrations/ym/likes.py` (split) | `ym_likes` |
| `tools/_helpers.py` | (delete; functionality moved to `_shared/resolvers.py` already) | rg for callers and rewire |

**Splitting rule**: when a single old file maps to multiple new files, the new files contain only the listed `@tool` functions plus any helpers used exclusively by those functions. Shared helpers move to `_shared/`.

### Task 5.3: Move trivial 1-to-1 files

Start with the easiest moves (no splits) to get the muscle memory. Each move is its own commit.

- [ ] **Step 1: `crud.py` → `sets/crud.py`**

```bash
git mv app/mcp/tools/crud.py app/mcp/tools/sets/crud.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

If snapshot fails, the tools didn't load — check that `sets/__init__.py` exists. Then commit:

```bash
git commit -m "refactor(mcp): move crud.py to sets/crud.py"
```

- [ ] **Step 2: `delivery.py` → `sets/delivery.py`**

```bash
git mv app/mcp/tools/delivery.py app/mcp/tools/sets/delivery.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git commit -m "refactor(mcp): move delivery.py to sets/delivery.py"
```

- [ ] **Step 3: `reasoning.py` → `sets/reasoning.py`**

```bash
git mv app/mcp/tools/reasoning.py app/mcp/tools/sets/reasoning.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git commit -m "refactor(mcp): move reasoning.py to sets/reasoning.py"
```

- [ ] **Step 4: `search.py` → `library/search.py`**

```bash
git mv app/mcp/tools/search.py app/mcp/tools/library/search.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git commit -m "refactor(mcp): move search.py to library/search.py"
```

- [ ] **Step 5: `import_download.py` → `discovery/ingestion.py`**

```bash
git mv app/mcp/tools/import_download.py app/mcp/tools/discovery/ingestion.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git commit -m "refactor(mcp): move import_download.py to discovery/ingestion.py"
```

- [ ] **Step 6: `sync.py` → `integrations/sync.py`**

```bash
git mv app/mcp/tools/sync.py app/mcp/tools/integrations/sync.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git commit -m "refactor(mcp): move sync.py to integrations/sync.py"
```

- [ ] **Step 7: `audio_atomic.py` → `audio/_atomic.py`**

```bash
git mv app/mcp/tools/audio_atomic.py app/mcp/tools/audio/_atomic.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

⚠️ **Critical**: the leading `_` will cause FastMCP to skip discovery. The `_atomic` tools are intentionally hidden from auto-discovery (loaded via a different code path). **Verify the snapshot still passes** — if atomic tools were previously visible in the snapshot, this rename will break it. If so, use `audio/atomic.py` (no underscore) and let server.py's `mcp.disable(tags={"atomic"})` continue handling visibility.

```bash
# if snapshot fails:
git mv app/mcp/tools/audio/_atomic.py app/mcp/tools/audio/atomic.py
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Then commit:

```bash
git commit -m "refactor(mcp): move audio_atomic.py to audio/atomic.py"
```

### Task 5.4: Split `audio.py` → `audio/analysis.py` + `audio/stems.py`

**Files:**
- Create: `app/mcp/tools/audio/analysis.py`
- Create: `app/mcp/tools/audio/stems.py`
- Delete: `app/mcp/tools/audio.py`

- [ ] **Step 1: Open `app/mcp/tools/audio.py` and identify the boundaries**

The file has 3 `@tool` functions. `analyze_track` and `analyze_batch` go to `analysis.py`. `separate_stems` goes to `stems.py`. Any helper functions used by both go to `audio/_helpers.py` (private).

- [ ] **Step 2: Create `audio/analysis.py`**

Cut the `analyze_track` and `analyze_batch` blocks into the new file. Include all imports they need at the top. Replace any `from app.mcp.tools._helpers import validate_id_or_query` with `from app.mcp.tools._shared import validate_id_or_query`.

- [ ] **Step 3: Create `audio/stems.py`**

Cut the `separate_stems` block. Same import treatment.

- [ ] **Step 4: Delete `audio.py`**

```bash
git rm app/mcp/tools/audio.py
```

- [ ] **Step 5: Run snapshot test**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS. If FAIL, check that all 3 tools registered.

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/audio/
git commit -m "refactor(mcp): split audio.py into audio/{analysis,stems}.py"
```

### Task 5.5: Split `tracks.py` → `library/tracks_query.py` + `library/tracks_command.py`

- [ ] **Step 1: Identify boundaries in `app/mcp/tools/tracks.py`**

Read tools:
- `list_tracks`, `get_track`, `get_track_features` → `tracks_query.py`
- `manage_tracks` → `tracks_command.py`

- [ ] **Step 2: Create `library/tracks_query.py`** with the read-only tools and their helpers.

- [ ] **Step 3: Create `library/tracks_command.py`** with `manage_tracks`. **Leave the if/elif body intact** — Command pattern refactor is Stage 8.

- [ ] **Step 4: `git rm app/mcp/tools/tracks.py`**

- [ ] **Step 5: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/library/
git commit -m "refactor(mcp): split tracks.py into library/tracks_{query,command}.py"
```

### Task 5.6: Split `playlists.py` → `library/playlists_query.py` + `library/playlists_command.py`

Same template as Task 5.5. Read-only `list_playlists`, `get_playlist` → `query`. `manage_playlist` → `command`. Leave the if/elif body intact.

- [ ] **Step 1: Read tools from `app/mcp/tools/playlists.py`**
- [ ] **Step 2: Create `library/playlists_query.py`**
- [ ] **Step 3: Create `library/playlists_command.py`**
- [ ] **Step 4: `git rm app/mcp/tools/playlists.py`**
- [ ] **Step 5: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/library/
git commit -m "refactor(mcp): split playlists.py into library/playlists_{query,command}.py"
```

### Task 5.7: Split `sets.py` → `sets/building.py` + `sets/scoring.py`

- [ ] **Step 1: Identify boundaries in `app/mcp/tools/sets.py`**
  - `build_set`, `rebuild_set` → `building.py`
  - `score_transitions`, `get_set_cheat_sheet` → `scoring.py`

- [ ] **Step 2: Create `sets/building.py`**
- [ ] **Step 3: Create `sets/scoring.py`**
- [ ] **Step 4: `git rm app/mcp/tools/sets.py`**
- [ ] **Step 5: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/sets/
git commit -m "refactor(mcp): split sets.py into sets/{building,scoring}.py"
```

### Task 5.8: Split `curation.py` into 4 files

- [ ] **Step 1: Identify boundaries in `app/mcp/tools/curation.py`**
  - `classify_mood` → `classification.py`
  - `audit_playlist`, `review_set_quality` → `audit.py`
  - `distribute_to_subgenres` → `distribution.py`
  - `get_library_stats` → `stats.py`

- [ ] **Step 2: Create the 4 files**, cutting each tool's code block plus its imports.

- [ ] **Step 3: `git rm app/mcp/tools/curation.py`**

- [ ] **Step 4: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/curation/
git commit -m "refactor(mcp): split curation.py into 4 files (classification, audit, distribution, stats)"
```

### Task 5.9: Split `discovery.py` → `similar.py` + `expansion.py`

- [ ] **Step 1: Identify boundaries**
  - `find_similar_tracks` → `similar.py`
  - `expand_playlist_ym`, `filter_by_feedback` → `expansion.py`

- [ ] **Step 2: Merge `sampling_models.py` content into `discovery/similar.py`** (it's the only consumer per the spec).

- [ ] **Step 3: Create the 2 files**

- [ ] **Step 4: `git rm app/mcp/tools/discovery.py app/mcp/tools/sampling_models.py`**

- [ ] **Step 5: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/discovery/
git commit -m "refactor(mcp): split discovery.py into discovery/{similar,expansion}.py"
```

### Task 5.10: Split `admin.py` → `visibility.py` + `platforms.py`

- [ ] **Step 1: Identify boundaries**
  - `unlock_tools` → `visibility.py`
  - `list_platforms` → `platforms.py`

- [ ] **Step 2: Create the 2 files**
- [ ] **Step 3: `git rm app/mcp/tools/admin.py`**
- [ ] **Step 4: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/admin/
git commit -m "refactor(mcp): split admin.py into admin/{visibility,platforms}.py"
```

### Task 5.11: Split `ym.py` into 4 files

This is the largest split (339 lines → 4 files).

- [ ] **Step 1: Identify boundaries**
  - `ym_search`, `ym_get_tracks` → `search.py`
  - `ym_get_album`, `ym_artist_tracks` → `catalog.py`
  - `ym_playlists` → `playlists.py`
  - `ym_likes` → `likes.py`

- [ ] **Step 2: Create the 4 files** in `app/mcp/tools/integrations/ym/`. **Leave the if/elif bodies of `ym_playlists` and `ym_likes` intact** — Command pattern refactor is Stages 10-11.

- [ ] **Step 3: `git rm app/mcp/tools/ym.py`**

- [ ] **Step 4: Snapshot test + commit**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
git add app/mcp/tools/integrations/ym/
git commit -m "refactor(mcp): split ym.py into integrations/ym/{search,catalog,playlists,likes}.py"
```

### Task 5.12: Delete `_helpers.py`

- [ ] **Step 1: Find remaining callers**

```bash
uv run rg "from app\.mcp\.tools\._helpers import" .
```

- [ ] **Step 2: Rewrite each caller** to import from `_shared`:

```python
# before
from app.mcp.tools._helpers import resolve_track_id, validate_id_or_query

# after
from app.mcp.tools._shared import resolve_track_id, validate_id_or_query
```

- [ ] **Step 3: `git rm app/mcp/tools/_helpers.py`**

- [ ] **Step 4: Run full check**

```bash
make check
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(mcp): remove _helpers.py — superseded by _shared

All callers now import from app.mcp.tools._shared. Functionality
is identical (single source of truth in _shared/resolvers.py).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 5.13: Stage 5 verification gate

- [ ] **Step 1: Confirm `app/mcp/tools/` top level is empty of `.py` files**

```bash
ls app/mcp/tools/*.py 2>/dev/null
```

Expected: nothing (or only `__init__.py`).

- [ ] **Step 2: Run full check + snapshot**

```bash
make check
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: all green, snapshot diff = 0.

- [ ] **Step 3: No new commit** — this is verification only.

---

## Stage 5b: Move existing tests to mirror new layout

**Purpose:** Tests now point at the old paths. Update them.

### Task 5b.1: Move test files

- [ ] **Step 1: Find existing tool tests**

```bash
uv run rg -l "from app\.mcp\.tools\." tests/
ls tests/test_mcp/ 2>/dev/null
```

- [ ] **Step 2: For each test file, update its import paths**

Use the table in Task 5.2 to find new locations. Example:

```python
# before
from app.mcp.tools.tracks import list_tracks

# after
from app.mcp.tools.library.tracks_query import list_tracks
```

If a test file covers a single domain, also `git mv` it into the corresponding `tests/test_mcp/tools/<domain>/` directory.

- [ ] **Step 3: Run the relocated tests**

```bash
uv run pytest tests/test_mcp/ -v
```

Expected: all green (note: most MCP tool tests use the FastMCP `Client` fixture and call tools by *name*, so import path changes are limited).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "$(cat <<'EOF'
test(mcp): mirror new tools layout in test directory

Update import paths in tool tests and move them under
tests/test_mcp/tools/<domain>/ to match the new vertical-slice
layout.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 6: Apply `@map_errors` decorator

**Purpose:** Replace per-tool `try/except domain → ToolError` boilerplate with the decorator.

### Task 6.1: Audit current error handling

- [ ] **Step 1: Find tools with manual error mapping**

```bash
uv run rg -l "except (NotFoundError|ValidationError|ConflictError)" app/mcp/tools/
```

For each file in the list, you will:
1. Add `from app.mcp.tools._shared import map_errors` to imports
2. Add `@map_errors` directly under each `@tool` decorator
3. Delete the `try/except` blocks that map to `ToolError`

### Task 6.2: Apply decorator file by file

For each file from Task 6.1, do one commit per file:

- [ ] **Step 1: Open the file and add `@map_errors` to every `@tool`**

Order: `@tool(...)` MUST be the outermost decorator (FastMCP needs to see the original function signature). `@map_errors` goes between `@tool` and the function:

```python
@tool(tags={"core"}, annotations={"readOnlyHint": True})
@map_errors
async def get_track(...) -> TrackStandard:
    ...
```

- [ ] **Step 2: Remove the now-redundant try/except blocks** inside each tool body.

- [ ] **Step 3: Run the targeted tests**

```bash
uv run pytest tests/test_mcp/tools/<domain>/ -v
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: green. The catalog snapshot must still match (decorator doesn't change schema).

- [ ] **Step 4: Commit per file**

```bash
git commit -m "refactor(mcp): apply @map_errors to <domain>/<file>.py tools"
```

### Task 6.3: Stage 6 verification

- [ ] **Step 1: Confirm no manual domain-error mapping remains in tools**

```bash
uv run rg "except NotFoundError" app/mcp/tools/
```

Expected: empty result.

- [ ] **Step 2: Full check**

```bash
make check
```

---

## Stage 7: Apply `ResponseBuilder`

**Purpose:** Replace ad-hoc `PaginatedResponse[T](items=..., next_cursor=..., total=...)` construction with `ResponseBuilder.paginated(...)`.

### Task 7.1: Audit ad-hoc PaginatedResponse construction

- [ ] **Step 1: Find every site**

```bash
uv run rg "PaginatedResponse\[" app/mcp/tools/
```

### Task 7.2: Replace each site

For each file from Task 7.1:

- [ ] **Step 1: Add import**

```python
from app.mcp.tools._shared import ResponseBuilder
```

- [ ] **Step 2: Replace the construction**

```python
# before
return PaginatedResponse[TrackBrief](
    items=tracks_brief,
    next_cursor=page.next_cursor,
    total=page.total,
)

# after
return ResponseBuilder.paginated(
    items=tracks_brief,
    next_cursor=page.next_cursor,
    total=page.total,
    item_type=TrackBrief,
)
```

- [ ] **Step 3: Run tests for the touched file**

```bash
uv run pytest tests/test_mcp/tools/<domain>/ tests/test_mcp/test_tool_catalog_snapshot.py -v
```

- [ ] **Step 4: Commit per file**

```bash
git commit -m "refactor(mcp): use ResponseBuilder in <domain>/<file>.py"
```

### Task 7.3: Stage 7 verification

- [ ] **Step 1: Confirm no direct `PaginatedResponse[` construction in tools**

```bash
uv run rg "PaginatedResponse\[" app/mcp/tools/
```

Expected: empty result (only `_shared/responses.py` may reference the type).

- [ ] **Step 2: Full check**

```bash
make check
```

---

## Stage 8: Command pattern for `manage_tracks`

**Purpose:** Replace the if/elif body of `library/tracks_command.py:manage_tracks` with a Command-pattern dispatch.

### Task 8.1: Define `ToolCommand` ABC

**Files:**
- Create: `app/mcp/tools/library/_commands/__init__.py`
- Create: `app/mcp/tools/library/_commands/base.py`
- Create: `tests/test_mcp/tools/library/_commands/__init__.py`
- Create: `tests/test_mcp/tools/library/_commands/test_base.py`

- [ ] **Step 1: Write failing test**

`tests/test_mcp/tools/library/_commands/test_base.py`:

```python
"""Tests for ToolCommand ABC."""

from __future__ import annotations

import pytest

from app.mcp.tools.library._commands.base import ToolCommand

def test_subclass_must_define_name() -> None:
    class NoName(ToolCommand):
        async def execute(self, args, ctx, deps):
            return {}

    with pytest.raises((TypeError, AttributeError)):
        NoName()  # type: ignore[abstract]

def test_subclass_must_implement_execute() -> None:
    class NoExec(ToolCommand):
        name = "noop"

    with pytest.raises(TypeError):
        NoExec()  # type: ignore[abstract]

def test_concrete_subclass_works() -> None:
    class Echo(ToolCommand):
        name = "echo"

        async def execute(self, args, ctx, deps):
            return args

    cmd = Echo()
    assert cmd.name == "echo"
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
uv run pytest tests/test_mcp/tools/library/_commands/test_base.py -v
```

- [ ] **Step 3: Implement `base.py`**

```python
"""Base class for library tool commands (Command pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from fastmcp.server.context import Context

class ToolCommand(ABC):
    """A single action within a multi-action tool.

    Subclasses set `name` (the action string) and implement `execute`.
    Tools dispatch to subclasses via a registry dict.
    """

    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "name") or not isinstance(getattr(cls, "name", None), str):
            raise AttributeError(
                f"{cls.__name__} must define a `name` class attribute (str)"
            )

    @abstractmethod
    async def execute(
        self,
        args: dict[str, Any],
        ctx: "Context | None",
        deps: dict[str, Any],
    ) -> Any:
        """Execute this command. `deps` carries injected services."""
```

⚠️ **Note**: Python's `__init_subclass__` runs before the abstract-method check and may collide with the abstract `name` ClassVar. If the tests don't pass with this design, drop `__init_subclass__` and rely on `name = ""` default + a runtime check at registry build time.

- [ ] **Step 4: Run tests, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/library/_commands/test_base.py -v
```

- [ ] **Step 5: Commit**

```bash
mkdir -p app/mcp/tools/library/_commands tests/test_mcp/tools/library/_commands
touch app/mcp/tools/library/_commands/__init__.py tests/test_mcp/tools/library/_commands/__init__.py
git add app/mcp/tools/library/_commands/ tests/test_mcp/tools/library/_commands/
git commit -m "feat(mcp): add ToolCommand ABC for library command pattern"
```

### Task 8.2: Implement track commands

**Files:**
- Create: `app/mcp/tools/library/_commands/track_commands.py`
- Create: `tests/test_mcp/tools/library/_commands/test_track_commands.py`

- [ ] **Step 1: Read the existing if/elif body** in `app/mcp/tools/library/tracks_command.py:manage_tracks` and identify the 4 actions (`create`, `update`, `archive`, `unarchive`) and the data fields each consumes.

- [ ] **Step 2: Write failing tests for each command**

Skeleton (fill in concrete fields based on actual TrackService method signatures):

```python
"""Tests for track command classes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.mcp.tools.library._commands.track_commands import (
    ArchiveTrackCommand,
    CreateTrackCommand,
    TRACK_COMMANDS,
    UnarchiveTrackCommand,
    UpdateTrackCommand,
)

def test_registry_contains_all_commands() -> None:
    assert set(TRACK_COMMANDS.keys()) == {"create", "update", "archive", "unarchive"}

@pytest.mark.asyncio
async def test_create_track_command_calls_service() -> None:
    svc = AsyncMock()
    svc.create = AsyncMock(return_value={"id": 1})
    cmd = CreateTrackCommand()
    result = await cmd.execute(
        args={"data": {"title": "Test"}}, ctx=None, deps={"track_svc": svc},
    )
    assert result == {"id": 1}
    svc.create.assert_awaited_once_with({"title": "Test"})

@pytest.mark.asyncio
async def test_update_track_command_calls_service() -> None:
    svc = AsyncMock()
    svc.update = AsyncMock(return_value={"id": 1, "title": "X"})
    cmd = UpdateTrackCommand()
    result = await cmd.execute(
        args={"data": {"id": 1, "title": "X"}}, ctx=None, deps={"track_svc": svc},
    )
    svc.update.assert_awaited_once()

@pytest.mark.asyncio
async def test_archive_track_command_calls_service() -> None:
    svc = AsyncMock()
    svc.archive = AsyncMock(return_value=None)
    cmd = ArchiveTrackCommand()
    result = await cmd.execute(
        args={"data": {"id": 1}}, ctx=None, deps={"track_svc": svc},
    )
    svc.archive.assert_awaited_once_with(1)

@pytest.mark.asyncio
async def test_unarchive_track_command_calls_service() -> None:
    svc = AsyncMock()
    svc.unarchive = AsyncMock(return_value=None)
    cmd = UnarchiveTrackCommand()
    await cmd.execute(args={"data": {"id": 1}}, ctx=None, deps={"track_svc": svc})
    svc.unarchive.assert_awaited_once_with(1)
```

Adjust assertions to match the real `TrackService` method signatures (read them first).

- [ ] **Step 3: Run tests, expect FAIL**

- [ ] **Step 4: Implement `track_commands.py`**

```python
"""Track manage_* commands (Command pattern)."""

from __future__ import annotations

from typing import Any

from app.mcp.tools.library._commands.base import ToolCommand

class CreateTrackCommand(ToolCommand):
    name = "create"

    async def execute(self, args, ctx, deps):
        svc = deps["track_svc"]
        return await svc.create(args["data"])

class UpdateTrackCommand(ToolCommand):
    name = "update"

    async def execute(self, args, ctx, deps):
        svc = deps["track_svc"]
        return await svc.update(args["data"])

class ArchiveTrackCommand(ToolCommand):
    name = "archive"

    async def execute(self, args, ctx, deps):
        svc = deps["track_svc"]
        track_id = args["data"]["id"]
        return await svc.archive(track_id)

class UnarchiveTrackCommand(ToolCommand):
    name = "unarchive"

    async def execute(self, args, ctx, deps):
        svc = deps["track_svc"]
        track_id = args["data"]["id"]
        return await svc.unarchive(track_id)

TRACK_COMMANDS: dict[str, type[ToolCommand]] = {
    cmd.name: cmd
    for cmd in (
        CreateTrackCommand,
        UpdateTrackCommand,
        ArchiveTrackCommand,
        UnarchiveTrackCommand,
    )
}
```

Reconcile the body of each `execute` with the actual logic from `manage_tracks`'s if/elif body — this skeleton assumes simple delegation, but the original may do more (e.g. validation, response formatting). Preserve every behavior.

- [ ] **Step 5: Run tests, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/library/_commands/track_commands.py tests/test_mcp/tools/library/_commands/test_track_commands.py
git commit -m "feat(mcp): add track manage_* commands"
```

### Task 8.3: Wire `manage_tracks` to use the registry

**Files:**
- Modify: `app/mcp/tools/library/tracks_command.py`

- [ ] **Step 1: Replace the if/elif body with dispatch**

```python
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_track_service
from app.mcp.tools._shared import map_errors
from app.mcp.tools.library._commands.track_commands import TRACK_COMMANDS
from app.services.track_service import TrackService  # for type hint only

@tool(tags={"core"}, annotations={"readOnlyHint": False})
@map_errors
async def manage_tracks(
    action: str,
    data: dict | None = None,
    ctx: Context | None = None,
    track_svc: TrackService = ...,  # Depends(get_track_service) — keep existing wiring
) -> dict:
    """Create, update, archive, or unarchive tracks.

    Actions: create, update, archive, unarchive.
    Action-specific fields go in `data`.
    """
    cmd_cls = TRACK_COMMANDS.get(action)
    if cmd_cls is None:
        raise ToolError(
            f"Unknown action: {action}. "
            f"Allowed: {sorted(TRACK_COMMANDS.keys())}"
        )
    return await cmd_cls().execute(
        args={"data": data or {}},
        ctx=ctx,
        deps={"track_svc": track_svc},
    )
```

⚠️ Keep the **exact same `Depends()` wiring** that existed in the original `manage_tracks` — copy it from the pre-refactor version. The `...` placeholder above is a marker, not real code.

⚠️ Keep the **exact same parameter names and type hints** for `action`, `data` so the input schema is byte-stable.

- [ ] **Step 2: Run snapshot test**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

If FAIL, the schema drifted — compare the new function signature to the old one and reconcile.

- [ ] **Step 3: Run library tests**

```bash
uv run pytest tests/test_mcp/tools/library/ -v
```

- [ ] **Step 4: Commit**

```bash
git add app/mcp/tools/library/tracks_command.py
git commit -m "refactor(mcp): manage_tracks uses Command pattern dispatch"
```

---

## Stage 9: Command pattern for `manage_playlist`

Same template as Stage 8. The 6 actions are `create`, `update`, `delete`, `add_tracks`, `remove_tracks`, `reorder`.

### Task 9.1: Implement playlist commands

**Files:**
- Create: `app/mcp/tools/library/_commands/playlist_commands.py`
- Create: `tests/test_mcp/tools/library/_commands/test_playlist_commands.py`

- [ ] **Step 1: Read the existing if/elif body** in `app/mcp/tools/library/playlists_command.py:manage_playlist` to identify the 6 action signatures.

- [ ] **Step 2: Write failing tests** — one per command, asserting it calls the right `PlaylistService` method with the right args.

Use the same skeleton as Task 8.2 Step 2, with classes `CreatePlaylistCommand`, `UpdatePlaylistCommand`, `DeletePlaylistCommand`, `AddTracksCommand`, `RemoveTracksCommand`, `ReorderTracksCommand`.

- [ ] **Step 3: Run tests, expect FAIL**

```bash
uv run pytest tests/test_mcp/tools/library/_commands/test_playlist_commands.py -v
```

- [ ] **Step 4: Implement `playlist_commands.py`**

```python
"""Playlist manage_* commands (Command pattern)."""

from __future__ import annotations

from typing import Any

from app.mcp.tools.library._commands.base import ToolCommand

class CreatePlaylistCommand(ToolCommand):
    name = "create"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.create(args["data"])

class UpdatePlaylistCommand(ToolCommand):
    name = "update"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.update(args["data"])

class DeletePlaylistCommand(ToolCommand):
    name = "delete"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.delete(args["data"]["id"])

class AddTracksCommand(ToolCommand):
    name = "add_tracks"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.add_tracks(
            playlist_id=args["data"]["playlist_id"],
            track_refs=args["track_refs"],
        )

class RemoveTracksCommand(ToolCommand):
    name = "remove_tracks"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.remove_tracks(
            playlist_id=args["data"]["playlist_id"],
            track_refs=args["track_refs"],
        )

class ReorderTracksCommand(ToolCommand):
    name = "reorder"

    async def execute(self, args, ctx, deps):
        svc = deps["playlist_svc"]
        return await svc.reorder(
            playlist_id=args["data"]["playlist_id"],
            positions=args["positions"],
        )

PLAYLIST_COMMANDS: dict[str, type[ToolCommand]] = {
    cmd.name: cmd
    for cmd in (
        CreatePlaylistCommand,
        UpdatePlaylistCommand,
        DeletePlaylistCommand,
        AddTracksCommand,
        RemoveTracksCommand,
        ReorderTracksCommand,
    )
}
```

Same caveat as Task 8.2: reconcile each `execute` body with the **actual** code from the original if/elif. Preserve all current behavior — validation, error messages, response shape.

- [ ] **Step 5: Run tests, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/library/_commands/playlist_commands.py tests/test_mcp/tools/library/_commands/test_playlist_commands.py
git commit -m "feat(mcp): add playlist manage_* commands"
```

### Task 9.2: Wire `manage_playlist`

**Files:**
- Modify: `app/mcp/tools/library/playlists_command.py`

- [ ] **Step 1: Replace if/elif with dispatch** (same template as Task 8.3)

```python
@tool(tags={"core"}, annotations={"readOnlyHint": False})
@map_errors
async def manage_playlist(
    action: str,
    data: dict | None = None,
    track_refs: list | None = None,
    positions: list | None = None,
    ctx: Context | None = None,
    playlist_svc: PlaylistService = Depends(get_playlist_service),
) -> dict:
    """..."""
    cmd_cls = PLAYLIST_COMMANDS.get(action)
    if cmd_cls is None:
        raise ToolError(
            f"Unknown action: {action}. "
            f"Allowed: {sorted(PLAYLIST_COMMANDS.keys())}"
        )
    return await cmd_cls().execute(
        args={"data": data or {}, "track_refs": track_refs, "positions": positions},
        ctx=ctx,
        deps={"playlist_svc": playlist_svc},
    )
```

Match the **original parameter signature exactly** (read it first).

- [ ] **Step 2: Snapshot test + library tests**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py tests/test_mcp/tools/library/ -v
```

- [ ] **Step 3: Commit**

```bash
git add app/mcp/tools/library/playlists_command.py
git commit -m "refactor(mcp): manage_playlist uses Command pattern dispatch"
```

---

## Stage 10: Command pattern for `ym_playlists`

The 8 actions are `get`, `list`, `create`, `rename`, `delete`, `add_tracks`, `remove_tracks`, `get_tracks`.

### Task 10.1: Define YM command base

**Files:**
- Create: `app/mcp/tools/integrations/ym/_commands/__init__.py`
- Create: `app/mcp/tools/integrations/ym/_commands/base.py`

- [ ] **Step 1: Create directory + base class**

```bash
mkdir -p app/mcp/tools/integrations/ym/_commands tests/test_mcp/tools/integrations/ym/_commands
touch app/mcp/tools/integrations/ym/_commands/__init__.py tests/test_mcp/tools/integrations/ym/_commands/__init__.py
```

`app/mcp/tools/integrations/ym/_commands/base.py`:

```python
"""Base class for YM tool commands (Command pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from fastmcp.server.context import Context

    from app.ym.client import YandexMusicClient

class YMCommand(ABC):
    """A single action within a multi-action YM tool."""

    name: ClassVar[str] = ""

    @abstractmethod
    async def execute(
        self,
        args: dict[str, Any],
        ctx: "Context | None",
        ym: "YandexMusicClient",
    ) -> Any: ...
```

- [ ] **Step 2: Quick smoke test**

`tests/test_mcp/tools/integrations/__init__.py`, `tests/test_mcp/tools/integrations/ym/__init__.py`, `tests/test_mcp/tools/integrations/ym/_commands/__init__.py` — create as empty.

`tests/test_mcp/tools/integrations/ym/_commands/test_base.py`:

```python
"""Smoke test for YMCommand ABC."""

from __future__ import annotations

import pytest

from app.mcp.tools.integrations.ym._commands.base import YMCommand

def test_must_implement_execute() -> None:
    class NoExec(YMCommand):
        name = "noop"

    with pytest.raises(TypeError):
        NoExec()  # type: ignore[abstract]

def test_concrete_subclass() -> None:
    class Echo(YMCommand):
        name = "echo"

        async def execute(self, args, ctx, ym):
            return args

    assert Echo().name == "echo"
```

- [ ] **Step 3: Run, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/integrations/ym/_commands/test_base.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/mcp/tools/integrations/ym/_commands/ tests/test_mcp/tools/integrations/
git commit -m "feat(mcp): add YMCommand ABC"
```

### Task 10.2: Implement YM playlist commands

**Files:**
- Create: `app/mcp/tools/integrations/ym/_commands/playlist_commands.py`
- Create: `tests/test_mcp/tools/integrations/ym/_commands/test_playlist_commands.py`

- [ ] **Step 1: Read existing if/elif** in `app/mcp/tools/integrations/ym/playlists.py:ym_playlists` and identify the 8 actions and which `YandexMusicClient` methods each calls.

- [ ] **Step 2: Write failing tests** for all 8 commands using the AsyncMock pattern from Task 8.2 Step 2.

Class names: `GetPlaylistCommand`, `ListPlaylistsCommand`, `CreatePlaylistCommand`, `RenamePlaylistCommand`, `DeletePlaylistCommand`, `AddTracksCommand`, `RemoveTracksCommand`, `GetPlaylistTracksCommand`. Registry: `YM_PLAYLIST_COMMANDS`.

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement** `playlist_commands.py` — one class per action, each delegating to the corresponding `ym.<method>(...)` call. Mirror the original if/elif behavior exactly.

- [ ] **Step 5: Run, expect PASS**

```bash
uv run pytest tests/test_mcp/tools/integrations/ym/_commands/test_playlist_commands.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/integrations/ym/_commands/playlist_commands.py tests/test_mcp/tools/integrations/ym/_commands/test_playlist_commands.py
git commit -m "feat(mcp): add YM playlist commands (8 actions)"
```

### Task 10.3: Wire `ym_playlists`

**Files:**
- Modify: `app/mcp/tools/integrations/ym/playlists.py`

- [ ] **Step 1: Replace if/elif with dispatch** (template as in Task 8.3, but using `YM_PLAYLIST_COMMANDS` and `ym` dependency instead of `track_svc`).

⚠️ Match the **original `ym_playlists` parameter signature** exactly.

- [ ] **Step 2: Snapshot test**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

- [ ] **Step 3: Run integrations tests**

```bash
uv run pytest tests/test_mcp/tools/integrations/ -v
```

- [ ] **Step 4: Commit**

```bash
git add app/mcp/tools/integrations/ym/playlists.py
git commit -m "refactor(mcp): ym_playlists uses Command pattern dispatch"
```

---

## Stage 11: Command pattern for `ym_likes`

3 actions: `get_liked`, `add`, `remove`.

### Task 11.1: Implement and wire YM like commands

**Files:**
- Create: `app/mcp/tools/integrations/ym/_commands/like_commands.py`
- Create: `tests/test_mcp/tools/integrations/ym/_commands/test_like_commands.py`
- Modify: `app/mcp/tools/integrations/ym/likes.py`

- [ ] **Step 1: Read existing if/elif** in `likes.py`.

- [ ] **Step 2: Write failing tests** for `GetLikedCommand`, `AddLikeCommand`, `RemoveLikeCommand`, registry `YM_LIKE_COMMANDS`.

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement `like_commands.py`** — 3 classes mirroring the original behavior.

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: Replace if/elif in `likes.py`** with dispatch.

- [ ] **Step 7: Snapshot + integrations tests**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py tests/test_mcp/tools/integrations/ -v
```

- [ ] **Step 8: Commit**

```bash
git add app/mcp/tools/integrations/ym/_commands/like_commands.py tests/test_mcp/tools/integrations/ym/_commands/test_like_commands.py app/mcp/tools/integrations/ym/likes.py
git commit -m "refactor(mcp): ym_likes uses Command pattern (3 actions)"
```

---

## Stage 12: Hardcoded values audit + LifespanRegistry wiring

### Task 12.1: Audit hardcoded values in tools

- [ ] **Step 1: Find numeric magic values**

```bash
uv run rg "limit(=|: int = )[0-9]+" app/mcp/tools/
uv run rg "top_n(=|: int = )[0-9]+" app/mcp/tools/
uv run rg "timeout(=|: int = )[0-9]+" app/mcp/tools/
```

- [ ] **Step 2: For each finding, decide**:
  - **Settings**: if it's environment-tunable → move to `app/config.py:Settings` and reference as `settings.X`
  - **Constant**: if it's a domain rule → add to `app/core/constants.py`
  - **Tool-local**: if it's only meaningful inside the tools layer → create `app/mcp/tools/_shared/constants.py` and put it there

- [ ] **Step 3: Create `_shared/constants.py` if needed**

```python
"""Tool-layer constants (not user-tunable, not domain rules)."""

from __future__ import annotations

# Default top-N for transition scoring suggestions
DEFAULT_SCORING_TOP_N = 5
# Default `count` for reasoning tools that suggest alternatives
DEFAULT_SUGGESTION_COUNT = 3
```

- [ ] **Step 4: Replace each magic value with a reference**

Per file, swap `top_n: int = 5` for `top_n: int = DEFAULT_SCORING_TOP_N` (or `settings.scoring_top_n`, etc.).

- [ ] **Step 5: Snapshot test**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

⚠️ Default values are part of the input schema. If you change a default, the snapshot will fail. Either:
- Keep the same default value (the constant just gives it a name) → snapshot stays green
- Or rebaseline the snapshot in the same commit (only if the value change is intentional and approved)

- [ ] **Step 6: Commit**

```bash
git commit -m "refactor(mcp): replace magic values with named constants"
```

### Task 12.2: Wire `LifespanRegistry` into `dependencies.py`

**Files:**
- Modify: `app/mcp/dependencies.py`

- [ ] **Step 1: Replace string-key access with `LifespanRegistry`**

```python
# before
def get_ym_client() -> YandexMusicClient:
    ctx = get_context()
    return ctx.lifespan_context["ym_client"]

# after
from app.mcp.tools._shared import LifespanRegistry

def get_ym_client() -> YandexMusicClient:
    ctx = get_context()
    return LifespanRegistry.ym_client(ctx)
```

Same pattern for `get_analyzer_registry`, `get_transition_cache`. The public DI factory names stay identical — only the internal lookup changes.

- [ ] **Step 2: Run full check**

```bash
make check
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

- [ ] **Step 3: Commit**

```bash
git add app/mcp/dependencies.py
git commit -m "$(cat <<'EOF'
refactor(mcp): use LifespanRegistry in dependencies.py

Replaces magic-string lifespan_context lookups with type-safe
classmethod accessors. Public DI factory names unchanged.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Stage 13: Final audit

### Task 13.1: File size cap audit

- [ ] **Step 1: Find files over 250 lines**

```bash
find app/mcp/tools -name "*.py" | xargs wc -l | sort -rn | awk '$1 > 250'
find app/services/{import_,discovery_,metadata,sync} -name "*.py" 2>/dev/null | xargs wc -l | sort -rn | awk '$1 > 250'
```

Expected: empty result.

- [ ] **Step 2: If anything is >250 lines**, split it. Each split = its own commit. Re-run the snapshot test after each split.

### Task 13.2: Duplicate scan

- [ ] **Step 1: Search for known duplicate patterns**

```bash
# validate_id_or_query — should only be in _shared
uv run rg "def validate_id_or_query" app/mcp/

# Should be in _shared/resolvers.py only:
# app/mcp/tools/_shared/resolvers.py:def validate_id_or_query(...)

# resolve_track_id — same
uv run rg "def resolve_track_id" app/mcp/

# PaginatedResponse[ — should not appear in tools
uv run rg "PaginatedResponse\[" app/mcp/tools/

# except NotFoundError — should not appear in tools
uv run rg "except NotFoundError" app/mcp/tools/

# manual ctx.lifespan_context["..."] in tools
uv run rg 'lifespan_context\[' app/mcp/tools/
```

Expected: each grep returns either nothing or only the canonical `_shared/...` location.

### Task 13.3: Tool count + snapshot diff

- [ ] **Step 1: Run snapshot test**

```bash
uv run pytest tests/test_mcp/test_tool_catalog_snapshot.py -v
```

Expected: PASS (zero diff against the Stage 0 baseline).

- [ ] **Step 2: Run full `make check`**

```bash
make check
```

Expected: lint clean, mypy clean, all tests green.

- [ ] **Step 3: Boot the server**

```bash
uv run python -c "
import asyncio
from app.server import mcp

async def main():
    tools = await mcp.get_tools()
    print(f'Tool count: {len(tools)}')
    assert len(tools) == 50, f'Expected 50, got {len(tools)}'

asyncio.run(main())
"
```

Expected: `Tool count: 50` (or whatever the baseline count is).

- [ ] **Step 4: Boot the REST API as a smoke test**

```bash
uv run --extra http uvicorn serve_http:api --host 127.0.0.1 --port 8001 &
SERVER_PID=$!
sleep 3
curl -sf http://127.0.0.1:8001/api/health | head -20
curl -sf http://127.0.0.1:8001/api/tools | python -c "import json, sys; d = json.load(sys.stdin); print(f'REST tool count: {len(d.get(\"tools\", []))}')"
kill $SERVER_PID
```

Expected: health OK, REST tool count matches MCP tool count.

### Task 13.4: Metrics review

- [ ] **Step 1: Compute the after-numbers**

```bash
echo "=== Files in app/mcp/tools/ (recursive) ==="
find app/mcp/tools -name "*.py" -not -path "*/__pycache__/*" | wc -l

echo "=== Largest tool file ==="
find app/mcp/tools -name "*.py" -not -path "*/__pycache__/*" | xargs wc -l | sort -rn | head -3

echo "=== God-files in services (>300 lines) ==="
find app/services -name "*.py" -not -path "*/__pycache__/*" | xargs wc -l | sort -rn | awk '$1 > 300'
```

- [ ] **Step 2: Compare against spec §10 metrics table**

| Metric | Target | Actual |
|---|---|---|
| Files in `app/mcp/tools/` (recursive) | ~40 | (fill in) |
| Largest tool file | ≤200 | (fill in) |
| God-files in `app/services/` (>300 lines) | 0 | (fill in) |
| Tool catalog snapshot diff | 0 | 0 |

If any metric is off, file a follow-up issue but don't block — the structural goal is met.

### Task 13.5: Final commit + branch ready for review

- [ ] **Step 1: Confirm clean working tree**

```bash
git status
```

Expected: clean.

- [ ] **Step 2: Show the commit log**

```bash
git log --oneline main..HEAD | head -50
```

Expected: a clean sequence of refactor commits, one per task.

- [ ] **Step 3: Write a summary file (optional)**

Create `docs/superpowers/reports/2026-04-XX-mcp-tools-refactor-report.md` with:
- Total commits
- Lines changed (`git diff --stat main..HEAD`)
- Metrics table from Task 13.4
- Any deviations from the spec
- Any open follow-ups

- [ ] **Step 4: Push and open PR**

(If working in a worktree, push and open PR per the project workflow.)

---

## Self-review

Spec coverage check (against `docs/superpowers/specs/2026-04-07-mcp-tools-refactor-design.md`):

| Spec § | Requirement | Plan task |
|---|---|---|
| §3.1 | `_shared/` package with 7 modules | Stage 1 (Tasks 1.1-1.7) |
| §3.1 | `library/`, `sets/`, `audio/`, `curation/`, `discovery/`, `integrations/`, `admin/` dirs | Stage 5 (Tasks 5.1-5.13) |
| §3.1 | `_atomic.py` for hidden audio tools | Task 5.3 Step 7 |
| §3.1 | `_commands/` subpackages for Command pattern | Stages 8-11 |
| §3.2 | `services/import_/`, `discovery_/`, `metadata/`, `sync/` splits | Stages 3, 4a, 4b, 4c |
| §3.3 | Command pattern | Stages 8-11 |
| §3.3 | Builder pattern (`ResponseBuilder`) | Tasks 1.3, 7.1-7.3 |
| §3.3 | Facade pattern (services) | Stages 3, 4a-4c |
| §3.3 | Strategy pattern (discovery) | Task 4a (implicit — formalized only if it simplifies) |
| §3.3 | Template Method (`@map_errors`) | Tasks 1.4, 6.1-6.3 |
| §3.3 | Adapter (`_shared/parsing.py`) | Task 1.6 |
| §3.3 | Registry (`LifespanRegistry`) | Tasks 1.5, 12.2 |
| §3.4 | `_shared` module details | Tasks 1.2-1.6 |
| §3.5 | Command pattern detail | Stages 8-11 |
| §3.6 | Stable contracts | Stage 0 + snapshot test gate everywhere |
| §4 | Constants/hardcoded audit | Task 12.1 |
| §5 | `CLAUDE.md` for tools layer | Stage 2 |
| §6 | Tests structure | Tasks 5b.1, 1.2-1.6, 8.x-11.x |
| §7 | 14 stages | Stages 0-13 ✓ |
| §10 | Metrics success | Task 13.4 |

**Gaps found and patched during self-review:**
- Stage 0 added an explicit baseline-snapshot fixture so every later stage has a measurable contract gate.
- Task 5.3 Step 7 explicitly handles the `_atomic.py` vs `atomic.py` ambiguity (FastMCP `_`-prefix skip vs hidden-via-tag).
- Task 8.1 Step 3 includes a `__init_subclass__` caveat — the abstract method check vs class attr ordering can collide; alternative is documented inline.
- Task 12.1 Step 5 explicitly notes that changing default values breaks the snapshot, and what to do about it.

**Placeholder scan**: searched the plan for "TBD", "TODO", "implement later", "fill in details", "similar to Task N", "add appropriate". Findings:
- Task 3.3 Step 2 says "same constructor signature as before" — this is correct because the executor must read the old file first; the constructor is *not* placeholder, it's "preserve exactly what's there".
- Stages 4a/4b/4c reference "same template as Stage 3 Task 3.3 Step 2" — acceptable because Stage 3 is the canonical example and the template is short. Each sub-task still spells out the inventory + classification + mv + verify cycle.
- Stages 9, 10, 11 reference "template as in Task 8.3" — the dispatch boilerplate is given inline in 8.3 and the parameter signature requirement is explicit.

**Type consistency check**:
- `ToolCommand.execute(self, args, ctx, deps)` (Task 8.1) vs `YMCommand.execute(self, args, ctx, ym)` (Task 10.1) — intentionally different (`deps` dict vs raw `ym`); each has its own ABC. ✓
- `TRACK_COMMANDS`, `PLAYLIST_COMMANDS`, `YM_PLAYLIST_COMMANDS`, `YM_LIKE_COMMANDS` — naming consistent. ✓
- `LifespanRegistry.ym_client / analyzer_registry / transition_cache` — same names in tests (Task 1.5) and dependencies wiring (Task 12.2). ✓
- `ResponseBuilder.paginated(*, items, next_cursor, total, item_type)` — same kwargs in tests (Task 1.3), in CLAUDE.md (Stage 2), and in Stage 7 usage. ✓
- `@map_errors` decorator order: `@tool` outermost, `@map_errors` between tool and function — same in CLAUDE.md (Stage 2) and Task 6.2. ✓

Plan ready for execution.

---

## Execution choice

**Plan complete and saved to `docs/superpowers/plans/2026-04-07-mcp-tools-refactor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review (code-reviewer + verification), fast iteration, clean context.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**

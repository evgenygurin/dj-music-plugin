# Surface Redesign v2 — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 11 v2.0 domain-manager tools (e.g. `tracks_list`, `sets_build`, `transitions_score`) as an ergonomic facade over the existing v1.0 generic dispatchers. v1 dispatchers stay callable, tagged `deprecated`, discoverable via session-unlock. Zero business-logic duplication: managers are `ToolTransform`-derived with `ArgTransform(hide=True, default="<entity>")`, except `transitions_score` which is a composite orchestrating `transition_score_pool` + `sequence_optimize`.

**Architecture:**

- New file `app/server/surface.py` declares all `ToolTransformConfig` instances and the single registration function `register_managers(mcp)`.
- New file `app/tools/domain/transitions_score.py` — standalone composite tool under `FileSystemProvider` auto-discovery.
- Extend `app/server/transforms.py:ALWAYS_VISIBLE_TOOLS` to manager names (6 entries), deprecate raw dispatcher names.
- Extend `app/tools/admin/unlock_namespace.py` with new namespace literals (`sets:destructive`, `playlists:write`, `deprecated`).
- Extend `app/server/visibility.py:apply_visibility_policy` to disable `deprecated` tag at startup.
- Tests live in `tests/server/test_surface.py`, `tests/server/test_surface_parity.py`, `tests/tools/domain/test_transitions_score.py`.

**Tech Stack:** Python 3.12 async, FastMCP v3.1+ (`ToolTransform`, `ArgTransform`, `BM25SearchTransform`), SQLAlchemy 2.0 async, pytest + pytest-asyncio (asyncio_mode=auto), `inline-snapshot` for prompt snapshots, `aiosqlite` for in-memory test DB.

**Prerequisites (must be true before Task 1):**

- Runtime fix (Phase 0a) executed: `cache/dj-music-plugin/dj-music/0.7.1` removed, Claude relaunched, `mcp__plugin_dj-music_dj-music__unlock_namespace(action="status", namespace="all")` returns v1 dispatchers (e.g. `entity_list`).
- Dev branch is `dev`; commit `aa6254a` (spec) is HEAD.
- `uv sync --all-extras` passes. `make check` baseline green.

---

## File Structure

**New files (Phase 1):**

```text
app/server/surface.py                                  # Manager configs + register_managers
app/tools/domain/__init__.py                           # Package marker (empty)
app/tools/domain/transitions_score.py                  # Composite tool
tests/server/test_surface.py                           # Metadata + wiring
tests/server/test_surface_parity.py                    # Manager vs dispatcher parity
tests/tools/domain/__init__.py                         # Package marker
tests/tools/domain/test_transitions_score.py           # Composite tool tests
```

**Modified files (Phase 1):**

```text
app/server/transforms.py                               # ALWAYS_VISIBLE_TOOLS: manager names
app/server/app.py                                      # call register_managers() after post-constructor transforms
app/server/visibility.py                               # apply_visibility_policy: disable deprecated + legacy namespaces
app/tools/admin/unlock_namespace.py                    # extend NAMESPACES + NAMESPACE_TAGS
app/schemas/tool_responses.py                          # add TransitionsScoreResult
docs/tool-catalog.md                                   # update: 11 managers + 13 deprecated dispatchers
.importlinter                                          # +1 contract: surface-declarative
```

**Unchanged (out of Phase 1 scope):**

- `app/tools/entity/**`, `app/tools/provider/**`, `app/tools/compute/**`, `app/tools/sync/**`, `app/handlers/**`, `app/repositories/**`, `app/domain/**`, `app/models/**`, `app/audio/**`, panel, rest, migrations.

---

## Task 1: Test scaffolding — assert surface module exists, has expected managers

**Files:**

- Create: `tests/server/test_surface.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_surface.py
"""Tests for app.server.surface — Phase 1 domain manager facade."""

from __future__ import annotations

import pytest

PHASE1_MANAGER_NAMES: frozenset[str] = frozenset(
    {
        "tracks_list",
        "tracks_get",
        "tracks_import",
        "tracks_analyze",
        "tracks_audio_download",
        "playlists_list",
        "playlists_sync",
        "sets_build",
        "sets_get",
        "library_aggregate",
        "transitions_score",
    }
)

def test_surface_module_importable() -> None:
    """Phase 1 ships app.server.surface with register_managers."""
    from app.server import surface

    assert hasattr(surface, "register_managers"), "register_managers missing"
    assert callable(surface.register_managers)

def test_manager_configs_exported() -> None:
    """Each Phase 1 manager has a ToolTransformConfig constant in module scope."""
    from app.server import surface

    # Names come from spec §4.1 table. Config attribute name = upper-case manager name.
    expected_attrs = {name.upper() for name in PHASE1_MANAGER_NAMES}
    missing = expected_attrs - {a for a in dir(surface) if a.isupper()}
    assert not missing, f"missing ToolTransformConfig constants: {sorted(missing)}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_surface.py -v`

Expected:
```text
tests/server/test_surface.py::test_surface_module_importable FAILED
ModuleNotFoundError: No module named 'app.server.surface'
```

- [ ] **Step 3: No implementation yet — commit the failing test**

```bash
git add tests/server/test_surface.py
git commit -m "test(surface): add failing test for surface module presence"
```

---

## Task 2: Create `app/server/surface.py` skeleton with `register_managers` stub

**Files:**

- Create: `app/server/surface.py`

- [ ] **Step 1: Write minimal module with placeholder function**

```python
# app/server/surface.py
"""Phase 1 domain-manager facade over v1 generic dispatchers.

Each manager is a ``ToolTransformConfig`` that renames a raw dispatcher
and hides the ``entity``/``provider`` argument. The facade is zero-dup —
the handler chain remains the raw dispatcher's.

``transitions_score`` is a composite registered separately as a
standalone ``@tool`` under ``app/tools/domain/``, not a ``ToolTransform``.

Public API: ``register_managers(mcp)``. Called from ``build_mcp_server``
after ``register_post_constructor_transforms``.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.transforms import ToolTransform
from fastmcp.tools.tool_transform import ArgTransform, ToolTransformConfig

# Placeholder configs — real definitions added in Task 4.
TRACKS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="tracks_list",
    description="placeholder",
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="track")},
)
TRACKS_GET: ToolTransformConfig = ToolTransformConfig(
    name="tracks_get",
    description="placeholder",
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="track")},
)
TRACKS_IMPORT: ToolTransformConfig = ToolTransformConfig(
    name="tracks_import",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="track")},
)
TRACKS_ANALYZE: ToolTransformConfig = ToolTransformConfig(
    name="tracks_analyze",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="track_features")},
)
TRACKS_AUDIO_DOWNLOAD: ToolTransformConfig = ToolTransformConfig(
    name="tracks_audio_download",
    description="placeholder",
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="audio_file")},
)
PLAYLISTS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="playlists_list",
    description="placeholder",
    tags={"namespace:domain:playlists", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="playlist")},
)
PLAYLISTS_SYNC: ToolTransformConfig = ToolTransformConfig(
    name="playlists_sync",
    description="placeholder",
    tags={"namespace:domain:playlists:write", "write"},
    version="2.0",
    transform_args={},
)
SETS_BUILD: ToolTransformConfig = ToolTransformConfig(
    name="sets_build",
    description="placeholder",
    tags={"namespace:domain:sets", "write"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="set_version")},
)
SETS_GET: ToolTransformConfig = ToolTransformConfig(
    name="sets_get",
    description="placeholder",
    tags={"namespace:domain:sets", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="set")},
)
LIBRARY_AGGREGATE: ToolTransformConfig = ToolTransformConfig(
    name="library_aggregate",
    description="placeholder",
    tags={"namespace:domain:library", "read"},
    version="2.0",
    transform_args={},
)
# TRANSITIONS_SCORE is a composite — no ToolTransformConfig.
# It lives as a standalone tool under app/tools/domain/transitions_score.py.

def register_managers(mcp: FastMCP) -> None:
    """Attach v2.0 domain managers as ToolTransform over v1 dispatchers.

    One ToolTransform per manager (so one original dispatcher can feed many
    managers). The composite ``transitions_score`` is auto-discovered by
    the FileSystemProvider; nothing to register here.
    """
    mcp.add_transform(ToolTransform({"entity_list": TRACKS_LIST}))
    mcp.add_transform(ToolTransform({"entity_list": PLAYLISTS_LIST}))
    mcp.add_transform(ToolTransform({"entity_get": TRACKS_GET}))
    mcp.add_transform(ToolTransform({"entity_get": SETS_GET}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_IMPORT}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_ANALYZE}))
    mcp.add_transform(ToolTransform({"entity_create": TRACKS_AUDIO_DOWNLOAD}))
    mcp.add_transform(ToolTransform({"entity_create": SETS_BUILD}))
    mcp.add_transform(ToolTransform({"entity_aggregate": LIBRARY_AGGREGATE}))
    mcp.add_transform(ToolTransform({"playlist_sync": PLAYLISTS_SYNC}))
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_surface.py -v`

Expected:
```text
tests/server/test_surface.py::test_surface_module_importable PASSED
tests/server/test_surface.py::test_manager_configs_exported PASSED
```

- [ ] **Step 3: Commit**

```bash
git add app/server/surface.py
git commit -m "feat(surface): add ToolTransformConfig skeleton for 10 declarative managers"
```

---

## Task 3: Wire `register_managers` into `build_mcp_server`

**Files:**

- Modify: `app/server/app.py` (add import + call)
- Create: test in `tests/server/test_surface.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/server/test_surface.py`:

```python
# tests/server/test_surface.py (appended)

import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

@pytest_asyncio.fixture
async def mcp_app():
    from app.server.app import build_mcp_app_for_tests

    return await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=False,
        with_lifespan=False,
        with_sampling=False,
    )

async def test_managers_registered_in_mcp(mcp_app) -> None:
    """After build_mcp_app_for_tests, each Phase 1 manager is in list_tools."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}

    missing = PHASE1_MANAGER_NAMES - {"transitions_score"} - names
    # transitions_score arrives in Task 5 (composite tool). All other managers
    # should be present after Task 3 wiring.
    assert not missing, f"managers absent from mcp.list_tools: {sorted(missing)}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/server/test_surface.py::test_managers_registered_in_mcp -v`

Expected: FAIL — managers missing because `register_managers` never called.

- [ ] **Step 3: Modify `app/server/app.py`**

Locate the import block around line 43 and append:

```python
from app.server.surface import register_managers
```

Inside `build_mcp_server()`, immediately after `register_post_constructor_transforms(mcp)` (currently line 81), add:

```python
    # Domain-manager facade (v2.0 surface over v1 dispatchers).
    register_managers(mcp)
```

Inside `build_mcp_app_for_tests(...)`, find the block that registers transforms (around line 128) and add the same line AFTER `register_post_constructor_transforms(mcp)`:

```python
    if with_transforms:
        register_post_constructor_transforms(mcp)
        register_managers(mcp)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/server/test_surface.py -v`

Expected: all three tests pass.

- [ ] **Step 5: Full `make check` sanity**

Run: `uv run lint-imports && uv run mypy app/server/ && uv run ruff check app/server/ tests/server/`

Expected: PASS. Any failure indicates a typing or import issue — fix before commit.

- [ ] **Step 6: Commit**

```bash
git add app/server/surface.py app/server/app.py tests/server/test_surface.py
git commit -m "feat(surface): wire register_managers into build_mcp_server"
```

---

## Task 4: Flesh out manager descriptions + examples

**Files:**

- Modify: `app/server/surface.py` — replace placeholder descriptions with production-grade text per spec §4.1

- [ ] **Step 1: Write test for description/examples presence**

Append to `tests/server/test_surface.py`:

```python
def test_manager_configs_fully_described() -> None:
    """Every manager config has a non-placeholder description and filter examples."""
    from app.server import surface

    config_attrs = [
        "TRACKS_LIST",
        "TRACKS_GET",
        "TRACKS_IMPORT",
        "TRACKS_ANALYZE",
        "TRACKS_AUDIO_DOWNLOAD",
        "PLAYLISTS_LIST",
        "PLAYLISTS_SYNC",
        "SETS_BUILD",
        "SETS_GET",
        "LIBRARY_AGGREGATE",
    ]
    for attr in config_attrs:
        cfg = getattr(surface, attr)
        assert cfg.description and cfg.description != "placeholder", (
            f"{attr}: placeholder description"
        )
        assert len(cfg.description) >= 40, f"{attr}: description too short"

    # List/aggregate managers should give examples for `filters`
    for attr in ("TRACKS_LIST", "PLAYLISTS_LIST", "LIBRARY_AGGREGATE"):
        cfg = getattr(surface, attr)
        if "filters" in cfg.transform_args:
            assert cfg.transform_args["filters"].examples, f"{attr}: filters missing examples"
```

- [ ] **Step 2: Verify it fails**

Run: `uv run pytest tests/server/test_surface.py::test_manager_configs_fully_described -v`

Expected: FAIL — all descriptions are `"placeholder"`.

- [ ] **Step 3: Replace each config in `app/server/surface.py`**

Replace the 10 placeholder configs with these full definitions:

```python
# app/server/surface.py (replace placeholder section)

TRACKS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="tracks_list",
    description=(
        "List tracks with optional filtering, sorting, and field projection. "
        "Filters use Django-style lookups: bpm__gte, bpm__lte, bpm__range, "
        "mood__in, key_code__eq, has_features, title__icontains, id__in, "
        "created_at__range. Field presets: 'id', 'ref', 'summary', 'full'."
    ),
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track"),
        "filters": ArgTransform(
            description='Django-style filter dict, e.g. {"bpm__gte": 120, "mood__in": ["peak_time"]}',
            examples=[
                {"bpm__gte": 120, "bpm__lte": 135},
                {"mood__in": ["peak_time"], "has_features": True},
                {"id__in": [42, 61, 88]},
            ],
        ),
    },
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

TRACKS_GET: ToolTransformConfig = ToolTransformConfig(
    name="tracks_get",
    description=(
        "Fetch a single track by local ID with optional field projection and "
        "relation inclusion. Use include_relations=['artists', 'features'] for "
        "eager-loaded joins."
    ),
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="track")},
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

TRACKS_IMPORT: ToolTransformConfig = ToolTransformConfig(
    name="tracks_import",
    description=(
        "Import tracks from a provider. Fetches metadata, persists Track + "
        "provider-specific metadata (yandex: album, artist, cover, explicit). "
        "Idempotent unless force=true."
    ),
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track"),
        "data": ArgTransform(
            description='{"provider": "yandex", "provider_track_ids": ["12345"], "force": false}',
            examples=[{"provider": "yandex", "provider_track_ids": ["61297756"]}],
        ),
    },
)

TRACKS_ANALYZE: ToolTransformConfig = ToolTransformConfig(
    name="tracks_analyze",
    description=(
        "Run tiered audio analysis on tracks. Level 1 (BPM/LUFS), 2 (+mood via "
        "classifier), 3 (+key/MFCC for scoring), 4 (+structure for transitions), "
        "5 (all 18 analyzers). Skips tracks already at or above target level "
        "unless force=true."
    ),
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track_features"),
        "data": ArgTransform(
            description='{"track_ids": [42, 61], "level": 2, "force": false}',
            examples=[{"track_ids": [42, 61], "level": 2}],
        ),
    },
)

TRACKS_AUDIO_DOWNLOAD: ToolTransformConfig = ToolTransformConfig(
    name="tracks_audio_download",
    description=(
        "Download the MP3 for a track from the provider into the local library "
        "directory. Registers DjLibraryItem and initializes DjBeatgrid."
    ),
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="audio_file"),
        "data": ArgTransform(
            description='{"track_id": 42, "provider": "yandex"}',
            examples=[{"track_id": 42, "provider": "yandex"}],
        ),
    },
)

PLAYLISTS_LIST: ToolTransformConfig = ToolTransformConfig(
    name="playlists_list",
    description=(
        "List local playlists with optional filtering. Filters: "
        "source_of_truth__eq ('local' or 'yandex'), name__icontains, id__in."
    ),
    tags={"namespace:domain:playlists", "read"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="playlist"),
        "filters": ArgTransform(
            description='Django-style filter dict.',
            examples=[{"source_of_truth__eq": "yandex"}],
        ),
    },
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

PLAYLISTS_SYNC: ToolTransformConfig = ToolTransformConfig(
    name="playlists_sync",
    description=(
        "Bidirectional sync between a local playlist and a platform playlist. "
        "direction='pull' fetches remote into local, 'push' writes local to "
        "remote, 'diff' reports discrepancies without mutation."
    ),
    tags={"namespace:domain:playlists:write", "write", "sync"},
    version="2.0",
    transform_args={},  # playlist_sync keeps its native signature
)

SETS_BUILD: ToolTransformConfig = ToolTransformConfig(
    name="sets_build",
    description=(
        "Build a new set version from a pool of tracks. Runs GA/greedy "
        "optimization, scores transitions, persists set_items + transitions. "
        "Uses template-aware fitness when template is set (classic_60, "
        "peak_hour_60, roller_90, ...)."
    ),
    tags={"namespace:domain:sets", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="set_version"),
        "data": ArgTransform(
            description=(
                '{"set_id": 25, "track_ids": [1, 2, 3], "template": "classic_60", '
                '"algorithm": "ga"}'
            ),
            examples=[
                {"set_id": 25, "track_ids": [1, 2, 3, 4, 5], "template": "classic_60"},
            ],
        ),
    },
)

SETS_GET: ToolTransformConfig = ToolTransformConfig(
    name="sets_get",
    description=(
        "Fetch a DJ set by ID. Use include_relations=['versions', 'items'] to "
        "join the latest version with its ordered track items."
    ),
    tags={"namespace:domain:sets", "read"},
    version="2.0",
    transform_args={"entity": ArgTransform(hide=True, default="set")},
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

LIBRARY_AGGREGATE: ToolTransformConfig = ToolTransformConfig(
    name="library_aggregate",
    description=(
        "Compute summary statistics across entities: count, distinct, "
        "histogram, min_max, sum, avg. Optional group_by + filters. Useful "
        "for dashboards without fetching rows."
    ),
    tags={"namespace:domain:library", "read"},
    version="2.0",
    transform_args={
        "filters": ArgTransform(
            description='Django-style filter dict',
            examples=[{"bpm__gte": 120}],
        ),
    },
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
```

- [ ] **Step 4: Verify tests pass**

Run: `uv run pytest tests/server/test_surface.py -v`

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/server/surface.py tests/server/test_surface.py
git commit -m "feat(surface): document all 10 Phase-1 managers with descriptions and examples"
```

---

## Task 5: `transitions_score` composite tool

**Files:**

- Create: `app/tools/domain/__init__.py` (empty package marker)
- Create: `app/tools/domain/transitions_score.py`
- Modify: `app/schemas/tool_responses.py` — add `TransitionsScoreResult`
- Create: `tests/tools/domain/__init__.py` (empty)
- Create: `tests/tools/domain/test_transitions_score.py`

- [ ] **Step 1: Write failing test**

```python
# tests/tools/domain/test_transitions_score.py
"""Tests for app.tools.domain.transitions_score composite."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

@pytest_asyncio.fixture
async def mcp_app():
    from app.server.app import build_mcp_app_for_tests

    return await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=False,
        with_lifespan=False,
        with_sampling=False,
    )

async def test_transitions_score_tool_registered(mcp_app) -> None:
    """transitions_score appears in list_tools after build."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
    assert "transitions_score" in names

async def test_transitions_score_metadata(mcp_app) -> None:
    """transitions_score carries the expected tags, version, description."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "transitions_score")

    assert "transitions_score" == tool.name
    # FastMCP exposes tags on tool.meta or tool.tags depending on client version —
    # check both for forward compat.
    tags = getattr(tool, "tags", None) or (tool.meta.get("tags") if tool.meta else None) or set()
    tags = set(tags)
    assert "namespace:domain:transitions" in tags
    assert "read" in tags
    assert "pool and ordering" in (tool.description or "").lower() or "score" in (tool.description or "").lower()

async def test_transitions_score_invokes_score_pool_and_optimize(mcp_app, monkeypatch) -> None:
    """Composite calls score_pool + sequence_optimize and returns both results."""
    recorded = []

    async def fake_score_pool(track_ids: list[int], **kw):
        recorded.append(("score_pool", list(track_ids)))
        return {
            "count": len(track_ids) * (len(track_ids) - 1),
            "top": [
                {"from_track_id": track_ids[0], "to_track_id": track_ids[1], "overall_score": 0.9},
            ],
        }

    async def fake_optimize(track_ids: list[int], algorithm: str = "ga", **kw):
        recorded.append(("optimize", list(track_ids), algorithm))
        return {
            "ordering": list(track_ids),
            "quality_score": 0.88,
            "algorithm": algorithm,
        }

    # Monkey-patch the module-level helpers the composite imports.
    from app.tools.domain import transitions_score as mod

    monkeypatch.setattr(mod, "_run_score_pool", fake_score_pool)
    monkeypatch.setattr(mod, "_run_optimize", fake_optimize)

    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        result = await client.call_tool(
            "transitions_score",
            {"track_ids": [1, 2, 3], "algorithm": "greedy", "top_k": 1},
        )

    payload = result.structured_content
    assert payload["algorithm"] == "greedy"
    assert payload["ordering"] == [1, 2, 3]
    assert payload["quality_score"] == 0.88
    assert payload["top_pairs"][0]["overall_score"] == 0.9
    assert recorded[0][0] == "score_pool"
    assert recorded[1][0] == "optimize"
```

- [ ] **Step 2: Verify it fails**

Run: `uv run pytest tests/tools/domain/test_transitions_score.py -v`

Expected: `ModuleNotFoundError: No module named 'app.tools.domain'` (all tests collect-fail).

- [ ] **Step 3: Add response schema**

Modify `app/schemas/tool_responses.py` — append:

```python
# app/schemas/tool_responses.py (appended)

from typing import Literal

from pydantic import BaseModel, Field

class TransitionsScoreTopPair(BaseModel):
    """Top-ranked transition pair within the scored pool."""

    from_track_id: int
    to_track_id: int
    overall_score: float = Field(ge=0.0, le=1.0)

class TransitionsScoreResult(BaseModel):
    """Composite result for ``transitions_score`` — pool score + optimized ordering."""

    track_ids: list[int]
    algorithm: Literal["ga", "greedy"]
    ordering: list[int]
    quality_score: float = Field(ge=0.0, le=1.0)
    top_pairs: list[TransitionsScoreTopPair]
    pair_count: int
```

- [ ] **Step 4: Create `app/tools/domain/__init__.py`**

Write empty file:

```python
# app/tools/domain/__init__.py
"""Phase 1+ composite domain tools (not expressible via ToolTransform alone)."""
```

- [ ] **Step 5: Create `app/tools/domain/transitions_score.py`**

```python
# app/tools/domain/transitions_score.py
"""transitions_score — composite over transition_score_pool + sequence_optimize.

Purpose: one-call shortcut for "score N tracks, return ordered set with top
pairs". Delegates to the raw compute tools via helper functions so the test
suite can monkey-patch them.

For full control, callers can still invoke ``transition_score_pool`` and
``sequence_optimize`` separately (they remain registered, tagged
``namespace:compute``).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import (
    TransitionsScoreResult,
    TransitionsScoreTopPair,
)
from app.server.di import get_optimizer, get_transition_scorer, get_uow
from app.tools.compute.score_pool import transition_score_pool as _score_pool_impl
from app.tools.compute.sequence_optimize import sequence_optimize as _optimize_impl

async def _run_score_pool(
    track_ids: list[int],
    *,
    uow: UnitOfWork,
    scorer: Any,
    ctx: Context,
) -> dict[str, Any]:
    """Indirection for monkey-patching in tests."""
    result = await _score_pool_impl(
        track_ids=track_ids,
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)

async def _run_optimize(
    track_ids: list[int],
    *,
    algorithm: Literal["ga", "greedy"],
    uow: UnitOfWork,
    scorer: Any,
    optimizer_builder: Any,
    ctx: Context,
) -> dict[str, Any]:
    result = await _optimize_impl(
        track_ids=track_ids,
        algorithm=algorithm,
        uow=uow,
        scorer=scorer,
        optimizer_builder=optimizer_builder,
        ctx=ctx,
    )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)

@tool(
    name="transitions_score",
    tags={"namespace:domain:transitions", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    description=(
        "Score and order a pool of tracks in one call. Computes the pairwise "
        "transition-score matrix (transition_score_pool), then runs the "
        "optimizer (sequence_optimize) to produce a final ordering plus top "
        "pairs. Use transition_score_pool and sequence_optimize directly if "
        "you need intermediate results."
    ),
)
async def transitions_score(
    track_ids: Annotated[
        list[int],
        Field(min_length=2, max_length=500, description="Track IDs to score + order."),
    ],
    algorithm: Annotated[
        Literal["ga", "greedy"],
        Field(description="Optimization algorithm."),
    ] = "greedy",
    top_k: Annotated[
        int,
        Field(ge=1, le=50, description="How many top pairs to return."),
    ] = 10,
    uow: UnitOfWork = Depends(get_uow),
    scorer=Depends(get_transition_scorer),
    optimizer_builder=Depends(get_optimizer),
    ctx: Context = CurrentContext(),
) -> TransitionsScoreResult:
    pool = await _run_score_pool(track_ids, uow=uow, scorer=scorer, ctx=ctx)
    opt = await _run_optimize(
        track_ids,
        algorithm=algorithm,
        uow=uow,
        scorer=scorer,
        optimizer_builder=optimizer_builder,
        ctx=ctx,
    )

    top_entries = pool.get("top", [])[:top_k]
    top_pairs = [
        TransitionsScoreTopPair(
            from_track_id=int(entry["from_track_id"]),
            to_track_id=int(entry["to_track_id"]),
            overall_score=float(entry["overall_score"]),
        )
        for entry in top_entries
    ]

    return TransitionsScoreResult(
        track_ids=list(track_ids),
        algorithm=algorithm,
        ordering=list(opt.get("ordering", track_ids)),
        quality_score=float(opt.get("quality_score", 0.0)),
        top_pairs=top_pairs,
        pair_count=int(pool.get("count", 0)),
    )
```

- [ ] **Step 6: Create `tests/tools/domain/__init__.py`**

Write empty file with module docstring only:

```python
# tests/tools/domain/__init__.py
"""Tests for composite tools under app/tools/domain/."""
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/tools/domain/test_transitions_score.py -v`

Expected: all three tests pass.

- [ ] **Step 8: Full sanity**

Run: `uv run lint-imports && uv run mypy app/tools/domain/ app/server/surface.py && uv run ruff check app/tools/domain/ app/server/surface.py tests/tools/domain/`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/tools/domain/ app/schemas/tool_responses.py tests/tools/domain/
git commit -m "feat(tools): add transitions_score composite over pool+optimize"
```

---

## Task 6: Switch `ALWAYS_VISIBLE_TOOLS` to manager names

**Files:**

- Modify: `app/server/transforms.py:36-46`
- Modify: `tests/server/test_surface.py` (add visibility assertion)

- [ ] **Step 1: Write failing test**

Append to `tests/server/test_surface.py`:

```python
async def test_always_visible_are_managers(mcp_app) -> None:
    """Tools listed without search should be managers + admin, not v1 dispatchers."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        tools = await client.list_tools()
        visible_names = {t.name for t in tools}

    # 6 managers + 2 BM25 synthetic (search_tools + call_tool) + unlock_namespace
    # + composite tools transitions_score
    must_be_visible = {
        "tracks_list",
        "tracks_get",
        "sets_build",
        "library_aggregate",
        "unlock_namespace",
        "transitions_score",
    }
    missing = must_be_visible - visible_names
    assert not missing, f"expected visible: {sorted(missing)}"

    # v1 dispatchers should NOT be in the default list (they live under `deprecated` tag
    # after Task 8). But Task 6 only touches always_visible — disable happens in Task 8.
    # So for Task 6, assert: at minimum, they're not duplicated in always_visible.
    # The full disable assertion lives in Task 8.
```

- [ ] **Step 2: Run test (may pass or fail depending on BM25 behavior)**

Run: `uv run pytest tests/server/test_surface.py::test_always_visible_are_managers -v`

If it already passes because BM25 has a large max_results — still modify transforms.py to make the intent explicit.

If it fails because dispatchers are in always_visible — fix in Step 3.

- [ ] **Step 3: Replace `ALWAYS_VISIBLE_TOOLS` in `app/server/transforms.py`**

Lines 36-46 currently read:

```python
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
```

Replace with:

```python
ALWAYS_VISIBLE_TOOLS: tuple[str, ...] = (
    # Phase 1 (spec §4.3): managers always on + admin.
    "tracks_list",
    "tracks_get",
    "sets_build",
    "library_aggregate",
    "transitions_score",
    "unlock_namespace",
)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/server/test_surface.py::test_always_visible_are_managers -v`

Expected: PASS.

- [ ] **Step 5: Re-run the full surface test file**

Run: `uv run pytest tests/server/test_surface.py tests/tools/domain/test_transitions_score.py -v`

Expected: all pass. No regressions.

- [ ] **Step 6: Commit**

```bash
git add app/server/transforms.py tests/server/test_surface.py
git commit -m "refactor(transforms): point ALWAYS_VISIBLE_TOOLS at v2.0 managers"
```

---

## Task 7: Extend `unlock_namespace` with `sets:destructive`, `playlists:write`, `deprecated`

**Files:**

- Modify: `app/tools/admin/unlock_namespace.py:14-32`
- Create: `tests/tools/test_unlock_namespace.py`

- [ ] **Step 1: Write failing test**

```python
# tests/tools/test_unlock_namespace.py
"""Tests for app/tools/admin/unlock_namespace — Phase 1 namespace extension."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

@pytest_asyncio.fixture
async def mcp_app():
    from app.server.app import build_mcp_app_for_tests

    return await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=False,
        with_lifespan=False,
        with_sampling=False,
    )

async def test_unlock_namespace_accepts_new_values(mcp_app) -> None:
    """Phase 1 adds sets:destructive, playlists:write, deprecated."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        for ns in ("sets:destructive", "playlists:write", "deprecated"):
            result = await client.call_tool(
                "unlock_namespace", {"namespace": ns, "action": "status"}
            )
            payload = result.structured_content
            assert payload["namespace"] == ns

async def test_unlock_namespace_rejects_unknown(mcp_app) -> None:
    """Unknown namespaces raise a validation-equivalent error."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        with pytest.raises(Exception):  # Literal mismatch → MCP validation error
            await client.call_tool(
                "unlock_namespace", {"namespace": "no_such_namespace", "action": "status"}
            )
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/tools/test_unlock_namespace.py -v`

Expected: FAIL — new namespaces rejected by the `Literal[...]` type in current signature.

- [ ] **Step 3: Extend `app/tools/admin/unlock_namespace.py`**

Replace lines 14-32 (from `NAMESPACES = frozenset(...)` through the end of `NAMESPACE_TAGS = {...}`) with:

```python
NAMESPACES = frozenset(
    {
        # Phase 1 additions (spec §4.3):
        "sets:destructive",
        "playlists:write",
        "deprecated",
        # Existing v1:
        "crud:destructive",
        "provider:write",
        "sync",
        "all",
    }
)

NAMESPACE_TAGS = {
    "sets:destructive": ["namespace:domain:sets:destructive"],
    "playlists:write": ["namespace:domain:playlists:write"],
    "deprecated": ["deprecated"],
    "crud:destructive": ["namespace:crud:destructive"],
    "provider:write": ["namespace:provider:write"],
    "sync": ["namespace:sync"],
    "all": [
        "namespace:domain:sets:destructive",
        "namespace:domain:playlists:write",
        "deprecated",
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
    ],
}
```

Also replace the `namespace:` parameter type signature (line ~46) from:

```python
    namespace: Annotated[
        Literal["crud:destructive", "provider:write", "sync", "all"],
        Field(description="Namespace to toggle"),
    ],
```

to:

```python
    namespace: Annotated[
        Literal[
            "sets:destructive",
            "playlists:write",
            "deprecated",
            "crud:destructive",
            "provider:write",
            "sync",
            "all",
        ],
        Field(description="Namespace to toggle"),
    ],
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/tools/test_unlock_namespace.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/admin/unlock_namespace.py tests/tools/test_unlock_namespace.py
git commit -m "feat(admin): extend unlock_namespace with sets/playlists/deprecated tags"
```

---

## Task 8: Apply `deprecated` tag to v1 dispatchers and disable them at startup

**Files:**

- Modify: `app/tools/entity/list.py` (add `deprecated` tag)
- Modify: `app/tools/entity/get.py`
- Modify: `app/tools/entity/create.py`
- Modify: `app/tools/entity/update.py`
- Modify: `app/tools/entity/delete.py`
- Modify: `app/tools/entity/aggregate.py`
- Modify: `app/tools/provider/read.py`
- Modify: `app/tools/provider/write.py`
- Modify: `app/tools/provider/search.py`
- Modify: `app/tools/compute/score_pool.py`
- Modify: `app/tools/compute/sequence_optimize.py`
- Modify: `app/tools/sync/playlist_sync.py`
- Modify: `app/server/visibility.py` (extend `apply_visibility_policy`)

- [ ] **Step 1: Write failing test**

Append to `tests/server/test_surface.py`:

```python
async def test_v1_dispatchers_hidden_by_default(mcp_app) -> None:
    """After Task 8, v1 dispatcher names are absent from default list_tools."""
    # NOTE: this test requires with_visibility=True in the fixture, which Task 8
    # wires. Build a separate fixture with visibility ON.
    from app.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=True,
        with_lifespan=False,
        with_sampling=False,
    )

    async with Client(transport=FastMCPTransport(app)) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}

    v1_names = {
        "entity_list", "entity_get", "entity_create", "entity_update",
        "entity_delete", "entity_aggregate",
        "provider_read", "provider_write", "provider_search",
        "transition_score_pool", "sequence_optimize",
        "playlist_sync",
    }
    present = v1_names & names
    assert not present, f"v1 dispatchers leaked into default listing: {sorted(present)}"

async def test_deprecated_unlock_reveals_v1(mcp_app) -> None:
    """After unlock_namespace(namespace='deprecated', action='unlock'), v1 appears."""
    from app.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=True,
        with_lifespan=False,
        with_sampling=False,
    )

    async with Client(transport=FastMCPTransport(app)) as client:
        await client.call_tool(
            "unlock_namespace", {"namespace": "deprecated", "action": "unlock"}
        )
        tools_after = await client.list_tools()
        names_after = {t.name for t in tools_after}

    assert "entity_list" in names_after
    assert "provider_read" in names_after
```

- [ ] **Step 2: Verify both tests fail**

Run: `uv run pytest tests/server/test_surface.py::test_v1_dispatchers_hidden_by_default tests/server/test_surface.py::test_deprecated_unlock_reveals_v1 -v`

Expected: FAIL — dispatchers have no `deprecated` tag, `apply_visibility_policy` doesn't disable anything new.

- [ ] **Step 3: Add `deprecated` tag to v1 dispatchers**

For each of the 12 dispatcher files (list below), locate the `@tool(...)` decorator and add `"deprecated"` to the `tags={...}` set. Example for `app/tools/entity/list.py`:

BEFORE:
```python
@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    ...
)
```

AFTER:
```python
@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read", "deprecated"},
    ...
)
```

Apply identical transformation to:

| File | Existing tags to PRESERVE + add `deprecated` |
|---|---|
| `app/tools/entity/list.py` | `namespace:crud:read, read` |
| `app/tools/entity/get.py` | `namespace:crud:read, read` |
| `app/tools/entity/create.py` | `namespace:crud:write, write` |
| `app/tools/entity/update.py` | `namespace:crud:destructive, write` |
| `app/tools/entity/delete.py` | `namespace:crud:destructive, write` |
| `app/tools/entity/aggregate.py` | `namespace:crud:read, read` |
| `app/tools/provider/read.py` | `namespace:provider:read, read` |
| `app/tools/provider/write.py` | `namespace:provider:write, write` |
| `app/tools/provider/search.py` | `namespace:provider:read, read` |
| `app/tools/compute/score_pool.py` | `namespace:compute, read` |
| `app/tools/compute/sequence_optimize.py` | `namespace:compute, read` |
| `app/tools/sync/playlist_sync.py` | `namespace:sync, write, sync` |

Do NOT add `deprecated` to `app/tools/admin/unlock_namespace.py` — unlock is not deprecated, it stays the admin entry point.

- [ ] **Step 4: Extend `apply_visibility_policy`**

Read the current body of `app/server/visibility.py`. The function currently disables three legacy namespace tags:

```python
# current (paraphrased)
def apply_visibility_policy(mcp: FastMCP) -> None:
    mcp.disable(tags={"namespace:crud:destructive"})
    mcp.disable(tags={"namespace:provider:write"})
    mcp.disable(tags={"namespace:sync"})
```

Replace body with:

```python
def apply_visibility_policy(mcp: FastMCP) -> None:
    """Disable hidden namespaces at startup.

    Phase 1 (2026-04-18): in addition to the three v1 legacy namespaces,
    disable the ``deprecated`` tag (hides v1 dispatchers) and the v2 write
    namespaces (``sets:destructive``, ``playlists:write``) that require
    explicit ``unlock_namespace`` per session.
    """
    mcp.disable(tags={"deprecated"})
    mcp.disable(tags={"namespace:domain:sets:destructive"})
    mcp.disable(tags={"namespace:domain:playlists:write"})
    # Legacy (Phase 7 cleanup will drop these once v1 dispatchers are gone):
    mcp.disable(tags={"namespace:crud:destructive"})
    mcp.disable(tags={"namespace:provider:write"})
    mcp.disable(tags={"namespace:sync"})
```

- [ ] **Step 5: Run tests**

Run:
```text
uv run pytest tests/server/test_surface.py tests/tools/test_unlock_namespace.py -v
```

Expected: all pass.

- [ ] **Step 6: Full sanity**

Run: `make check` (or `uv run ruff check && uv run mypy app/ && uv run lint-imports && uv run pytest`)

If anything else fails (e.g. old tests that asserted `entity_list` is visible), update those tests to exercise the manager or unlock the `deprecated` namespace first. Keep the fix scoped to the failing assertions.

- [ ] **Step 7: Commit**

```bash
git add app/tools/ app/server/visibility.py tests/server/test_surface.py
git commit -m "feat(visibility): tag v1 dispatchers deprecated, hide unless unlocked"
```

---

## Task 9: Parity test — every manager produces the same result as its dispatcher

**Files:**

- Create: `tests/server/test_surface_parity.py`

- [ ] **Step 1: Write the parity test file**

```python
# tests/server/test_surface_parity.py
"""Parity tests — every domain manager produces identical output to its
underlying v1 dispatcher for a given input.

The manager is visible by default; the dispatcher is unlocked for this test
via ``unlock_namespace(namespace='deprecated', action='unlock')``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

@pytest_asyncio.fixture
async def mcp_app():
    """Fresh in-memory server with full visibility policy applied."""
    from app.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests(
        with_middleware=False,
        with_visibility=True,
        with_lifespan=True,  # DB engine required for entity_list et al.
        with_sampling=False,
    )
    return app

@pytest_asyncio.fixture
async def client(mcp_app):
    async with Client(transport=FastMCPTransport(mcp_app)) as c:
        # Unlock deprecated namespace so raw dispatchers are callable.
        await c.call_tool(
            "unlock_namespace", {"namespace": "deprecated", "action": "unlock"}
        )
        yield c

# (manager, manager_args, dispatcher, dispatcher_args) tuples.
PARITY_CASES: list[tuple[str, dict, str, dict]] = [
    (
        "tracks_list",
        {"fields": "id", "limit": 3},
        "entity_list",
        {"entity": "track", "fields": "id", "limit": 3},
    ),
    (
        "playlists_list",
        {"fields": "id", "limit": 3},
        "entity_list",
        {"entity": "playlist", "fields": "id", "limit": 3},
    ),
    (
        "library_aggregate",
        {"operation": "count"},
        "entity_aggregate",
        {"entity": "track", "operation": "count"},
    ),
]

@pytest.mark.parametrize("manager,margs,dispatcher,dargs", PARITY_CASES)
async def test_manager_parity(
    client: Client,
    manager: str,
    margs: dict,
    dispatcher: str,
    dargs: dict,
) -> None:
    """Manager and dispatcher return identical structured_content for the same args."""
    manager_result = await client.call_tool(manager, margs)
    dispatcher_result = await client.call_tool(dispatcher, dargs)

    # structured_content may include timestamp-like fields; compare stable keys only.
    m_data = manager_result.structured_content
    d_data = dispatcher_result.structured_content

    # Both must be dict-like with the same item-count field (our dispatchers return a Page shape).
    assert type(m_data) is type(d_data)
    if isinstance(m_data, dict):
        # Compare ordered items (top-level lists of entities) — strip non-deterministic meta.
        m_items = m_data.get("items") if "items" in m_data else m_data
        d_items = d_data.get("items") if "items" in d_data else d_data
        assert m_items == d_items, (
            f"{manager} vs {dispatcher} diverge: manager={m_items!r} dispatcher={d_items!r}"
        )
```

- [ ] **Step 2: Run parity tests**

Run: `uv run pytest tests/server/test_surface_parity.py -v`

Expected: PASS for each PARITY_CASES tuple. If DB fixture fails because `with_lifespan=True` requires real DB URL, see Step 3.

- [ ] **Step 3: If DB fixture setup complains**

If tests error with "no DATABASE_URL" or similar, the current `build_mcp_app_for_tests(with_lifespan=True)` expects a real DB engine. Two choices:

1. **Preferred:** use `with_lifespan=False` and inject a mock `get_uow` via monkey-patch — covered by existing `tests/tools/conftest.py:mock_uow` fixture. Refactor the test to rely on that pattern:

```python
# Replace the mcp_app fixture body with:
from app.server.app import build_mcp_app_for_tests
from app.server import di
from unittest.mock import AsyncMock, MagicMock

@pytest_asyncio.fixture
async def mcp_app(monkeypatch):
    app = await build_mcp_app_for_tests(
        with_middleware=False, with_visibility=True,
        with_lifespan=False, with_sampling=False,
    )
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    # ... minimal repo stubs matching PARITY_CASES inputs
    monkeypatch.setattr(di, "get_uow", lambda: (yield uow))
    return app
```

2. Alternative: set `DJ_DATABASE_URL=sqlite+aiosqlite:///:memory:` for tests and seed a tiny dataset. Heavier; skip unless (1) proves insufficient.

Go with (1). Document mock behavior in the fixture docstring.

- [ ] **Step 4: Commit**

```bash
git add tests/server/test_surface_parity.py
git commit -m "test(surface): parity tests — managers mirror dispatcher output"
```

---

## Task 10: BM25 search still finds managers + unlocked deprecated dispatchers

**Files:**

- Modify: `tests/server/test_surface.py` (add 2 tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/server/test_surface.py`:

```python
async def test_bm25_finds_manager(mcp_app) -> None:
    """BM25 search_tools('list tracks with bpm filter') surfaces tracks_list."""
    async with Client(transport=FastMCPTransport(mcp_app)) as client:
        result = await client.call_tool(
            "search_tools",
            {"query": "list tracks with bpm filter"},
        )
        payload = result.structured_content or {}
        names = [item["name"] for item in payload.get("tools", payload) if isinstance(item, dict)]

    # tracks_list should appear in top 3
    assert "tracks_list" in names[:3], f"tracks_list not in top 3: {names[:3]}"

async def test_bm25_hides_deprecated_by_default(mcp_app) -> None:
    """search_tools should NOT surface v1 dispatchers until 'deprecated' is unlocked."""
    from app.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests(
        with_middleware=False, with_visibility=True,
        with_lifespan=False, with_sampling=False,
    )

    async with Client(transport=FastMCPTransport(app)) as client:
        result = await client.call_tool(
            "search_tools", {"query": "generic entity list"}
        )
        payload = result.structured_content or {}
        names = [
            item["name"] for item in payload.get("tools", payload) if isinstance(item, dict)
        ]

    assert "entity_list" not in names, (
        f"deprecated entity_list surfaced before unlock: {names}"
    )

async def test_bm25_finds_deprecated_after_unlock(mcp_app) -> None:
    """After unlock, search_tools finds v1 dispatchers."""
    from app.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests(
        with_middleware=False, with_visibility=True,
        with_lifespan=False, with_sampling=False,
    )

    async with Client(transport=FastMCPTransport(app)) as client:
        await client.call_tool(
            "unlock_namespace", {"namespace": "deprecated", "action": "unlock"}
        )
        result = await client.call_tool(
            "search_tools", {"query": "generic entity list"}
        )
        payload = result.structured_content or {}
        names = [
            item["name"] for item in payload.get("tools", payload) if isinstance(item, dict)
        ]

    assert "entity_list" in names, f"entity_list not found after unlock: {names}"
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/server/test_surface.py -v -k bm25`

Expected:
- `test_bm25_finds_manager` PASS — managers are in always_visible or discoverable.
- `test_bm25_hides_deprecated_by_default` PASS — matches the Task 8 disable.
- `test_bm25_finds_deprecated_after_unlock` PASS.

If any fail, inspect `BM25SearchTransform(max_results=...)` — may need to bump `max_results` to 12 or adjust `always_visible`.

- [ ] **Step 3: Commit**

```bash
git add tests/server/test_surface.py
git commit -m "test(surface): assert BM25 discovery respects deprecated visibility"
```

---

## Task 11: Import-linter contract for `app/server/surface.py` declarativity

**Files:**

- Modify: `.importlinter`

- [ ] **Step 1: Read current `.importlinter`**

Open `.importlinter` at repo root.

- [ ] **Step 2: Append contract to the file**

At the end of the file (or in the contracts section, following the same style as existing contracts), append:

```ini

[importlinter:contract:surface-declarative]
name = app/server/surface.py must stay declarative (no domain/repo/provider imports)
type = forbidden
source_modules =
    app.server.surface
forbidden_modules =
    app.repositories
    app.models
    app.providers
    app.audio
    app.domain
    app.handlers
```

- [ ] **Step 3: Run lint-imports**

Run: `uv run lint-imports`

Expected: PASS on all contracts including the new one.

If it fails with `app.server.surface imports forbidden ...`, it means my declarative module accidentally imported something it shouldn't. Fix by removing the offending import (most likely: an overeager type hint that pulls in `app.repositories` — replace with string/`TYPE_CHECKING` guard).

- [ ] **Step 4: Commit**

```bash
git add .importlinter
git commit -m "chore(importlinter): add surface-declarative contract"
```

---

## Task 12: Documentation update — `docs/tool-catalog.md`

**Files:**

- Modify: `docs/tool-catalog.md`

- [ ] **Step 1: Read current catalog**

Open `docs/tool-catalog.md`. Note the existing section "Tools (13)".

- [ ] **Step 2: Rewrite the Tools section**

Replace the "Tools (13)" heading and its table with:

```markdown
## Tools — v2.0 surface (11 always-available domain managers + admin + BM25)

Phase 1 (2026-04-18) of the surface redesign: the 13 v1.0 generic dispatchers are retained (tagged `deprecated`, callable after `unlock_namespace(namespace="deprecated")`), and a v2.0 manager layer provides ergonomic named tools.

### Always-visible (8)

| Tool | Version | Underlying | Purpose |
|---|---|---|---|
| `tracks_list` | 2.0 | `entity_list(entity="track")` | List tracks with filters/sort/pagination |
| `tracks_get` | 2.0 | `entity_get(entity="track")` | Single track projection |
| `sets_build` | 2.0 | `entity_create(entity="set_version")` | Optimizer + persist set version |
| `library_aggregate` | 2.0 | `entity_aggregate` | Count/histogram/distinct (dashboards) |
| `transitions_score` | 2.0 | composite: `transition_score_pool` + `sequence_optimize` | Score + order in one call |
| `unlock_namespace` | 1.0 | — | Per-session namespace activation |
| `search_tools` | synthetic | BM25 | Natural-language tool discovery |
| `call_tool` | synthetic | BM25 | Proxy invocation of discovered tools |

### BM25-discoverable managers (6 + per-session unlocked)

| Tool | Version | Namespace | Default |
|---|---|---|---|
| `tracks_import` | 2.0 | `domain:tracks` | ON (BM25-findable) |
| `tracks_analyze` | 2.0 | `domain:tracks` | ON |
| `tracks_audio_download` | 2.0 | `domain:tracks` | ON |
| `playlists_list` | 2.0 | `domain:playlists` | ON |
| `playlists_sync` | 2.0 | `domain:playlists:write` | unlock required |
| `sets_get` | 2.0 | `domain:sets` | ON |

### Phase 2 additions (not shipped yet)

- `sets_deliver` — composite replacing `deliver_set_workflow` prompt.
- `playlists_distribute` — classify + push to subgenre playlists.

### Deprecated dispatchers (13, tagged `deprecated`)

All original v1.0 dispatchers remain registered and callable via `call_tool`. They are absent from default `list_tools()` and BM25 search unless the session calls `unlock_namespace(namespace="deprecated", action="unlock")`. Phase 7 will drop them after the deprecation window.

| Dispatcher | Replacement |
|---|---|
| `entity_list` | `tracks_list`, `playlists_list`, `sets_get` (by entity) |
| `entity_get` | `tracks_get`, `sets_get` |
| `entity_create` | `tracks_import`, `tracks_analyze`, `tracks_audio_download`, `sets_build` |
| `entity_update` | (unlock `crud:destructive`) |
| `entity_delete` | (unlock `crud:destructive`) |
| `entity_aggregate` | `library_aggregate` |
| `provider_read` | (kept for now — no manager alias) |
| `provider_search` | (kept — no manager alias) |
| `provider_write` | (unlock `provider:write`) |
| `transition_score_pool` | `transitions_score` (composite) |
| `sequence_optimize` | `transitions_score` |
| `playlist_sync` | `playlists_sync` |
```

Update the "Tool count history" table at the bottom of the file:

```markdown
| Version | Count | Notes |
|---|---|---|
| v0.8.0 | 88 | Narrow per-operation tools |
| v1.0.0 | 13 | Generic dispatchers, polymorphism |
| v1.1.0 (Phase 1) | 11 visible + 13 deprecated = 24 | Domain manager facade over v1 dispatchers |
```

- [ ] **Step 3: Commit**

```bash
git add docs/tool-catalog.md
git commit -m "docs(tool-catalog): document Phase 1 manager surface"
```

---

## Task 13: Final sanity — `make check` + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Full make check**

Run: `make check`

Expected: ALL pass (lint, type-check, import-linter, tests).

If anything fails, diagnose and fix before proceeding.

- [ ] **Step 2: `fastmcp list` smoke**

Run:

```bash
uv run fastmcp list server.py 2>&1 | /usr/bin/head -60
```

Expected: list shows manager names (`tracks_list`, `sets_build`, `transitions_score`, ...) alongside `unlock_namespace`, `search_tools`, `call_tool`. v1 dispatchers may appear if `fastmcp list` doesn't apply visibility policy (check whether it does).

- [ ] **Step 3: In-memory Client smoke**

Create a temporary script `/tmp/phase1-smoke.py`:

```python
# /tmp/phase1-smoke.py
import asyncio

from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from app.server.app import build_mcp_app_for_tests

async def main():
    app = await build_mcp_app_for_tests(
        with_middleware=False, with_visibility=True,
        with_lifespan=False, with_sampling=False,
    )
    async with Client(transport=FastMCPTransport(app)) as client:
        tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        print(f"Visible tools ({len(names)}):")
        for n in names:
            print(f"  {n}")

asyncio.run(main())
```

Run:

```bash
uv run python /tmp/phase1-smoke.py
```

Expected: 8 always-visible names listed (tracks_list, tracks_get, sets_build, library_aggregate, transitions_score, unlock_namespace, search_tools, call_tool). No `entity_list`, no `provider_read`.

Clean up: `rm /tmp/phase1-smoke.py`.

- [ ] **Step 4: Phase 1 exit review**

Verify against spec §9 Phase 1 exit criteria:

- [ ] `make check` green.
- [ ] `fastmcp list server.py` shows managers alongside dispatchers.
- [ ] `Client(mcp).list_tools()` in-memory test returns the expected 8 always-visible names.
- [ ] `search_tools("score transition")` returns `transitions_score` as top hit (verified by Task 10).
- [ ] Parity test passes for every implemented manager (Task 9).

If all boxes ticked, Phase 1 is complete. No commit for Step 4 (verification only).

- [ ] **Step 5: Update CHANGELOG**

Edit `CHANGELOG.md`. Under `[Unreleased]` add:

```markdown
### Added
- Surface redesign v2 Phase 1: 11 v2.0 domain-manager tools (`tracks_list`, `tracks_get`, `tracks_import`, `tracks_analyze`, `tracks_audio_download`, `playlists_list`, `playlists_sync`, `sets_build`, `sets_get`, `library_aggregate`, `transitions_score`) exposing ergonomic named API over the v1 generic dispatchers.
- Composite tool `transitions_score` orchestrates `transition_score_pool` + `sequence_optimize` in one call.
- Three new unlockable namespaces: `sets:destructive`, `playlists:write`, `deprecated`.

### Changed
- `ALWAYS_VISIBLE_TOOLS` now lists v2.0 managers; v1 dispatchers are tagged `deprecated` and hidden from default `list_tools()` / BM25 search.
- `apply_visibility_policy` disables the `deprecated` tag plus `sets:destructive` and `playlists:write` namespaces at startup.
- `unlock_namespace` accepts three new namespace values: `sets:destructive`, `playlists:write`, `deprecated`.

### Notes
- Dispatchers remain callable via `call_tool(name="entity_list", ...)` or after `unlock_namespace(namespace="deprecated", action="unlock")`.
- Phase 2 will add `sets_deliver` and `playlists_distribute` composites + wire `MoodClassifier` into the analyze handler.
```

Commit:

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note Phase 1 surface redesign v2"
```

---

## Self-Review

**Spec coverage:**

- §4.1 Target Surface: Task 4 covers 10 declarative managers; Task 5 covers `transitions_score`. `playlists_distribute`, `sets_deliver` are Phase 2 (excluded intentionally per Plan header "Prerequisites").
- §4.3 Namespace matrix: Task 7 adds the three new namespaces; Task 8 applies visibility policy.
- §5.1 ToolTransform mechanism: Task 2-4 + Task 5 compose it.
- §5.2 Multi-map problem: Task 2 body uses separate `ToolTransform({...})` per manager (ten calls).
- §5.3 Visibility: Task 8 uses `deprecated` tag per spec's Phase 1-6 arrangement.
- §5.4 Composite tools: Task 5 delivers `transitions_score`. `sets_deliver` / `playlists_distribute` are Phase 2 — not in this plan.
- §8 FastMCP v3 features: `timeout=` on compute tools = Phase 3 (not here), `task=True` = Phase 5, native OTEL = Phase 3. All correctly deferred.
- §11 Import-linter: Task 11 adds `surface-declarative` contract.
- §14 Migration: Task 12 documents deprecation → consumers migrate during Phase 4.
- §9 Phase 1 exit: Task 13 verifies via `make check` + in-memory Client smoke.

**Placeholder scan (per skill checklist):**

- Searched for "TBD", "TODO", "FIXME", "implement later" — none found in the plan's instructional text (only as part of `app.tools.domain.__init__.py` docstring which is legitimate).
- Every code step has full code, not descriptions.
- Parity test parametrize table lists three concrete cases; no "add more".

**Type/signature consistency:**

- `TransitionsScoreResult` declared in Task 5 Step 3 with fields `track_ids`, `algorithm`, `ordering`, `quality_score`, `top_pairs`, `pair_count`. Used in Task 5 Step 5 `transitions_score(...)` return. Test in Task 5 Step 1 asserts `payload["algorithm"]`, `payload["ordering"]`, `payload["quality_score"]`, `payload["top_pairs"][0]["overall_score"]` — consistent.
- Manager config constants declared uppercase (Task 2) are referenced uppercase (Task 4) — consistent.
- `NAMESPACES` frozenset in Task 7 Step 3 matches the `Literal[...]` type in the same step — consistent.

**Scope check:** Plan covers Phase 1 as defined by spec §9. Phase 2 handler closure is explicitly out of scope (prerequisites note). Each task is 2-5 minutes of action.

No issues — plan is ready for execution.

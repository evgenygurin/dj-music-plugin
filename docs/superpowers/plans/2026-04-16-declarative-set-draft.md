# Declarative Set Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a session-state draft workflow to the declarative set building flow, using `ctx.set_state`, `ctx.sample`, `ctx.elicit`, and `ctx.report_progress` from FastMCP.

**Architecture:** Four new tools (`update_set_draft`, `preview_draft`, `commit_draft`, `clear_draft`) live in `app/controllers/tools/draft.py` and share a single session-state key `"set_draft"`. A new `session://set-draft` resource exposes the draft read-only. `ctx.sample(result_type=ArcCritique)` generates narrative feedback; `ctx.elicit()` gates DB writes with user confirmation. `FileSystemProvider` auto-discovers all new files — no bootstrap changes needed.

**Tech Stack:** FastMCP 3.x (`ctx.set_state`, `ctx.sample`, `ctx.elicit`, `ctx.report_progress`, `ctx.read_resource`), Pydantic v2, SQLAlchemy async, pytest-asyncio, unittest.mock.

**Spec:** `docs/superpowers/specs/2026-04-16-declarative-set-draft-design.md`

---

## File Map

| File | Action |
|---|---|
| `app/schemas/arc_critique.py` | Create — `ArcCritique` Pydantic model |
| `app/controllers/tools/draft.py` | Create — 4 tools |
| `app/controllers/resources/session_draft.py` | Create — `session://set-draft` resource |
| `app/controllers/tools/sets.py` | Modify — add `ctx.report_progress()` to `score_transitions` |
| `app/controllers/prompts/workflows/dj_expert_session.py` | Modify — step 4 |
| `tests/test_services/test_arc_critique.py` | Create |
| `tests/test_tools/test_draft_tools.py` | Create |
| `tests/test_tools/test_draft_session_resource.py` | Create |
| `tests/acceptance/test_draft_flow.py` | Create |

---

## Task 1: ArcCritique Pydantic model

**Files:**
- Create: `app/schemas/arc_critique.py`
- Create: `tests/test_services/test_arc_critique.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_arc_critique.py
"""Tests for ArcCritique Pydantic model."""
from __future__ import annotations
import pytest
from app.schemas.arc_critique import ArcCritique

def test_arc_critique_validates_required_fields():
    critique = ArcCritique(
        crowd_journey="Opens hypnotic → industrial peak at 10 → release",
        weak_transitions=["Track 8→9: same energy, no shift"],
        strongest_moment="Track 10 — peak crowd response",
        recommendation="Swap track 5 earlier for contrast",
    )
    assert critique.crowd_journey.startswith("Opens")
    assert len(critique.weak_transitions) == 1
    assert "10" in critique.strongest_moment

def test_arc_critique_accepts_empty_weak_transitions():
    critique = ArcCritique(
        crowd_journey="Smooth linear build",
        weak_transitions=[],
        strongest_moment="Track 7",
        recommendation="No changes needed",
    )
    assert critique.weak_transitions == []

def test_arc_critique_serializes_to_json():
    critique = ArcCritique(
        crowd_journey="Journey",
        weak_transitions=["t1→t2"],
        strongest_moment="t5",
        recommendation="Swap t3",
    )
    data = critique.model_dump()
    assert "crowd_journey" in data
    assert "weak_transitions" in data
    assert isinstance(data["weak_transitions"], list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_services/test_arc_critique.py -v
```
Expected: `FAIL` — `ModuleNotFoundError: app.schemas.arc_critique`

- [ ] **Step 3: Create `app/schemas/arc_critique.py`**

```python
"""ArcCritique — structured LLM output for set arc narrative."""
from __future__ import annotations
from pydantic import BaseModel, Field

class ArcCritique(BaseModel):
    """Structured narrative critique of a DJ set arc, generated via ctx.sample().

    Used as ``result_type`` in ``ctx.sample()`` — FastMCP handles JSON
    validation and auto-retry if the LLM returns an invalid response.
    """

    crowd_journey: str = Field(
        description=(
            "Narrative description of crowd experience across the set phases. "
            "E.g. 'Opens hypnotic 130 BPM → industrial build at 5–8 → peak at 10 → release'"
        )
    )
    weak_transitions: list[str] = Field(
        description=(
            "List of specific transition problems. Empty list means no weak spots. "
            "E.g. ['Track 8→9: same BPM and energy, no dynamic shift']"
        )
    )
    strongest_moment: str = Field(
        description="The single track position with highest expected crowd response."
    )
    recommendation: str = Field(
        description=(
            "One concrete improvement suggestion, or 'No changes needed' if arc is solid."
        )
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_services/test_arc_critique.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/arc_critique.py tests/test_services/test_arc_critique.py
git commit -m "feat: add ArcCritique Pydantic model for structured LLM arc narrative"
```

---

## Task 2: `session://set-draft` resource

**Files:**
- Create: `app/controllers/resources/session_draft.py`
- Create: `tests/test_tools/test_draft_session_resource.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_draft_session_resource.py
"""Tests for session://set-draft resource."""
from __future__ import annotations
import json
import pytest
from fastmcp import Client
from tests.conftest import _parse_tool_result as _parse

@pytest.mark.asyncio
async def test_session_draft_resource_returns_empty_when_no_draft(client: Client):
    """session://set-draft returns {} when no draft has been set."""
    result = await client.read_resource("session://set-draft")
    content = result[0].content if result else "{}"
    data = json.loads(content) if isinstance(content, str) else content
    assert data == {}

@pytest.mark.asyncio
async def test_session_draft_resource_returns_draft_after_update(client: Client):
    """session://set-draft reflects state after update_set_draft."""
    await client.call_tool("update_set_draft", {
        "track_ids": [10, 20, 30],
        "name": "Resource Test Set",
    })
    result = await client.read_resource("session://set-draft")
    content = result[0].content if result else "{}"
    data = json.loads(content) if isinstance(content, str) else content
    assert data["track_ids"] == [10, 20, 30]
    assert data["name"] == "Resource Test Set"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools/test_draft_session_resource.py -v
```
Expected: `FAIL` — resource `session://set-draft` not found.

- [ ] **Step 3: Create `app/controllers/resources/session_draft.py`**

```python
"""Session-scoped set draft resource (session://set-draft)."""
from __future__ import annotations
from fastmcp.dependencies import CurrentContext
from fastmcp.resources import resource
from fastmcp.server.context import Context
from app.controllers.tools._shared import ANNOTATIONS_READ_ONLY, ICON_SETS, RESOURCE_META

@resource(
    uri="session://set-draft",
    name="Set Draft",
    title="Current Set Draft",
    description=(
        "Read the current session-scoped set draft. "
        "Returns {} if no draft exists. Updated by update_set_draft."
    ),
    mime_type="application/json",
    tags={"sets"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=RESOURCE_META,
)
async def get_set_draft(ctx: Context = CurrentContext()) -> dict:  # type: ignore[assignment]
    """Return the current set draft stored in session state."""
    return await ctx.get_state("set_draft") or {}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_tools/test_draft_session_resource.py::test_session_draft_resource_returns_empty_when_no_draft -v
```
Expected: PASS. (The second test requires `update_set_draft` which comes in Task 3.)

- [ ] **Step 5: Commit**

```bash
git add app/controllers/resources/session_draft.py tests/test_tools/test_draft_session_resource.py
git commit -m "feat: add session://set-draft resource"
```

---

## Task 3: `update_set_draft` tool

**Files:**
- Create: `app/controllers/tools/draft.py` (start file here, more tools added in Tasks 4–6)
- Test: `tests/test_tools/test_draft_tools.py` (start file here, more tests added later)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools/test_draft_tools.py
"""Tests for draft set tools (update, preview, commit, clear)."""
from __future__ import annotations
import json
import pytest
from fastmcp import Client
from tests.conftest import _parse_tool_result as _parse

# ── update_set_draft ─────────────────────────────────

@pytest.mark.asyncio
async def test_update_set_draft_stores_track_ids(client: Client):
    result = await client.call_tool("update_set_draft", {
        "track_ids": [1, 2, 3],
        "name": "Test Draft",
    })
    data = _parse(result)
    assert data["track_count"] == 3
    assert data["name"] == "Test Draft"
    assert data["updated"] is True

@pytest.mark.asyncio
async def test_update_set_draft_replaces_previous(client: Client):
    await client.call_tool("update_set_draft", {"track_ids": [1, 2], "name": "A"})
    await client.call_tool("update_set_draft", {"track_ids": [10, 20, 30], "name": "B"})
    result = await client.read_resource("session://set-draft")
    content = result[0].content
    data = json.loads(content) if isinstance(content, str) else content
    assert data["track_ids"] == [10, 20, 30]
    assert data["name"] == "B"

@pytest.mark.asyncio
async def test_update_set_draft_rejects_empty_track_ids(client: Client):
    result = await client.call_tool("update_set_draft", {"track_ids": [], "name": "Empty"})
    data = _parse(result)
    # Should return error content — ToolError from map_domain_errors
    assert "error" in str(data).lower() or "track_ids" in str(data).lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "update_set_draft" -v
```
Expected: `FAIL` — tool `update_set_draft` not found.

- [ ] **Step 3: Create `app/controllers/tools/draft.py`**

```python
"""Declarative set draft tools.

Session-scoped draft workflow:
  update_set_draft → preview_draft → commit_draft
  clear_draft resets at any point.

Session state key: "set_draft"
  {"name": str, "template": str|None, "track_ids": list[int]}
"""
from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_set_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.core.errors import ValidationError
from app.services.set.facade import SetService

_DRAFT_KEY = "set_draft"

@tool(
    title="Update Set Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def update_set_draft(
    track_ids: Annotated[
        list[int],
        Field(description="Ordered list of track IDs. Replaces the entire draft."),
    ],
    name: Annotated[
        str | None,
        Field(description="Set name (required on first call, remembered afterwards)"),
    ] = None,
    template: Annotated[
        str | None,
        Field(description="Set template for arc scoring (e.g. 'roller_90')"),
    ] = None,
    ctx: Context = CurrentContext(),  # type: ignore[assignment]
) -> dict[str, Any]:
    """Store an ordered track list as the current session draft.

    Replaces the previous draft entirely. Call repeatedly as you refine
    the order — session state persists across tool calls in this session.

    Workflow: update_set_draft → preview_draft → update_set_draft → commit_draft.
    """
    if not track_ids:
        raise ValidationError("track_ids must not be empty")

    existing: dict[str, Any] = await ctx.get_state(_DRAFT_KEY) or {}
    draft: dict[str, Any] = {
        "name": name or existing.get("name") or "Untitled Set",
        "template": template if template is not None else existing.get("template"),
        "track_ids": track_ids,
    }
    await ctx.set_state(_DRAFT_KEY, draft)
    return {
        "track_count": len(track_ids),
        "name": draft["name"],
        "template": draft["template"],
        "updated": True,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "update_set_draft" -v
uv run pytest tests/test_tools/test_draft_session_resource.py -v
```
Expected: all pass (including the second resource test now that `update_set_draft` exists).

- [ ] **Step 5: Commit**

```bash
git add app/controllers/tools/draft.py tests/test_tools/test_draft_tools.py
git commit -m "feat: add update_set_draft tool and session state storage"
```

---

## Task 4: `clear_draft` tool

**Files:**
- Modify: `app/controllers/tools/draft.py` (append)
- Modify: `tests/test_tools/test_draft_tools.py` (append)

- [ ] **Step 1: Write the failing test** (append to `test_draft_tools.py`)

```python
# ── clear_draft ──────────────────────────────────────

@pytest.mark.asyncio
async def test_clear_draft_removes_state(client: Client):
    await client.call_tool("update_set_draft", {"track_ids": [1, 2, 3], "name": "ClearTest"})
    result = await client.call_tool("clear_draft", {})
    data = _parse(result)
    assert data["cleared"] is True

    resource_result = await client.read_resource("session://set-draft")
    content = resource_result[0].content
    draft = json.loads(content) if isinstance(content, str) else content
    assert draft == {}

@pytest.mark.asyncio
async def test_clear_draft_on_empty_session_is_safe(client: Client):
    result = await client.call_tool("clear_draft", {})
    data = _parse(result)
    assert data["cleared"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "clear_draft" -v
```
Expected: `FAIL` — tool `clear_draft` not found.

- [ ] **Step 3: Append `clear_draft` to `app/controllers/tools/draft.py`**

```python
@tool(
    title="Clear Set Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
async def clear_draft(
    ctx: Context = CurrentContext(),  # type: ignore[assignment]
) -> dict[str, Any]:
    """Reset the current session draft. Safe to call on an empty session."""
    await ctx.delete_state(_DRAFT_KEY)
    return {"cleared": True}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "clear_draft" -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/controllers/tools/draft.py tests/test_tools/test_draft_tools.py
git commit -m "feat: add clear_draft tool"
```

---

## Task 5: `preview_draft` tool (fast mode, no sampling)

**Files:**
- Modify: `app/controllers/tools/draft.py` (append)
- Modify: `tests/test_tools/test_draft_tools.py` (append)

`preview_draft` calls `preview_arc()` (already exists in `app/optimization/preview.py`) on the
current draft. This task covers the fast path: `narrative=False`.

- [ ] **Step 1: Write the failing tests** (append to `test_draft_tools.py`)

```python
# ── preview_draft — fast mode ────────────────────────

@pytest.mark.asyncio
async def test_preview_draft_raises_when_no_draft(client: Client):
    result = await client.call_tool("preview_draft", {})
    data = _parse(result)
    assert "error" in str(data).lower() or "draft" in str(data).lower()

@pytest.mark.asyncio
async def test_preview_draft_returns_arc_fields(client: Client, async_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(3):
            t = Track(title=f"Preview Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(TrackAudioFeaturesComputed(
                track_id=t.id,
                bpm=130.0 + i,
                key_code=8 + i,
                integrated_lufs=-11.0,
                energy_mean=0.6 + i * 0.05,
                spectral_centroid_hz=2400.0,
                onset_rate=4.0,
                kick_prominence=0.6,
            ))
        await session.commit()

    await client.call_tool("update_set_draft", {
        "track_ids": track_ids,
        "name": "Preview Test",
    })

    result = await client.call_tool("preview_draft", {"narrative": False})
    data = _parse(result)
    assert "score" in data
    assert "energy_arc" in data
    assert "bpm_arc" in data
    assert "weak_spots" in data
    assert "track_count" in data
    assert data["track_count"] == 3
    assert "critique" not in data   # narrative=False → no critique
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "preview_draft" -v
```
Expected: `FAIL` — tool `preview_draft` not found.

- [ ] **Step 3: Append `preview_draft` to `app/controllers/tools/draft.py`**

Add these imports at the top of the file (after existing imports):

```python
from app.controllers.dependencies import get_db_session
from app.db.repositories.feature import FeatureRepository
from app.optimization.preview import PreviewResult, preview_arc
from app.templates.registry import get_template
from app.transition.scorer import TransitionScorer
from sqlalchemy.ext.asyncio import AsyncSession
```

Then append the tool:

```python
@tool(
    title="Preview Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def preview_draft(
    narrative: Annotated[
        bool,
        Field(description="Generate narrative ArcCritique via LLM sampling (slower)"),
    ] = False,
    ctx: Context = CurrentContext(),  # type: ignore[assignment]
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Compute arc fitness for the current session draft.

    Fast mode (narrative=False): arc math only, no LLM call.
    Full mode (narrative=True): adds ArcCritique narrative via ctx.sample().

    Workflow: update_set_draft → preview_draft (iterate) → commit_draft.
    """
    draft: dict[str, Any] | None = await ctx.get_state(_DRAFT_KEY)
    if not draft or not draft.get("track_ids"):
        raise ValidationError("No draft set. Call update_set_draft first.")

    track_ids: list[int] = draft["track_ids"]
    template_name: str | None = draft.get("template")

    await ctx.report_progress(0, 3 if narrative else 2, "Loading features")

    feature_repo = FeatureRepository(session)
    features_map = await feature_repo.get_scoring_features_batch(track_ids)

    await ctx.report_progress(1, 3 if narrative else 2, "Computing arc")

    template_def = None
    if template_name:
        try:
            template_def = get_template(template_name)
        except KeyError:
            pass

    scorer = TransitionScorer()
    result: PreviewResult = preview_arc(scorer, features_map, track_ids, template=template_def)

    output: dict[str, Any] = {
        "score": round(result.score, 4),
        "energy_arc": [round(v, 3) for v in result.energy_arc],
        "bpm_arc": [round(v, 1) for v in result.bpm_arc],
        "weak_spots": result.weak_spots,
        "track_count": len(track_ids),
        "template": template_name,
    }

    if narrative:
        await ctx.report_progress(2, 3, "Generating narrative")
        output["critique"] = await _generate_narrative(ctx, result, track_ids)

    await ctx.report_progress(3 if narrative else 2, 3 if narrative else 2, "Done")
    return output

async def _generate_narrative(
    ctx: Context,
    result: PreviewResult,
    track_ids: list[int],
) -> dict[str, Any] | None:
    """Generate ArcCritique via ctx.sample(). Returns None on any failure."""
    from app.schemas.arc_critique import ArcCritique

    try:
        psychology_parts = await ctx.read_resource("knowledge://dancefloor-psychology")
        dynamics_parts = await ctx.read_resource("knowledge://set-dynamics")
        psychology = psychology_parts[0].content if psychology_parts else ""
        dynamics = dynamics_parts[0].content if dynamics_parts else ""
        system_prompt = (
            "You are a professional DJ analyst. Analyze the following set arc data "
            "and return a structured critique.\n\n"
            f"DANCEFLOOR PSYCHOLOGY:\n{psychology}\n\n"
            f"SET DYNAMICS THEORY:\n{dynamics}"
        )
        arc_summary = (
            f"Set: {len(track_ids)} tracks\n"
            f"BPM arc: {[round(v, 1) for v in result.bpm_arc]}\n"
            f"Energy arc (LUFS): {[round(v, 2) for v in result.energy_arc]}\n"
            f"Overall score: {result.score:.2f}\n"
            f"Weak spot positions: {result.weak_spots}\n"
            f"Arc recommendation: {result.recommendation}"
        )
        sample_result = await ctx.sample(
            messages=arc_summary,
            system_prompt=system_prompt,
            result_type=ArcCritique,
            max_tokens=400,
        )
        critique: ArcCritique = sample_result.result
        return critique.model_dump()
    except Exception:
        await ctx.warning("Narrative generation unavailable — returning arc scores only")
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "preview_draft" -v
```
Expected: 2 passed.

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check app/controllers/tools/draft.py
uv run mypy app/controllers/tools/draft.py --ignore-missing-imports
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/tools/draft.py app/schemas/arc_critique.py tests/test_tools/test_draft_tools.py
git commit -m "feat: add preview_draft tool with arc scoring and optional LLM narrative"
```

---

## Task 6: `commit_draft` tool

**Files:**
- Modify: `app/controllers/tools/draft.py` (append)
- Modify: `tests/test_tools/test_draft_tools.py` (append)

`commit_draft` uses `ctx.elicit(response_type=None)` to confirm before writing to DB.
The test mocks elicitation via a custom client.

- [ ] **Step 1: Write the failing tests** (append to `test_draft_tools.py`)

```python
# ── commit_draft ─────────────────────────────────────

@pytest.mark.asyncio
async def test_commit_draft_raises_when_no_draft(client: Client):
    result = await client.call_tool("commit_draft", {})
    data = _parse(result)
    assert "error" in str(data).lower() or "draft" in str(data).lower()

@pytest.mark.asyncio
async def test_commit_draft_saves_set_when_accepted(async_engine):
    """commit_draft with auto-accept elicitation creates DB record."""
    from fastmcp import Client
    from fastmcp.client.elicitation import ElicitResult
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track
    from app.db.repositories.set import SetRepository
    from app.server import mcp

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids: list[int] = []
    async with factory() as session:
        for i in range(2):
            t = Track(title=f"Commit Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(TrackAudioFeaturesComputed(
                track_id=t.id, bpm=130.0, integrated_lufs=-11.0,
                key_code=8, energy_mean=0.6, spectral_centroid_hz=2400.0,
                onset_rate=4.0, kick_prominence=0.6,
            ))
        await session.commit()

    # Build a client that auto-accepts elicitation
    async def accept_handler(request):  # type: ignore[return]
        return ElicitResult(action="accept", content=None)

    from unittest.mock import AsyncMock
    from app.audio.analyzers import AnalyzerRegistry
    from app.core.utils.cache import TransitionCache
    from app.providers.registry import ProviderRegistry
    from app.core.constants import Provider
    from unittest.mock import MagicMock
    from fastmcp.server.lifespan import lifespan

    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry.register(provider_mock, default=True)
    original_lifespan = mcp._lifespan

    @lifespan
    async def _lifespan(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "analyzer_registry": registry,
            "transition_cache": cache,
            "provider_registry": provider_registry,
        }

    mcp._lifespan = _lifespan
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp, elicitation_handler=accept_handler) as c:
            await c.call_tool("update_set_draft", {
                "track_ids": track_ids,
                "name": "Commit Accept Set",
            })
            result = await c.call_tool("commit_draft", {"version_label": "v1-test"})
            data = _parse(result)

        assert "set_id" in data
        assert data["track_count"] == 2
        assert data["version_label"] == "v1-test"

        async with factory() as session:
            set_repo = SetRepository(session)
            version = await set_repo.get_latest_version(data["set_id"])
            assert version is not None
            items = await set_repo.get_version_items(version.id)
            assert [item.track_id for item in items] == track_ids
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan

@pytest.mark.asyncio
async def test_commit_draft_cancelled_on_decline(async_engine):
    """commit_draft with decline elicitation returns cancelled=True, no DB write."""
    from fastmcp import Client
    from fastmcp.client.elicitation import ElicitResult
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.models.track import Track
    from app.server import mcp
    from unittest.mock import AsyncMock, MagicMock
    from app.audio.analyzers import AnalyzerRegistry
    from app.core.utils.cache import TransitionCache
    from app.providers.registry import ProviderRegistry
    from app.core.constants import Provider
    from fastmcp.server.lifespan import lifespan

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t = Track(title="Decline Track", status=0)
        session.add(t)
        await session.flush()
        track_id = t.id
        await session.commit()

    async def decline_handler(request):  # type: ignore[return]
        return ElicitResult(action="decline", content=None)

    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry.register(provider_mock, default=True)
    original_lifespan = mcp._lifespan

    @lifespan
    async def _lifespan(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine, "db_session_factory": factory,
            "ym_client": ym_mock, "analyzer_registry": registry,
            "transition_cache": cache, "provider_registry": provider_registry,
        }

    mcp._lifespan = _lifespan
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp, elicitation_handler=decline_handler) as c:
            await c.call_tool("update_set_draft", {
                "track_ids": [track_id],
                "name": "Declined Set",
            })
            result = await c.call_tool("commit_draft", {})
            data = _parse(result)
        assert data.get("cancelled") is True
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "commit_draft" -v
```
Expected: `FAIL` — tool `commit_draft` not found.

- [ ] **Step 3: Append `commit_draft` to `app/controllers/tools/draft.py`**

```python
@tool(
    title="Commit Draft",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def commit_draft(
    version_label: Annotated[
        str | None,
        Field(description="Version label, e.g. 'v2-peak-hour'"),
    ] = None,
    ctx: Context = CurrentContext(),  # type: ignore[assignment]
    svc: SetService = Depends(get_set_service),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Confirm with the user then save the current draft as a set version.

    Shows a summary (track count, arc score, weak transitions) via ctx.elicit().
    On accept: saves to DB and clears the draft.
    On decline/cancel: returns {cancelled: true}, DB unchanged.

    If the client does not support elicitation, saves directly without confirmation.
    """
    draft: dict[str, Any] | None = await ctx.get_state(_DRAFT_KEY)
    if not draft or not draft.get("track_ids"):
        raise ValidationError("No draft set. Call update_set_draft first.")

    track_ids: list[int] = draft["track_ids"]
    name: str = draft.get("name") or "Untitled Set"
    template_name: str | None = draft.get("template")

    # Compute a quick arc score for the confirmation message
    quality: float | None = None
    weak_count = 0
    try:
        feature_repo = FeatureRepository(session)
        features_map = await feature_repo.get_scoring_features_batch(track_ids)
        if features_map:
            template_def = None
            if template_name:
                try:
                    template_def = get_template(template_name)
                except KeyError:
                    pass
            arc = preview_arc(TransitionScorer(), features_map, track_ids, template=template_def)
            quality = arc.score
            weak_count = len(arc.weak_spots)
    except Exception:
        pass

    score_str = f"{quality:.2f}" if quality is not None else "n/a"
    elicit_msg = (
        f"Save '{name}': {len(track_ids)} tracks, score {score_str}, "
        f"{weak_count} weak transition(s). Confirm?"
    )

    try:
        elicit_result = await ctx.elicit(elicit_msg, response_type=None)
        if elicit_result.action != "accept":
            return {"cancelled": True}
    except Exception:
        # Client doesn't support elicitation — save directly
        await ctx.info("Elicitation not supported — saving draft without confirmation.")

    dj_set, version, scored_quality = await svc.commit_version(
        name=name,
        track_ids=track_ids,
        template=template_name,
        version_label=version_label,
    )
    await ctx.delete_state(_DRAFT_KEY)

    return {
        "set_id": dj_set.id,
        "version_id": version.id,
        "version_label": version.label,
        "track_count": len(track_ids),
        "quality_score": round(scored_quality, 4) if scored_quality is not None else None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_draft_tools.py -k "commit_draft" -v
```
Expected: 3 passed.

- [ ] **Step 5: Lint + typecheck**

```bash
uv run ruff check app/controllers/tools/draft.py --select F,E,N
uv run mypy app/controllers/tools/draft.py --ignore-missing-imports
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/tools/draft.py tests/test_tools/test_draft_tools.py
git commit -m "feat: add commit_draft tool with ctx.elicit() confirmation gate"
```

---

## Task 7: Acceptance test for the full draft flow

**Files:**
- Create: `tests/acceptance/test_draft_flow.py`

This test runs the complete flow: `update_set_draft → preview_draft → update_set_draft → commit_draft` end-to-end with real DB, mocked elicitation.

- [ ] **Step 1: Write the test**

```python
# tests/acceptance/test_draft_flow.py
"""Acceptance test for the declarative draft set flow."""
from __future__ import annotations
import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from sqlalchemy.ext.asyncio import async_sessionmaker
from unittest.mock import AsyncMock, MagicMock
from fastmcp.server.lifespan import lifespan

from app.audio.analyzers import AnalyzerRegistry
from app.core.constants import Provider
from app.core.utils.cache import TransitionCache
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.repositories.set import SetRepository
from app.providers.registry import ProviderRegistry
from app.server import mcp
from tests.acceptance.conftest import parse_tool_result

def _build_lifespan(async_engine, factory):  # type: ignore[no-untyped-def]
    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry.register(provider_mock, default=True)

    @lifespan
    async def _ls(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "analyzer_registry": registry,
            "transition_cache": cache,
            "provider_registry": provider_registry,
        }
    return _ls

@pytest.mark.asyncio
async def test_full_draft_flow_creates_ordered_version(
    async_engine,
    patch_tiered_noop,
) -> None:
    """update_set_draft → preview_draft → update_set_draft → commit_draft (accept)."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    track_ids: list[int] = []
    async with factory() as session:
        for i in range(4):
            t = Track(title=f"Draft Flow Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(TrackAudioFeaturesComputed(
                track_id=t.id,
                bpm=130.0 + i,
                key_code=8 + i,
                integrated_lufs=-11.0,
                energy_mean=0.6 + i * 0.03,
                spectral_centroid_hz=2400.0,
                onset_rate=4.0,
                kick_prominence=0.6,
            ))
        await session.commit()

    async def accept_handler(request):  # type: ignore[return]
        return ElicitResult(action="accept", content=None)

    original_lifespan = mcp._lifespan
    mcp._lifespan = _build_lifespan(async_engine, factory)
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp, elicitation_handler=accept_handler) as c:
            # 1. Set initial draft
            await c.call_tool("update_set_draft", {
                "track_ids": track_ids,
                "name": "Draft Flow Set",
                "template": None,
            })

            # 2. Preview — fast mode
            preview1 = parse_tool_result(await c.call_tool("preview_draft", {"narrative": False}))
            assert "score" in preview1
            assert preview1["track_count"] == 4

            # 3. Refine: reverse the order
            reversed_ids = list(reversed(track_ids))
            await c.call_tool("update_set_draft", {"track_ids": reversed_ids})

            # 4. Preview again
            preview2 = parse_tool_result(await c.call_tool("preview_draft", {}))
            assert preview2["track_count"] == 4

            # 5. Commit — elicitation auto-accepts
            commit_data = parse_tool_result(await c.call_tool("commit_draft", {
                "version_label": "v1-acceptance",
            }))
            assert commit_data["set_id"] > 0
            assert commit_data["track_count"] == 4
            assert commit_data["version_label"] == "v1-acceptance"

        # Verify DB: version exists with reversed track order
        async with factory() as session:
            repo = SetRepository(session)
            version = await repo.get_latest_version(commit_data["set_id"])
            assert version is not None
            items = await repo.get_version_items(version.id)
            assert [item.track_id for item in items] == reversed_ids
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/acceptance/test_draft_flow.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/acceptance/test_draft_flow.py
git commit -m "test: acceptance test for full draft flow (update → preview → commit)"
```

---

## Task 8: `ctx.report_progress()` in `score_transitions`

**Files:**
- Modify: `app/controllers/tools/sets.py`

Progress reporting is added to `score_transitions(mode="set")`. No logic changes.

- [ ] **Step 1: Locate the scoring call in `score_transitions`**

Open `app/controllers/tools/sets.py`. The tool is at line ~164. The `workflow.score_transitions()` call passes everything to `BuildSetWorkflow`. To add progress we need to pass ctx through. Currently `ctx` is already a parameter. The workflow's `score_transitions` method needs to emit progress, but since workflow is a service layer, we'll add progress calls in the tool itself by wrapping `ToolContext`.

Actually `ToolContext` already wraps the context and is passed as `log`. The `BuildSetWorkflow.score_transitions` calls the service. The simplest correct approach: add `ctx.report_progress` calls around the workflow call in the tool, using a before/after pattern.

- [ ] **Step 2: Modify `score_transitions` in `app/controllers/tools/sets.py`**

Find the function body (currently just `return await workflow.score_transitions(...)`). Replace:

```python
) -> dict[str, Any]:
    """Scores transitions for a set, a single pair, or anchor candidates and persists results. Use when auditing blends, ranking options, or refreshing stored transition scores."""
    if ctx is not None:
        await ctx.report_progress(0, 1, "Scoring transitions")
    result = await workflow.score_transitions(
        mode=mode,
        set_id=set_id,
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        track_id=track_id,
        top_n=top_n,
        log=ToolContext(ctx),
    )
    if ctx is not None:
        await ctx.report_progress(1, 1, "Done")
    return result
```

- [ ] **Step 3: Run full test suite to verify no regressions**

```bash
uv run pytest tests/ -x -q
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add app/controllers/tools/sets.py
git commit -m "feat: add ctx.report_progress() to score_transitions"
```

---

## Task 9: Update `dj_expert_session` prompt

**Files:**
- Modify: `app/controllers/prompts/workflows/dj_expert_session.py`

- [ ] **Step 1: Replace step 4 in the prompt**

In `app/controllers/prompts/workflows/dj_expert_session.py`, replace the `**Step 4 — Adopt these behavioral rules:**` block:

```python
    user_message = f"""You are initializing as a professional DJ expert assistant.
Complete the following setup steps before responding to the user:

**Step 1 — Read library state:**
- `library://snapshot` — track counts by subgenre, playlists, last-analyzed

**Step 2 — Read domain references:**
- `reference://subgenres` — all 15 techno subgenres with energy levels and BPM ranges
- `reference://camelot` — Camelot wheel compatibility rules
- `reference://templates` — 8 set templates with slot definitions and energy arcs

**Step 3 — Read knowledge resources:**
- `knowledge://vocabulary` — map human descriptors (dark, driving, hypnotic) to
  subgenres/BPM/features
- `knowledge://subgenre-culture` — artists, set position, transition neighbors per subgenre
- `knowledge://set-dynamics` — 20-minute rule, energy arc theory, tension-release cycles
- `knowledge://dancefloor-psychology` — crowd states, energy recovery, harmonic mixing perception

**Step 4 — Adopt these behavioral rules:**
- Translate human intent using `knowledge://vocabulary`. Never ask "what BPM range?"
- Make reasonable assumptions and state them briefly (one sentence max)
- Ask questions only when intent is genuinely ambiguous — at most one question
- Speak like a DJ, not a database interface
- Set building workflow — you own the track selection and ordering:
  1. `get_candidate_pool` — explore library by mood/subgenre/energy
  2. `update_set_draft(track_ids=[...])` — save your working order to session state
  3. `preview_draft(narrative=False)` — fast arc check; repeat steps 2–3 to refine
  4. `preview_draft(narrative=True)` — full narrative critique before final commit
  5. `commit_draft()` — user confirms via elicitation, then version is saved
- Use `clear_draft()` to start over at any point
- Read `session://set-draft` to inspect the current draft without calling a tool
- Never delegate ordering to an optimizer — curate the arc yourself

**Step 5 — Know your full capability surface:**
Beyond set building, you can handle any library or taste analysis task autonomously:

*Taste profile analysis* — when the user asks to analyse liked/disliked tracks or
understand their preferences:
1. Collect liked IDs: `ym_likes(action="get_liked")` — paginate until `truncated=False`
2. Identify disliked in local library: `filter_by_feedback(track_ids=<local_ym_ids>)`
3. Pull audio features: `get_candidate_pool(limit=500)`, cross-reference with both sets
4. Compare dimensions: subgenre distribution, BPM range, energy_lufs, dissonance_mean,
   danceability — compute liked vs disliked stats and deltas
5. Produce a structured Markdown report: TL;DR, per-dimension tables, actionable
   insights for set building, limitations

*Library health check* — `get_library_stats()` + `audit_playlist()` without being asked
*Transition explanations* — `explain_transition()` in plain language, no jargon
*Discovery from taste* — use liked subgenre/BPM patterns to seed `find_similar_tracks`{goal_line}

After completing setup, greet the user as a DJ assistant ready to work."""
```

Also update the assistant opening message when `goal` is set:

```python
    if goal:
        assistant_message = (
            f"I've loaded the library and knowledge base. "
            f"I can see you're after: **{goal}**. "
            f"Let me pull candidates with get_candidate_pool, build a draft, "
            f"then preview the arc narrative before committing — "
            f"I'll keep you in the loop at each step."
        )
```

- [ ] **Step 2: Run the full check**

```bash
make check
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add app/controllers/prompts/workflows/dj_expert_session.py
git commit -m "feat: update dj_expert_session step 4 — draft workflow instructions"
```

---

## Task 10: Final verification

- [ ] **Run full make check**

```bash
make check
```
Expected: all tests pass, lint clean, mypy clean, arch contracts pass.

- [ ] **Verify new tools appear in MCP tool list**

```bash
uv run python -c "
from app.server import mcp
import asyncio
async def list_tools():
    async with mcp:
        tools = await mcp.get_tools()
        names = sorted(tools.keys())
        for n in names:
            if 'draft' in n or 'commit' in n or 'preview' in n:
                print(n)
asyncio.run(list_tools())
"
```
Expected output includes: `clear_draft`, `commit_draft`, `commit_set_version`, `preview_draft`, `update_set_draft`.

- [ ] **Commit**

```bash
git add -A
git commit -m "chore: declarative set draft — all tasks complete"
```

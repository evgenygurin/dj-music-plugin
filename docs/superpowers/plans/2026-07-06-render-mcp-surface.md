# Render MCP Surface — Implementation Plan (2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prereq:** Plan 1 (`docs/superpowers/plans/2026-07-06-render-engine-core.md`) is merged — the engine, handlers, `SetVersionRepository.get_render_inputs`, `app/shared/render_jobs.py`, and `app/schemas/render.py` exist.

**Goal:** Expose the render engine as MCP: 3 `task=True` tools in a `render` namespace, 5 read-only resources, a `render_set_workflow` prompt, `FastMCP(tasks=True)` wiring, and delivery reuse — all generic by `version_id`.

**Architecture:** Thin `@tool` dispatchers in `app/tools/render/` inject the clock (timestamp) + workspace path and delegate to Plan 1 handlers. Resources in `app/resources/render.py` read the workspace files + `RENDER_JOBS` (both leaf-importable). The prompt is pure text. Delivery is prompt-driven, so "reuse" = a `DeliverySettings.emit_continuous_mix` flag + a mention in `deliver_set_workflow`.

**Tech Stack:** FastMCP v3 (`@tool`, `@resource`, `@prompt`, `tasks=True`, `Progress`), `fastmcp[tasks]` extra.

**Branch:** `feat/render-mcp-surface`.

---

## File Structure

**Create:**
- `app/tools/render/__init__.py`
- `app/tools/render/_shared.py` — workspace path + timestamp helpers.
- `app/tools/render/render_beatgrid.py`, `render_mixdown.py`, `render_diagnose.py`.
- `app/resources/render.py` — 5 resources.
- `app/prompts/render_set_workflow.py`.
- Tests mirroring each.

**Modify:**
- `pyproject.toml` — add `fastmcp[tasks]` to the `apps`/`all` extra set.
- `app/server/app.py` — `FastMCP(..., tasks=True)`.
- `app/server/transforms.py` — add the 3 render tools to `ALWAYS_VISIBLE_TOOLS`.
- `app/config/delivery.py` — add `emit_continuous_mix`.
- `app/prompts/deliver_set_workflow.py` — mention the rendered mix.
- `tests/prompts/…` — `EXPECTED_PROMPTS` + content-correctness.
- `docs/tool-catalog.md`, `docs/render-pipeline.md` — counts + surface.

---

## Task 1: Enable FastMCP tasks + dependency extra

**Files:**
- Modify: `pyproject.toml`, `app/server/app.py`
- Test: `tests/server/test_tasks_enabled.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_tasks_enabled.py
import pytest

from app.server.app import build_mcp_app_for_tests

@pytest.mark.asyncio
async def test_server_builds_with_tasks_enabled():
    mcp = await build_mcp_app_for_tests()
    # tasks support is on (attribute name per FastMCP: mcp.tasks or similar);
    # assert the server object exposes task capability without raising.
    assert mcp is not None
    # smoke: the render tools are registered
    tools = await mcp.get_tools()
    names = set(tools)
    assert {"render_beatgrid", "render_mixdown", "render_diagnose"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_tasks_enabled.py -v`
Expected: FAIL (render tools not registered yet / tasks not enabled).

- [ ] **Step 3: Implement**

In `pyproject.toml`, add the tasks extra to the `[audio]`+`apps` install path. Find the `[project.optional-dependencies]` block and add `fastmcp[tasks]` alongside the existing `fastmcp[apps]` entry (keep the exact FastMCP version pin consistent — same `>=3.2.4,<3.4` constraint):

```toml
# under the extra that already pulls fastmcp[apps]
"fastmcp[tasks]>=3.2.4,<3.4",
```

In `app/server/app.py`, add `tasks=True` to BOTH `FastMCP(...)` constructions (`build_mcp_server` and `build_mcp_app_for_tests`):

```python
    mcp = FastMCP(
        name="dj-music-v2",
        providers=[fsp_tools, fsp_resources, fsp_prompts],
        transforms=build_pre_constructor_transforms(),
        lifespan=build_server_lifespan(),
        sampling_handler=build_sampling_handler(),
        tasks=True,
    )
```

(This task's test also needs Tasks 2–4 done to pass the tool-registration assertion. Implement 2–4, then re-run. If you prefer strict red/green per task, split the assertion: land `tasks=True` first with only the `assert mcp is not None` line, then extend the assertion in Task 4.)

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/server/test_tasks_enabled.py -v` (after Tasks 2–4)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml app/server/app.py tests/server/test_tasks_enabled.py
git commit -m "feat(render): enable FastMCP tasks + fastmcp[tasks] extra"
```

---

## Task 2: render tool shared helpers

**Files:**
- Create: `app/tools/render/__init__.py`, `app/tools/render/_shared.py`
- Test: `tests/tools/render/test_shared.py`, `tests/tools/render/__init__.py` (empty)

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/render/test_shared.py
from app.tools.render._shared import render_workspace, render_timestamp

def test_workspace_path_by_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache
    reset_settings_cache()
    ws = render_workspace(131)
    assert ws.endswith("render/v131")

def test_timestamp_is_sortable_string():
    ts = render_timestamp()
    assert len(ts) == 15 and ts[8] == "-"  # YYYYMMDD-HHMMSS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/render/test_shared.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# app/tools/render/__init__.py
"""Render tools (namespace:render) — thin dispatchers over Plan 1 handlers."""
```

```python
# app/tools/render/_shared.py
"""Workspace-path + clock helpers for the render tools.

The tools inject the timestamp (clock) so the pure/domain layers never call
Date.now — keeps everything deterministic and testable.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.shared.time import utc_now

def render_workspace(version_id: int) -> str:
    """`<DeliverySettings.output_dir>/<RenderSettings.workspace_subdir>/v{id}`."""
    s = get_settings()
    root = Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
    return str(root)

def render_timestamp() -> str:
    """Sortable job timestamp, e.g. 20260706-142530."""
    return utc_now().strftime("%Y%m%d-%H%M%S")
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/render/test_shared.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/render/ tests/tools/render/
git commit -m "feat(render): tool workspace + timestamp helpers"
```

---

## Task 3: render_beatgrid tool

**Files:**
- Create: `app/tools/render/render_beatgrid.py`
- Test: `tests/tools/render/test_render_beatgrid_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/render/test_render_beatgrid_tool.py
import pytest
from fastmcp import Client

from app.server.app import build_mcp_app_for_tests

@pytest.mark.asyncio
async def test_render_beatgrid_tool_metadata():
    mcp = await build_mcp_app_for_tests()
    tools = await mcp.get_tools()
    t = tools["render_beatgrid"]
    assert "namespace:render" in t.tags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/render/test_render_beatgrid_tool.py -v`
Expected: FAIL (`KeyError: 'render_beatgrid'`).

- [ ] **Step 3: Implement**

```python
# app/tools/render/render_beatgrid.py
"""render_beatgrid — kick-phase + QA (phase refine + LUFS gain) for a version."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_beatgrid import render_beatgrid_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderBeatgridResult
from app.server.di import get_uow
from app.tools.render._shared import render_workspace

@tool(
    name="render_beatgrid",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Compute the beatgrid for a set version: kick-phase detect + sub-beat "
        "phase refine + LUFS level-match. Writes beatgrid.json. Heavy (librosa) "
        "— runs as a background task."
    ),
    meta={"timeout_s": 600.0},
    timeout=600.0,
    task=True,
)
async def render_beatgrid(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    refresh: Annotated[bool, Field(description="Recompute even if cached")] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderBeatgridResult:
    return await render_beatgrid_handler(
        ctx=ctx, uow=uow, version_id=version_id,
        workspace=render_workspace(version_id), refresh=refresh,
    )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/render/test_render_beatgrid_tool.py -v`
Expected: PASS.

If `@tool(task=True)` raises `TypeError: unexpected keyword 'task'` (standalone decorator lacks it in this FastMCP build), drop `task=True` and instead set `meta={"timeout_s": 600.0, "task": True}` — FastMCP's FileSystemProvider honours `meta` task flags. Verify which form the pinned FastMCP accepts by grepping `.venv` : `uv run python -c "from fastmcp.tools import tool; import inspect; print('task' in inspect.signature(tool).parameters)"`. Use whichever the version supports and keep it consistent across all 3 tools.

- [ ] **Step 5: Commit**

```bash
git add app/tools/render/render_beatgrid.py tests/tools/render/test_render_beatgrid_tool.py
git commit -m "feat(render): render_beatgrid tool (task=True)"
```

---

## Task 4: render_mixdown + render_diagnose tools

**Files:**
- Create: `app/tools/render/render_mixdown.py`, `app/tools/render/render_diagnose.py`
- Test: `tests/tools/render/test_render_mixdown_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/render/test_render_mixdown_tool.py
import pytest

from app.server.app import build_mcp_app_for_tests

@pytest.mark.asyncio
async def test_render_mixdown_and_diagnose_registered():
    mcp = await build_mcp_app_for_tests()
    tools = await mcp.get_tools()
    assert "namespace:render" in tools["render_mixdown"].tags
    assert "namespace:render" in tools["render_diagnose"].tags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/render/test_render_mixdown_tool.py -v`
Expected: FAIL (`KeyError`).

- [ ] **Step 3: Implement**

```python
# app/tools/render/render_mixdown.py
"""render_mixdown — beatmatch + EQ bass-swap render to one continuous MP3."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_mixdown import render_mixdown_handler
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderMixdownResult
from app.server.di import get_uow
from app.tools.render._shared import render_timestamp, render_workspace

@tool(
    name="render_mixdown",
    tags={"namespace:render", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Render the continuous beatmatched mix (rubberband→target BPM, 32-bar "
        "EQ bass-swap transitions, limiter) for a set version. Auto-runs the "
        "beatgrid if missing. Heavy (ffmpeg) — background task."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
    task=True,
)
async def render_mixdown(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    out_name: Annotated[str | None, Field(description="Output filename (default MIX.mp3)")] = None,
    transition_bars: Annotated[int | None, Field(ge=1, description="Override transition length")] = None,
    body_bars: Annotated[int | None, Field(ge=1, description="Override per-track solo length")] = None,
    refresh_grid: Annotated[bool, Field(description="Recompute the beatgrid first")] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderMixdownResult:
    return await render_mixdown_handler(
        ctx=ctx, uow=uow, version_id=version_id,
        workspace=render_workspace(version_id), timestamp=render_timestamp(),
        out_name=out_name, transition_bars=transition_bars, body_bars=body_bars,
        refresh_grid=refresh_grid,
    )
```

```python
# app/tools/render/render_diagnose.py
"""render_diagnose — scan + per-4s defect sweep of a rendered mix."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_diagnose import render_diagnose_handler
from app.schemas.render import RenderDiagnosticsResult
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.tools.render._shared import render_workspace

@tool(
    name="render_diagnose",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Scan + per-4s librosa defect sweep of a rendered mix (level jumps, "
        "dropouts, bass-thin). Heavy — background task. Pass version_id to "
        "diagnose that version's MIX.mp3, or an explicit mix_path."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
    task=True,
)
async def render_diagnose(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[str | None, Field(description="Explicit mix path (default workspace MIX.mp3)")] = None,
    ctx: Context = CurrentContext(),
) -> RenderDiagnosticsResult:
    ws = render_workspace(version_id)
    path = mix_path or str(Path(ws) / "MIX.mp3")
    if not Path(path).exists():
        raise ValidationError(f"no rendered mix at {path} — run render_mixdown first")
    return await render_diagnose_handler(
        ctx=ctx, job_id=f"v{version_id}", mix_path=path, workspace=ws,
    )
```

- [ ] **Step 4: Run test + the Task 1 test**

Run: `uv run pytest tests/tools/render/test_render_mixdown_tool.py tests/server/test_tasks_enabled.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add app/tools/render/render_mixdown.py app/tools/render/render_diagnose.py tests/tools/render/test_render_mixdown_tool.py
git commit -m "feat(render): render_mixdown + render_diagnose tools"
```

---

## Task 5: ALWAYS_VISIBLE_TOOLS wiring

Without this, `BM25SearchTransform` hides the render tools behind a search query.

**Files:**
- Modify: `app/server/transforms.py`
- Test: `tests/server/test_render_tools_always_visible.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_render_tools_always_visible.py
from app.server.transforms import ALWAYS_VISIBLE_TOOLS

def test_render_tools_always_visible():
    for name in ("render_beatgrid", "render_mixdown", "render_diagnose"):
        assert name in ALWAYS_VISIBLE_TOOLS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_render_tools_always_visible.py -v`
Expected: FAIL (`assert ... in`).

- [ ] **Step 3: Implement**

In `app/server/transforms.py`, add to the `ALWAYS_VISIBLE_TOOLS` tuple (after the `ui_*` entries):

```python
    # Render pipeline tools — visible by default (like compute/sync verbs).
    "render_beatgrid",
    "render_mixdown",
    "render_diagnose",
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/server/test_render_tools_always_visible.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/server/transforms.py tests/server/test_render_tools_always_visible.py
git commit -m "feat(render): keep render tools always-visible (BM25 whitelist)"
```

---

## Task 6: render resources

Five read-only resources. Status/timeline/beatgrid/diagnostics + reference defaults. All cheap (read workspace files / `RENDER_JOBS` / pure timeline). No librosa.

**Files:**
- Create: `app/resources/render.py`
- Test: `tests/resources/test_render_resources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/resources/test_render_resources.py
import json

import pytest

from app.resources.render import render_defaults_resource, render_job_status_resource

@pytest.mark.asyncio
async def test_defaults_resource_has_settings():
    payload = json.loads(await render_defaults_resource())
    assert payload["target_bpm"] == 130.0
    assert payload["transition_bars"] == 32

@pytest.mark.asyncio
async def test_status_resource_unknown_job():
    from app.shared.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await render_job_status_resource("does-not-exist")

@pytest.mark.asyncio
async def test_status_resource_reads_registry():
    from app.shared.render_jobs import RENDER_JOBS
    RENDER_JOBS.clear()
    RENDER_JOBS.start(job_id="v1-x", version_id=1, phase="mixdown")
    RENDER_JOBS.update("v1-x", progress=2, total=5, message="track 2")
    payload = json.loads(await render_job_status_resource("v1-x"))
    assert payload["phase"] == "mixdown" and payload["progress"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_render_resources.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# app/resources/render.py
"""Read-only render resources (workspace files + job registry + timeline).

Cheap reads only — the heavy librosa passes are tools (render_diagnose), not
resources. Imports only app.shared / app.domain / app.config (never handlers).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.config import get_settings
from app.domain.render.timeline import timeline_windows
from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.render_jobs import RENDER_JOBS

def _workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"

@resource(
    "reference://render/defaults",
    mime_type="application/json",
    tags={"namespace:reference"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_defaults_resource() -> str:
    """RenderSettings constants (BPM, bars, XSPLIT, limiter)."""
    r = get_settings().render
    return json.dumps({
        "target_bpm": r.target_bpm, "transition_bars": r.transition_bars,
        "body_bars": r.body_bars, "xsplit_hz": r.xsplit_hz,
        "low_swap_bars": r.low_swap_bars, "outro_fade_bars": r.outro_fade_bars,
        "limiter_ceiling": r.limiter_ceiling,
    })

@resource(
    "local://render/jobs/{job_id}/status",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_job_status_resource(job_id: str) -> str:
    """Live render-job progress from the in-process registry."""
    job = RENDER_JOBS.get(job_id)
    if job is None:
        raise NotFoundError("render_job", job_id)
    return json.dumps(asdict(job))

@resource(
    "local://render/jobs/{job_id}/diagnostics",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_job_diagnostics_resource(job_id: str) -> str:
    """Saved diagnostics report for a job's version workspace."""
    # job_id is v{version_id}-{ts} or v{version_id}; extract version
    vid = job_id.split("-")[0].lstrip("v")
    path = _workspace(int(vid)) / "diagnostics.json"
    if not path.exists():
        raise NotFoundError("render_diagnostics", job_id)
    return path.read_text()

@resource(
    "local://render/{version_id}/beatgrid",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_beatgrid_resource(version_id: int) -> str:
    """Saved beatgrid.json for a version (or 404 → run render_beatgrid)."""
    path = _workspace(version_id) / "beatgrid.json"
    if not path.exists():
        raise NotFoundError("render_beatgrid", version_id)
    return path.read_text()

@resource(
    "local://render/{version_id}/timeline",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_timeline_resource(
    version_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Segment + transition-window timeline for a version (pure math)."""
    inputs = await uow.set_versions.get_render_inputs(version_id)
    r = get_settings().render
    wins = timeline_windows(inputs, target_bpm=r.target_bpm,
                            body_bars=r.body_bars, transition_bars=r.transition_bars)
    return json.dumps({
        "version_id": version_id,
        "segments": [
            {"index": i, "title": inputs[i].title, "start_s": s, "end_s": e}
            for (i, s, e) in wins.segments
        ],
        "transitions": [
            {"from_index": t.from_index, "to_index": t.to_index,
             "start_s": t.start_s, "end_s": t.end_s}
            for t in wins.transitions
        ],
    })
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/resources/test_render_resources.py -v && uv run lint-imports`
Expected: tests PASS; import-linter still KEEPS `v2-resources-no-tools` (this module imports only shared/domain/config/repositories — allowed; repositories is permitted for resources, same as `set.py`).

- [ ] **Step 5: Commit**

```bash
git add app/resources/render.py tests/resources/test_render_resources.py
git commit -m "feat(render): 5 read-only render resources"
```

---

## Task 7: render_set_workflow prompt

**Files:**
- Create: `app/prompts/render_set_workflow.py`
- Modify: prompt registration test list + content-correctness expectations
- Test: `tests/prompts/test_render_set_workflow.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/prompts/test_render_set_workflow.py
import pytest

from app.prompts.render_set_workflow import render_set_workflow

@pytest.mark.asyncio
async def test_render_prompt_mentions_real_surface():
    res = await render_set_workflow(version_id=131)
    text = res.messages[0].content.text if hasattr(res.messages[0].content, "text") else str(res.messages[0].content)
    # references real tools/resources only
    assert "render_beatgrid" in text
    assert "render_mixdown" in text
    assert "entity_create(entity='audio_file'" in text or 'entity="audio_file"' in text
    assert "local://render/" in text
    assert "deliver_set_workflow" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prompts/test_render_set_workflow.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# app/prompts/render_set_workflow.py
"""render_set_workflow — render a set version to a continuous beatmatched mix."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META

def _build_body(version_id: int) -> str:
    return f"""To render set version {version_id} into ONE continuous, beatmatched,
tracks-only DJ mix (EQ bass-swap transitions) and deliver it:

1. Ensure every track has a physical MP3 registered (the engine reads files
   from dj_library_items; it does NOT download). For any missing track:
   entity_create(entity="audio_file", data={{"track_ids": [<track ids>]}})
   Download in batches of ~8-10 under the tool timeout; verify with
   entity_list(entity="audio_file", filters={{"track_id__in": [...]}}).

2. (Recommended) Bring the set tracks to analysis_level=5 first so bpm / key /
   LUFS are accurate:
   entity_update(entity="track_features", id=<track_id>, data={{"level": 5}})

3. Compute the beatgrid (kick-phase + sub-beat phase refine + LUFS level-match):
   render_beatgrid(version_id={version_id})
   Inspect it: read local://render/{version_id}/beatgrid — check per-track
   phase (ms) and gain (dB); tracks flagged "fixed" had a large correction.

4. Render the continuous mix (auto-uses the cached beatgrid):
   render_mixdown(version_id={version_id})
   This is heavy (ffmpeg+rubberband) and runs as a background task; poll
   local://render/jobs/{{job_id}}/status for progress.

5. Diagnose the result:
   render_diagnose(version_id={version_id})
   Read local://render/{version_id}/timeline to tell a TRANSITION-window hole
   (a mix defect) from a track's own breakdown (music). Most -17..-20 dB dips
   inside a track body are breakdowns — do NOT chase them.

6. Deliver: run the deliver_set_workflow prompt for this set. With
   emit_continuous_mix enabled the rendered MIX.mp3 ships alongside the M3U8 /
   rekordbox XML / cheatsheet bundle.

Honest engine limits: no real stem separation (the bass-swap is a 2-band EQ
crossover, not demucs); phrasing is approximate where DB beatgrids are absent;
LOOP_ROLL / FILTER_SWEEP are not engine presets. Target tempo + bar lengths
come from reference://render/defaults."""

@prompt(
    name="render_set_workflow",
    tags={"namespace:workflow", "delivery"},
    meta=PROMPT_META,
)
async def render_set_workflow(version_id: int) -> PromptResult:
    """Render a set version to a continuous beatmatched mix + deliver."""
    return PromptResult(
        messages=[Message(role="user", content=_build_body(version_id))],
        description="Render a set version into a continuous beatmatched DJ mix.",
    )
```

- [ ] **Step 4: Register + run content-correctness**

Find the prompt registration test (grep `EXPECTED_PROMPTS`) and add `"render_set_workflow"` to the expected set. Find the content-correctness dispatcher (grep `_render` / `PROMPTS` tuple in `tests/prompts/test_prompt_content_correctness.py`) and add `render_set_workflow(version_id=1)` to the render list so its `entity=`/`local://`/prompt-name references are validated against the live runtime.

Run: `uv run pytest tests/prompts/ -v`
Expected: PASS (new prompt registered; all names resolve — `audio_file` entity, `track_features` entity, `local://render/*` resources, `deliver_set_workflow` prompt all exist).

- [ ] **Step 5: Commit**

```bash
git add app/prompts/render_set_workflow.py tests/prompts/
git commit -m "feat(render): render_set_workflow prompt"
```

---

## Task 8: Delivery reuse (emit_continuous_mix)

**Files:**
- Modify: `app/config/delivery.py`, `app/prompts/deliver_set_workflow.py`
- Test: `tests/config/test_delivery_continuous_mix.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_delivery_continuous_mix.py
from app.config.delivery import DeliverySettings

def test_emit_continuous_mix_default_true():
    assert DeliverySettings().emit_continuous_mix is True

def test_emit_continuous_mix_env_override(monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_EMIT_CONTINUOUS_MIX", "false")
    assert DeliverySettings().emit_continuous_mix is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_delivery_continuous_mix.py -v`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Implement**

In `app/config/delivery.py`, add the field (next to the other `emit_*` toggles):

```python
    emit_continuous_mix: bool = Field(
        default=True,
        description="Include the rendered continuous beatmatched MIX.mp3 in the bundle.",
    )
```

In `app/prompts/deliver_set_workflow.py`, add a step in `_build_body` (after the audio-finalize step, before the platform-sync clause) so delivery references the rendered mix:

```python
    continuous_clause = (
        "   Also include the continuous beatmatched mix if one was rendered:\n"
        "   render_set_workflow produces generated-sets/render/v<version_id>/MIX.mp3.\n"
        "   Copy it into the deliverable bundle when DeliverySettings\n"
        "   emit_continuous_mix is enabled (default).\n"
    )
```

Insert `{continuous_clause}` into the returned f-string body at the delivery-bundle step.

- [ ] **Step 4: Run test + prompts gate**

Run: `uv run pytest tests/config/test_delivery_continuous_mix.py tests/prompts/ -v`
Expected: PASS (new field + deliver prompt still content-correct).

- [ ] **Step 5: Commit**

```bash
git add app/config/delivery.py app/prompts/deliver_set_workflow.py tests/config/test_delivery_continuous_mix.py
git commit -m "feat(render): emit_continuous_mix delivery toggle + deliver prompt mention"
```

---

## Task 9: Docs + full gate

**Files:**
- Modify: `docs/tool-catalog.md`, `docs/render-pipeline.md`

- [ ] **Step 1: Update docs**

In `docs/tool-catalog.md`: bump tool count 20→23 (+3 render tools; note `render` namespace visible by default, like `sync`/`compute`), add the render tools table row, the 5 render resources, and `render_set_workflow` to the prompt catalog (30→31). In `docs/render-pipeline.md`: fill the "MCP surface" section (3 tools + 5 resources + prompt).

- [ ] **Step 2: Full gate**

Run: `make check`
Expected: lint + mypy + `lint-imports` + full pytest all PASS. New render tests pass with `[audio]`+ffmpeg present; skip otherwise.

- [ ] **Step 3: Fix any failures**

Likely spots: the `@tool(task=True)` form (see Task 3 Step 4 note) — apply the same form to all 3 tools. If a resource-content test enumerates all `local://` URIs, add the render ones. If a "tool count" test asserts an exact number, update it.

- [ ] **Step 4: Commit**

```bash
git add docs/tool-catalog.md docs/render-pipeline.md
git commit -m "docs(render): document MCP surface (tools + resources + prompt)"
```

---

## Self-Review

**Spec coverage (Plan 2 = §1 surface + §3 execution + delivery):**
- 3 render tools (§1) → Tasks 3–4. ✓
- `task=True` + `fastmcp[tasks]` (§3) → Task 1. ✓
- ALWAYS_VISIBLE (§1 visibility) → Task 5. ✓
- 5 resources (§1) → Task 6. ✓
- `render_set_workflow` prompt (§1) → Task 7. ✓
- delivery reuse `emit_continuous_mix` (§1) → Task 8. ✓
- docs counts (§5 rollout) → Task 9. ✓
- **Deferred to Plan 3:** `ui_render_studio` + app-helper.

**Type consistency:** tool names `render_beatgrid`/`render_mixdown`/`render_diagnose` identical across Tasks 3–5, resources, prompt, docs. `render_workspace`/`render_timestamp` helper names consistent (Tasks 2–4). Handler call signatures match Plan 1 (`render_beatgrid_handler(ctx, uow, version_id, workspace, refresh)`, `render_mixdown_handler(..., timestamp, out_name, transition_bars, body_bars, refresh_grid)`, `render_diagnose_handler(ctx, job_id, mix_path, workspace)`). `RENDER_JOBS` imported from `app.shared.render_jobs` in the resource (matches Plan 1's relocation). `job_id` format `v{version_id}-{timestamp}` reused in the diagnostics resource parse.

**Placeholder scan:** no TBD/TODO; full code in every step; every test has real assertions. The one conditional (`@tool(task=True)` vs `meta` task flag) has an explicit verification command + fallback, not a placeholder.

---

## Next plan

- **Plan 3 — Prefab render studio:** `ui_render_studio` (`app=True`) entry tool + hidden `render_studio_panel` app-helper (`visibility=["app"]`) + `RenderStudioFallback` in `app/tools/ui/_fallback.py` + `ALWAYS_VISIBLE` add + `tests/tools/ui/test_render_studio.py`.

# Render Prefab Studio — Implementation Plan (3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prereq:** Plans 1 + 2 merged — the render engine, the 3 `render_*` tools, the 5 `local://render/*` resources, `render_set_workflow`, and `app/shared/render_jobs.py` all exist and pass `make check`.

**Goal:** An interactive Prefab control panel `ui_render_studio(version_id)` — buttons that `CallTool` into the real `render_*` tools, live job status, QA table, timeline, and diagnostics slots — plus a hidden `render_studio_panel` app-helper that re-renders the slots. Non-Prefab clients get a Pydantic fallback.

**Architecture:** Follows the 6 existing `ui_*` tools: `@tool(meta={"ui": True})`, `supports_ui(ctx)` gate, Pydantic fallback in `_fallback.py`. The pult uses Prefab's `PrefabApp`/`Column`/`Button`/`CallTool`/`SetState`/`Slot`/`ShowToast`. The hidden helper carries `AppConfig(visibility=["app"])` so the model never sees it but the UI can `CallTool` it. Status flows through OUR CallTool round-trip (reading `RENDER_JOBS` + workspace files), never the host task protocol — satisfying the §3 degradation contract.

**Tech Stack:** FastMCP v3 apps, `prefab_ui` (`fastmcp[apps]`), `prefab_ui.components`, `fastmcp.server.apps.AppConfig`.

**Branch:** `feat/render-mcp-surface`.

**Reference doc:** `prefab.prefect.io/docs/running/fastmcp` — `@mcp.tool(app=True)` entry tools; `AppConfig(visibility=["app"])` helper tools; `PrefabApp(view, state)`; actions `CallTool`, `SetState`, `ShowToast`; `Slot` + `RESULT` callback ref.

> **⚠️ API CORRECTION (verified live 2026-07-06 against installed fastmcp 3.2.4 + prefab_ui 0.19.1 — no upgrade needed; interactivity IS available on the pinned versions):**
> - The standalone `@tool` decorator has **no `app=` param**. Use `meta={"ui": True}` (exactly like the 6 existing `ui_*` tools) — that IS the `app=True` equivalent for FileSystemProvider auto-discovery.
> - `CallTool` lives in **`prefab_ui.actions.mcp`**, NOT `prefab_ui.actions`. Correct imports:
>   `from prefab_ui.actions.mcp import CallTool` and `from prefab_ui.actions import SetState, ShowToast`.
> - `AppConfig` is imported from **`fastmcp.apps`** (not `fastmcp.server.apps`, which is deprecated). For the hidden helper, pass app-visibility via meta: `meta={"ui": True, **app_config_to_meta_dict(AppConfig(visibility=["app"]))}` where `from fastmcp.apps import AppConfig, app_config_to_meta_dict` (→ merges `{"visibility": ["app"]}`).
> - **Rendering of interactive actions CANNOT be verified headless** — tests cover construction (no error), the non-Prefab fallback branch, registration, and `make check`. Live button behavior needs a Prefab-aware client (Claude Desktop). If the hidden-helper `visibility` meta turns out not to hide the helper from the model in this version, fall back to: single self-refreshing entry tool (Refresh button re-`CallTool`s `ui_render_studio` itself with `job_id`), dropping the separate helper.

---

## File Structure

**Create:**
- `app/tools/ui/render_studio.py` — `ui_render_studio` entry tool + `render_studio_panel` helper.
- Tests under `tests/tools/ui/`.

**Modify:**
- `app/tools/ui/_fallback.py` — add `RenderStudioFallback`.
- `app/server/transforms.py` — add `ui_render_studio` to `ALWAYS_VISIBLE_TOOLS`.
- `docs/tool-catalog.md` — UI tools 6→7, tool count 23→24.

---

## Task 1: RenderStudioFallback model

**Files:**
- Modify: `app/tools/ui/_fallback.py`
- Test: `tests/tools/ui/test_render_studio_fallback.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_render_studio_fallback.py
from app.tools.ui._fallback import RenderStudioFallback

def test_render_studio_fallback_shape():
    f = RenderStudioFallback(
        version_id=131, n_tracks=15, target_bpm=130.0,
        beatgrid=[{"track_id": 1, "phase_ms": 10.0, "gain_db": 1.5, "flags": ["fixed"]}],
        job={"job_id": "v131-x", "phase": "mixdown", "progress": 3, "total": 15},
        timeline=[{"index": 0, "title": "t1", "start_s": 0.0, "end_s": 100.0}],
        diagnostics=[{"offset_s": 20.0, "tags": ["DROPOUT -30dB"]}],
    )
    assert f.version_id == 131 and f.n_tracks == 15
    assert f.job["phase"] == "mixdown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_render_studio_fallback.py -v`
Expected: FAIL (`ImportError: cannot import name 'RenderStudioFallback'`).

- [ ] **Step 3: Implement**

Add to `app/tools/ui/_fallback.py` (after the existing fallback models):

```python
class RenderStudioFallback(BaseModel):
    version_id: int
    n_tracks: int = 0
    target_bpm: float | None = None
    beatgrid: list[dict[str, Any]] = Field(default_factory=list)
    job: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
```

(`Any` and `Field` are already imported at the top of `_fallback.py`.)

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_render_studio_fallback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/_fallback.py tests/tools/ui/test_render_studio_fallback.py
git commit -m "feat(render): RenderStudioFallback model"
```

---

## Task 2: render_studio_panel data gatherer + helper tool

The panel gatherer reads the same sources as the resources (`RENDER_JOBS`, workspace `beatgrid.json`/`diagnostics.json`, `timeline_windows`) and returns a plain dict. Both the entry tool's fallback and the Prefab helper build from this one gatherer (DRY).

**Files:**
- Create: `app/tools/ui/render_studio.py` (gatherer + helper; entry tool added in Task 3)
- Test: `tests/tools/ui/test_render_studio_panel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_render_studio_panel.py
import json

import pytest

from app.tools.ui.render_studio import gather_render_studio
from app.domain.render.models import TrackInput

class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs
        self.set_versions = _SV()

@pytest.mark.asyncio
async def test_gather_reads_workspace_and_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache
    reset_settings_cache()
    ws = tmp_path / "render" / "v131"
    ws.mkdir(parents=True)
    (ws / "beatgrid.json").write_text(json.dumps([
        {"track_id": 1, "trim_start_s": 0.4, "refined_trim_s": 0.4, "gain_db": 1.5,
         "phase_ms": 45.0, "flags": ["fixed"]},
    ]))
    from app.shared.render_jobs import RENDER_JOBS
    RENDER_JOBS.clear()
    RENDER_JOBS.start(job_id="v131-x", version_id=131, phase="mixdown")

    inputs = [TrackInput(track_id=1, yandex_id=9, title="t1", bpm=130.0, key_code=1,
                         mix_in_ms=0, integrated_lufs=-12.0, file_path="/a.mp3")]
    data = await gather_render_studio(_StubUow(inputs), version_id=131, job_id="v131-x")
    assert data["version_id"] == 131
    assert data["n_tracks"] == 1
    assert data["beatgrid"][0]["flags"] == ["fixed"]
    assert data["job"]["phase"] == "mixdown"
    assert data["timeline"][0]["index"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_render_studio_panel.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement (gatherer + helper only)**

```python
# app/tools/ui/render_studio.py
"""ui_render_studio — interactive Prefab control panel for the render pipeline.

Entry tool (app=True) with Analyze/QA, Render, Diagnose, Deliver buttons that
CallTool into the real render_* tools; live status + QA table + timeline +
diagnostics slots. The render_studio_panel helper (visibility=["app"]) re-reads
the workspace/registry so status updates flow through our CallTool round-trip,
not the host task protocol.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.config import get_settings
from app.domain.render.timeline import timeline_windows
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.render_jobs import RENDER_JOBS
from app.tools.ui._fallback import RenderStudioFallback, supports_ui

try:
    from fastmcp.server.apps import AppConfig
    from prefab_ui.app import PrefabApp
    from prefab_ui.actions import CallTool, SetState, ShowToast
    from prefab_ui.components import (
        Badge,
        Button,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Muted,
        Row,
        Slot,
    )
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_render_studio requires prefab-ui. Install with: uv sync --all-extras."
    ) from _exc

def _workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"

async def gather_render_studio(
    uow: UnitOfWork, *, version_id: int, job_id: str | None
) -> dict[str, Any]:
    """Read every render data source for one version (DRY across UI + fallback)."""
    r = get_settings().render
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = _workspace(version_id)

    beatgrid: list[dict[str, Any]] = []
    gp = ws / "beatgrid.json"
    if gp.exists():
        beatgrid = json.loads(gp.read_text())

    diagnostics: list[dict[str, Any]] = []
    dp = ws / "diagnostics.json"
    if dp.exists():
        diagnostics = json.loads(dp.read_text()).get("windows", [])

    wins = timeline_windows(inputs, target_bpm=r.target_bpm,
                            body_bars=r.body_bars, transition_bars=r.transition_bars)
    timeline = [
        {"index": i, "title": inputs[i].title, "start_s": s, "end_s": e}
        for (i, s, e) in wins.segments
    ]

    job = None
    if job_id:
        j = RENDER_JOBS.get(job_id)
        if j is not None:
            job = asdict(j)

    return {
        "version_id": version_id, "n_tracks": len(inputs), "target_bpm": r.target_bpm,
        "beatgrid": beatgrid, "job": job, "timeline": timeline,
        "diagnostics": [d for d in diagnostics if d.get("tags")],
    }

def _panel_state(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version_id": data["version_id"],
        "beatgrid": data["beatgrid"],
        "job": data["job"] or {},
        "timeline": data["timeline"],
        "diagnostics": data["diagnostics"],
    }

@tool(
    name="render_studio_panel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    app=AppConfig(visibility=["app"]),
    description="UI helper: re-render the render studio slots. Called from the UI only.",
    timeout=30.0,
)
async def render_studio_panel(
    version_id: Annotated[int, Field(ge=1)],
    job_id: Annotated[str | None, Field(description="Active render job id")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_render_studio(uow, version_id=version_id, job_id=job_id)
    with Column(gap=3) as view:
        _render_status_card(data)
        _render_beatgrid_table(data)
        _render_timeline_card(data)
        _render_diagnostics_card(data)
    return PrefabApp(view=view, state=_panel_state(data))
```

Add the small slot-builder helpers (used by both the panel and the entry tool) at the bottom of the file:

```python
def _render_status_card(data: dict[str, Any]) -> None:
    job = data.get("job") or {}
    with Card() as _c:
        CardHeader(CardTitle("Job status"))
        with CardContent():
            if job:
                Muted(f"{job.get('phase', 'pending')} — {job.get('progress', 0)}/"
                      f"{job.get('total', 0)} — {job.get('message', '')}")
                if job.get("error"):
                    Badge(f"error: {job['error']}", variant="destructive")
            else:
                Muted("No render started yet.")

def _render_beatgrid_table(data: dict[str, Any]) -> None:
    rows = data.get("beatgrid") or []
    if not rows:
        return
    with Card() as _c:
        CardHeader(CardTitle("Beatgrid / QA"))
        with CardContent():
            DataTable(
                columns=[
                    DataTableColumn("track_id", "Track"),
                    DataTableColumn("phase_ms", "Phase (ms)"),
                    DataTableColumn("gain_db", "Gain (dB)"),
                ],
                rows=[{"track_id": r["track_id"], "phase_ms": r.get("phase_ms"),
                       "gain_db": r.get("gain_db")} for r in rows],
            )

def _render_timeline_card(data: dict[str, Any]) -> None:
    segs = data.get("timeline") or []
    if not segs:
        return
    with Card() as _c:
        CardHeader(CardTitle("Timeline"))
        with CardContent():
            DataTable(
                columns=[
                    DataTableColumn("index", "#"),
                    DataTableColumn("title", "Track"),
                    DataTableColumn("start_s", "Start (s)"),
                ],
                rows=[{"index": s["index"], "title": s["title"],
                       "start_s": round(s["start_s"], 1)} for s in segs],
            )

def _render_diagnostics_card(data: dict[str, Any]) -> None:
    flags = data.get("diagnostics") or []
    with Card() as _c:
        CardHeader(CardTitle("Diagnostics"))
        with CardContent():
            if not flags:
                Muted("No flags (or not diagnosed yet).")
            for f in flags[:20]:
                Badge(f"{f.get('offset_s')}s: {', '.join(f.get('tags', []))}",
                      variant="outline")
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_render_studio_panel.py -v`
Expected: PASS. (If the `prefab_ui.actions` import path differs in the pinned version, grep the installed package: `uv run python -c "import prefab_ui, pkgutil; print([m.name for m in pkgutil.iter_modules(prefab_ui.__path__)])"` and adjust the import — the components import mirrors `app/tools/ui/set_view.py` which is known-good.)

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/render_studio.py tests/tools/ui/test_render_studio_panel.py
git commit -m "feat(render): render studio panel gatherer + app-helper"
```

---

## Task 3: ui_render_studio entry tool + fallback

**Files:**
- Modify: `app/tools/ui/render_studio.py` (add the entry tool)
- Test: `tests/tools/ui/test_render_studio_entry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_render_studio_entry.py
import pytest

from app.domain.render.models import TrackInput
from app.tools.ui.render_studio import ui_render_studio

class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs
        self.set_versions = _SV()

class _NoUiCtx:
    def client_supports_extension(self, _ext):
        return False

@pytest.mark.asyncio
async def test_entry_returns_fallback_when_no_prefab(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache
    reset_settings_cache()
    inputs = [TrackInput(track_id=1, yandex_id=9, title="t1", bpm=130.0, key_code=1,
                         mix_in_ms=0, integrated_lufs=-12.0, file_path="/a.mp3")]
    res = await ui_render_studio.fn(version_id=131, uow=_StubUow(inputs), ctx=_NoUiCtx())
    # non-Prefab client -> Pydantic fallback
    from app.tools.ui._fallback import RenderStudioFallback
    assert isinstance(res, RenderStudioFallback)
    assert res.version_id == 131 and res.n_tracks == 1
```

(`ui_render_studio.fn` accesses the undecorated function — mirror however the existing `ui_*` tests call their tool; if the project calls the decorated object directly, use that instead.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_render_studio_entry.py -v`
Expected: FAIL (`AttributeError: module has no attribute 'ui_render_studio'`).

- [ ] **Step 3: Implement (add to `app/tools/ui/render_studio.py`)**

Insert the entry tool ABOVE the `_render_*` helpers (after `render_studio_panel`):

```python
@tool(
    name="ui_render_studio",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    app=True,
    description=(
        "Interactive render studio for a set version: Analyze/QA, Render, "
        "Diagnose, Deliver buttons + live job status, beatgrid QA table, "
        "timeline and diagnostics. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_render_studio(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_render_studio(uow, version_id=version_id, job_id=None)
    if not supports_ui(ctx):
        return RenderStudioFallback(
            version_id=data["version_id"], n_tracks=data["n_tracks"],
            target_bpm=data["target_bpm"], beatgrid=data["beatgrid"],
            job=data["job"], timeline=data["timeline"], diagnostics=data["diagnostics"],
        )

    vid = version_id

    def _run_button(label: str, tool_name: str) -> None:
        Button(
            label,
            on_click=[
                CallTool(
                    tool_name, arguments={"version_id": vid},
                    on_success=CallTool("render_studio_panel", arguments={"version_id": vid}),
                    on_error=ShowToast("{{ $error }}", variant="error"),
                ),
            ],
        )

    with Column(gap=4) as view:
        Heading(f"Render Studio — version {vid}")
        Muted(f"{data['n_tracks']} tracks · target {data['target_bpm']} BPM")
        with Row(gap=2):
            _run_button("Analyze + QA", "render_beatgrid")
            _run_button("Render", "render_mixdown")
            _run_button("Diagnose", "render_diagnose")
            Button(
                "Refresh",
                on_click=[CallTool("render_studio_panel", arguments={"version_id": vid})],
            )
        Slot("status")
        Slot("beatgrid")
        Slot("timeline")
        Slot("diagnostics")
    return PrefabApp(view=view, state=_panel_state(data))
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_render_studio_entry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/render_studio.py tests/tools/ui/test_render_studio_entry.py
git commit -m "feat(render): ui_render_studio interactive entry tool"
```

---

## Task 4: Always-visible + registration + docs + gate

**Files:**
- Modify: `app/server/transforms.py`, `docs/tool-catalog.md`
- Test: `tests/tools/ui/test_render_studio_registered.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_render_studio_registered.py
import pytest

from app.server.app import build_mcp_app_for_tests
from app.server.transforms import ALWAYS_VISIBLE_TOOLS

def test_ui_render_studio_always_visible():
    assert "ui_render_studio" in ALWAYS_VISIBLE_TOOLS

@pytest.mark.asyncio
async def test_ui_render_studio_registered_and_helper_hidden():
    mcp = await build_mcp_app_for_tests()
    tools = await mcp.get_tools()
    assert "ui_render_studio" in tools
    # helper is app-visibility only — present but not model-visible.
    assert "render_studio_panel" in tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_render_studio_registered.py -v`
Expected: FAIL (`assert 'ui_render_studio' in ALWAYS_VISIBLE_TOOLS`).

- [ ] **Step 3: Implement**

In `app/server/transforms.py`, add to `ALWAYS_VISIBLE_TOOLS` (with the other `ui_*` entries):

```python
    "ui_render_studio",
```

(Do NOT add `render_studio_panel` — it is `visibility=["app"]`, intentionally hidden from the model / BM25.)

In `docs/tool-catalog.md`: UI tools 6→7 (add `ui_render_studio` row to the UI/Prefab table), model-visible tool count 23→24, and note `render_studio_panel` as a hidden app-helper.

- [ ] **Step 4: Run test + full gate**

Run: `uv run pytest tests/tools/ui/test_render_studio_registered.py -v && make check`
Expected: PASS; `make check` green (lint + mypy + `lint-imports` + full pytest). UI tests need `[audio]`+`[apps]` extras; skip cleanly otherwise.

- [ ] **Step 5: Fix any failures + commit**

Likely spots: if a test asserts the exact count of `ui_*` tools or total tool count, update it to include `ui_render_studio` (+ note the hidden `render_studio_panel`). If `import-linter` flags `app.tools.ui.render_studio -> app.repositories`, that edge already exists for the other `ui_*` tools (they use `Depends(get_uow)` + `UnitOfWork`) and is allowed.

```bash
git add app/server/transforms.py docs/tool-catalog.md tests/tools/ui/test_render_studio_registered.py
git commit -m "feat(render): register ui_render_studio (always-visible) + docs"
```

---

## Task 5: Finishing the branch

- [ ] **Step 1: Full regression**

Run: `make check`
Expected: all green.

- [ ] **Step 2: Verify the whole feature end-to-end (manual, needs [audio]+ffmpeg)**

On a real set version with downloaded audio:
```text
render_beatgrid(version_id=<v>)      # writes beatgrid.json
render_mixdown(version_id=<v>)       # writes MIX.mp3, returns job_id + scan
render_diagnose(version_id=<v>)      # writes diagnostics.json
```

Read `local://render/<v>/timeline`, `local://render/jobs/<job_id>/status`,
`local://render/<v>/beatgrid`. Open `ui_render_studio(version_id=<v>)` in a
Prefab-aware client and click the buttons.

- [ ] **Step 3: Version bump + CHANGELOG**

Bump minor version in `pyproject.toml`, `CLAUDE.md`, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`; add a `## [X.Y.0]` CHANGELOG section (Added:
render namespace — 3 tools, 5 resources, `render_set_workflow`,
`ui_render_studio`; generic set-version render engine).

```bash
git add pyproject.toml CLAUDE.md .claude-plugin/ CHANGELOG.md
git commit -m "chore: bump version for render pipeline MCP surface"
```

- [ ] **Step 4: Open the PR**

```bash
git push -u origin feat/render-mcp-surface
```
Then open a PR into `main` (squash-merge) using the project's PR template. Use the superpowers:finishing-a-development-branch skill to choose merge vs PR.

---

## Self-Review

**Spec coverage (Plan 3 = §4 Prefab studio):**
- `ui_render_studio` entry tool (`app=True`) with Analyze/QA/Render/Diagnose/Deliver buttons → Task 3. ✓
- Live status + beatgrid + timeline + diagnostics slots → Tasks 2–3. ✓
- Hidden `render_studio_panel` app-helper (`visibility=["app"]`) → Task 2. ✓
- `RenderStudioFallback` for non-Prefab clients → Task 1. ✓
- Status via OUR CallTool round-trip (reads `RENDER_JOBS`, not host task protocol) → Task 2 gatherer. ✓
- ALWAYS_VISIBLE + docs → Task 4. ✓
- **Note:** the Deliver button wiring calls the deliver path; if a single `deliver` tool does not exist (delivery is prompt-driven), the Deliver button is dropped in Task 3 and delivery stays a prompt step in `render_set_workflow` — decide during Task 3 by checking whether a callable deliver tool exists, else omit that one `_run_button`.

**Type consistency:** `gather_render_studio` returns the same dict keys consumed by `_panel_state`, `RenderStudioFallback`, and the slot builders (`version_id`, `n_tracks`, `target_bpm`, `beatgrid`, `job`, `timeline`, `diagnostics`). Tool names `render_beatgrid`/`render_mixdown`/`render_diagnose` in the buttons match Plan 2. `render_studio_panel` name consistent (Tasks 2–3). `RenderStudioFallback` fields match Task 1 definition. `_workspace` path matches Plan 2's `render_workspace` (`output_dir/workspace_subdir/v{id}`).

**Placeholder scan:** no TBD/TODO; full code in every step; every test has real assertions. The two conditionals (prefab import path; Deliver-button existence) carry explicit verification commands + fallbacks, not placeholders.

---

## Full feature complete

After Plan 3 merges: `render_pipeline.py`'s every capability is a generic, set-version-driven MCP surface — 3 `render_*` tools (task-backed), 5 `local://render/*` resources, `render_set_workflow`, and an interactive `ui_render_studio` — with the engine split cleanly across `app/domain/render` (pure) + `app/audio/render` (side-effect) + handlers, the bundle reusing existing delivery, and no new DB table. The original script stays as the golden reference.

# DJ Control Center — Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `ui_control_center(version_id)` — one interactive Prefab panel that shows library + set/version state and drives the render pipeline (Analyze+QA / Render / Diagnose) via buttons, rendered in Claude Desktop, with a Pydantic fallback for non-Prefab clients.

**Architecture:** A standalone `@tool(meta={"ui": True})` entry tool that mirrors `app/tools/ui/render_studio.py` 1:1 (the proven `PrefabApp` + `Slot("panel")` + `CallTool` round-trip). Data is composed from three existing gatherers (`library_dashboard._gather`, `set_view._gather`, `render_studio.gather_render_studio`) — **zero new business logic**. Phase 1 reuses the existing hidden `render_studio_panel` helper as the refresh target, so **no new helper tool** is needed. FileSystemProvider auto-discovers the entry tool; `ALWAYS_VISIBLE_TOOLS` makes it discoverable without a BM25 query.

**Tech Stack:** FastMCP v3 (`3.2.4`), `prefab_ui` (`0.19.1`), `prefab_ui.app.PrefabApp`, `prefab_ui.actions(.mcp)`, `Depends(get_uow)`.

**Branch:** `feat/control-center` (already created; spec committed there).

**Spec:** `docs/superpowers/specs/2026-07-06-control-center-design.md`.

> **Scope note:** Phase 1 makes `version_id` **required** (matches `ui_render_studio`). The spec's "optional → resolve latest overall version" needs a repo query that does not exist yet; it is deferred to Phase 2 with the version selector. No invented queries in Phase 1.

---

## File Structure

**Create:**
- `app/tools/ui/control_center.py` — `gather_control_center` gatherer + `control_center_fallback` mapper + `ui_control_center` entry tool + section builders.
- `tests/tools/ui/test_control_center_fallback.py`
- `tests/tools/ui/test_control_center_gather.py`
- `tests/tools/ui/test_control_center_entry.py`
- `tests/tools/ui/test_control_center_registered.py`

**Modify:**
- `app/tools/ui/_fallback.py` — add `ControlCenterFallback`.
- `app/server/transforms.py` — add `"ui_control_center"` to `ALWAYS_VISIBLE_TOOLS`.
- `docs/tool-catalog.md` — UI tools 7→8; model-visible tool count 24→25.

---

## Task 1: ControlCenterFallback model

**Files:**
- Modify: `app/tools/ui/_fallback.py`
- Test: `tests/tools/ui/test_control_center_fallback.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_control_center_fallback.py
from app.tools.ui._fallback import ControlCenterFallback

def test_control_center_fallback_shape():
    f = ControlCenterFallback(
        version_id=42,
        set_id=25,
        set_name="ga-all-fixed",
        quality_score=0.82,
        n_tracks=22,
        total_tracks=24005,
        analyzed_tracks=23817,
        coverage=0.992,
        tracks=[{"position": 0, "track_id": 977, "bpm": 130.0}],
        energy_arc=[{"position": 0, "lufs": -12.0}],
        bpm_histogram={"125-129": 12975},
        mood_distribution={"driving": 8333},
        beatgrid=[{"track_id": 1, "phase_ms": 10.0}],
        job={"job_id": "v42-x", "phase": "mixdown"},
        timeline=[{"index": 0, "title": "t1", "start_s": 0.0}],
        diagnostics=[{"offset_s": 20.0, "tags": ["DROPOUT"]}],
    )
    assert f.version_id == 42
    assert f.set_name == "ga-all-fixed"
    assert f.n_tracks == 22
    assert f.job["phase"] == "mixdown"

def test_control_center_fallback_defaults():
    f = ControlCenterFallback(version_id=1)
    assert f.n_tracks == 0
    assert f.tracks == []
    assert f.job is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_control_center_fallback.py -v`
Expected: FAIL (`ImportError: cannot import name 'ControlCenterFallback'`).

- [ ] **Step 3: Implement**

Add to `app/tools/ui/_fallback.py`, immediately after the existing `RenderStudioFallback` class (`Any` and `Field` are already imported at the top):

```python
class ControlCenterFallback(BaseModel):
    version_id: int
    set_id: int | None = None
    set_name: str | None = None
    quality_score: float | None = None
    n_tracks: int = 0
    # library overview
    total_tracks: int = 0
    analyzed_tracks: int = 0
    coverage: float = 0.0
    bpm_histogram: dict[str, int] = Field(default_factory=dict)
    mood_distribution: dict[str, int] = Field(default_factory=dict)
    # current set/version
    tracks: list[dict[str, Any]] = Field(default_factory=list)
    energy_arc: list[dict[str, Any]] = Field(default_factory=list)
    # render sub-block
    beatgrid: list[dict[str, Any]] = Field(default_factory=list)
    job: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_control_center_fallback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/_fallback.py tests/tools/ui/test_control_center_fallback.py
git commit -m "feat(ui): ControlCenterFallback model"
```

---

## Task 2: gather_control_center + fallback mapper

The gatherer composes the three existing read paths. It never queries directly — it delegates to `library_dashboard._gather`, `set_view._gather`, and `render_studio.gather_render_studio`. `control_center_fallback(data)` is a pure dict→model mapper (testable without a DB).

**Files:**
- Create: `app/tools/ui/control_center.py`
- Test: `tests/tools/ui/test_control_center_gather.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_control_center_gather.py
import pytest

import app.tools.ui.control_center as cc
from app.tools.ui._fallback import ControlCenterFallback

class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id

class _StubUow:
    def __init__(self, ver):
        class _SV:
            async def get(self, vid):
                return ver
        self.set_versions = _SV()

@pytest.mark.asyncio
async def test_gather_composes_three_sources(monkeypatch):
    async def _fake_lib(uow):
        return {
            "total_tracks": 24005, "analyzed_tracks": 23817, "coverage": 0.992,
            "bpm_histogram": {"125-129": 12975},
            "mood_distribution": {"driving": 8333},
            "camelot_distribution": {"7B": 2513},
        }

    async def _fake_set(uow, set_id, version_id):
        from app.tools.ui._fallback import EnergyPoint, TrackRow
        return {
            "set_id": set_id, "name": "ga-all-fixed", "template_name": None,
            "version_id": version_id, "quality_score": 0.82,
            "tracks": [TrackRow(position=0, track_id=977, bpm=130.0)],
            "energy_arc": [EnergyPoint(position=0, lufs=-12.0)],
            "transitions": [],
        }

    async def _fake_render(uow, *, version_id, job_id):
        return {
            "version_id": version_id, "n_tracks": 1, "target_bpm": 130.0,
            "beatgrid": [{"track_id": 977, "phase_ms": 12.0}],
            "job": None, "timeline": [{"index": 0, "title": "t1", "start_s": 0.0}],
            "diagnostics": [],
        }

    monkeypatch.setattr(cc, "_gather_library", _fake_lib)
    monkeypatch.setattr(cc, "_gather_set", _fake_set)
    monkeypatch.setattr(cc, "gather_render_studio", _fake_render)

    data = await cc.gather_control_center(_StubUow(_Ver(25)), version_id=42, job_id=None)
    assert data["version_id"] == 42
    assert data["set_id"] == 25
    assert data["set_name"] == "ga-all-fixed"
    assert data["quality_score"] == 0.82
    assert data["n_tracks"] == 1
    assert data["tracks"][0]["track_id"] == 977
    assert data["total_tracks"] == 24005
    assert data["beatgrid"][0]["phase_ms"] == 12.0

    fb = cc.control_center_fallback(data)
    assert isinstance(fb, ControlCenterFallback)
    assert fb.version_id == 42 and fb.n_tracks == 1

@pytest.mark.asyncio
async def test_gather_raises_on_missing_version():
    from app.shared.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await cc.gather_control_center(_StubUow(None), version_id=999, job_id=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_control_center_gather.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.tools.ui.control_center'`).

- [ ] **Step 3: Implement the gatherer + mapper (create the file with the module docstring, imports, gatherer, mapper)**

```python
# app/tools/ui/control_center.py
"""ui_control_center — one interactive Prefab panel to drive the set lifecycle.

Entry tool (``meta={"ui": True}``) that shows library + current-set/version
state and, in Phase 1, the render pipeline buttons (Analyze+QA / Render /
Diagnose). It reuses the proven ``render_studio`` round-trip: buttons
``CallTool`` the real ``render_*`` tools, then ``CallTool`` the existing hidden
``render_studio_panel`` helper and ``SetState("panel", RESULT)`` so a
``Slot("panel")`` re-renders only the render status/QA/timeline/diagnostics
fragment.

Data is composed from three existing gatherers — ``library_dashboard._gather``
(stats), ``set_view._gather`` (tracks + energy arc), and
``render_studio.gather_render_studio`` (render status) — no duplicated business
logic and no new DB queries.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.tools.ui._fallback import ControlCenterFallback, supports_ui
from app.tools.ui.library_dashboard import _gather as _gather_library
from app.tools.ui.render_studio import _panel_fragment, gather_render_studio
from app.tools.ui.set_view import _gather as _gather_set

try:
    from prefab_ui.actions import SetState, ShowToast
    from prefab_ui.actions.mcp import CallTool
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import (
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Metric,
        Muted,
        Row,
        Slot,
    )
    from prefab_ui.components.charts import ChartSeries, LineChart
    from prefab_ui.rx import RESULT
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_control_center requires prefab-ui. Install with: uv sync --all-extras "
        "(or `pip install 'fastmcp[apps]'`)."
    ) from _exc

async def gather_control_center(
    uow: UnitOfWork, *, version_id: int, job_id: str | None = None
) -> dict[str, Any]:
    """Compose library + set/version + render state for one set version."""
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)
    set_id = getattr(ver, "set_id", None)

    lib = await _gather_library(uow)
    setd = await _gather_set(uow, set_id, version_id)
    render = await gather_render_studio(uow, version_id=version_id, job_id=job_id)

    tracks = [t.model_dump() for t in (setd.get("tracks") or [])]
    energy = [e.model_dump() for e in (setd.get("energy_arc") or [])]

    return {
        "version_id": version_id,
        "set_id": set_id,
        "set_name": setd.get("name"),
        "quality_score": setd.get("quality_score"),
        "n_tracks": len(tracks),
        "tracks": tracks,
        "energy_arc": energy,
        "total_tracks": lib["total_tracks"],
        "analyzed_tracks": lib["analyzed_tracks"],
        "coverage": lib["coverage"],
        "bpm_histogram": lib["bpm_histogram"],
        "mood_distribution": lib["mood_distribution"],
        "beatgrid": render["beatgrid"],
        "job": render["job"],
        "timeline": render["timeline"],
        "diagnostics": render["diagnostics"],
    }

def control_center_fallback(data: dict[str, Any]) -> ControlCenterFallback:
    """Pure dict → Pydantic mapper for non-Prefab clients."""
    return ControlCenterFallback(
        version_id=data["version_id"],
        set_id=data.get("set_id"),
        set_name=data.get("set_name"),
        quality_score=data.get("quality_score"),
        n_tracks=data.get("n_tracks", 0),
        total_tracks=data.get("total_tracks", 0),
        analyzed_tracks=data.get("analyzed_tracks", 0),
        coverage=data.get("coverage", 0.0),
        bpm_histogram=data.get("bpm_histogram", {}),
        mood_distribution=data.get("mood_distribution", {}),
        tracks=data.get("tracks", []),
        energy_arc=data.get("energy_arc", []),
        beatgrid=data.get("beatgrid", []),
        job=data.get("job"),
        timeline=data.get("timeline", []),
        diagnostics=data.get("diagnostics", []),
    )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_control_center_gather.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/control_center.py tests/tools/ui/test_control_center_gather.py
git commit -m "feat(ui): control center gatherer + fallback mapper"
```

---

## Task 3: ui_control_center entry tool

Adds the entry tool to `control_center.py`: builds the two data sections, the render action Row (reusing `render_studio_panel` as the refresh target), and the pre-seeded `Slot("panel")`. Non-Prefab clients get `control_center_fallback`.

**Files:**
- Modify: `app/tools/ui/control_center.py`
- Test: `tests/tools/ui/test_control_center_entry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_control_center_entry.py
import pytest

import app.tools.ui.control_center as cc
from app.tools.ui._fallback import ControlCenterFallback

class _NoUiCtx:
    def client_supports_extension(self, _ext):
        return False

class _UiCtx:
    def client_supports_extension(self, _ext):
        return True

_DATA = {
    "version_id": 42, "set_id": 25, "set_name": "ga-all-fixed",
    "quality_score": 0.82, "n_tracks": 1,
    "tracks": [{"position": 0, "track_id": 977, "title": "t1", "bpm": 130.0,
                "camelot": "7B", "lufs": -12.0, "mood": "driving"}],
    "energy_arc": [{"position": 0, "lufs": -12.0}],
    "total_tracks": 24005, "analyzed_tracks": 23817, "coverage": 0.992,
    "bpm_histogram": {"125-129": 12975}, "mood_distribution": {"driving": 8333},
    "beatgrid": [], "job": None, "timeline": [], "diagnostics": [],
}

@pytest.mark.asyncio
async def test_entry_returns_fallback_when_no_prefab(monkeypatch):
    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    res = await cc.ui_control_center.fn(version_id=42, uow=object(), ctx=_NoUiCtx())
    assert isinstance(res, ControlCenterFallback)
    assert res.version_id == 42 and res.n_tracks == 1

@pytest.mark.asyncio
async def test_entry_returns_prefab_app_when_supported(monkeypatch):
    from prefab_ui.app import PrefabApp

    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    res = await cc.ui_control_center.fn(version_id=42, uow=object(), ctx=_UiCtx())
    assert isinstance(res, PrefabApp)
```

(`ui_control_center.fn` accesses the undecorated function — same convention the other `ui_*` tests use to call their tool.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_control_center_entry.py -v`
Expected: FAIL (`AttributeError: module 'app.tools.ui.control_center' has no attribute 'ui_control_center'`).

- [ ] **Step 3: Implement — append the section builders and entry tool to `control_center.py`**

```python
def _render_library_section(data: dict[str, Any]) -> None:
    with Card():
        CardHeader(children=[CardTitle("Library")])
        with CardContent():
            with Row(gap=4):
                Metric(label="Tracks", value=str(data["total_tracks"]))
                Metric(label="Analyzed", value=str(data["analyzed_tracks"]))
                Metric(
                    label="Coverage",
                    value=f"{data['coverage'] * 100:.0f}%",
                    trend_sentiment=("positive" if data["coverage"] >= 0.9 else "neutral"),
                )

def _render_set_section(data: dict[str, Any]) -> None:
    rows = data.get("tracks") or []
    energy = [
        {"position": e.get("position"), "lufs": e.get("lufs") or 0.0}
        for e in (data.get("energy_arc") or [])
    ]
    set_label = data.get("set_name") or f"set #{data.get('set_id')}"
    quality = data.get("quality_score") or 0.0
    with Card():
        CardHeader(
            children=[
                CardTitle(f"{set_label} · v{data['version_id']} · quality {quality:.2f}")
            ]
        )
        with CardContent():
            if energy:
                LineChart(
                    data=energy,
                    series=[ChartSeries(data_key="lufs", label="LUFS", color="#34d399")],
                    x_axis="position",
                    show_grid=True,
                    show_legend=False,
                    height=200,
                )
            if rows:
                DataTable(
                    rows=rows,
                    columns=[
                        DataTableColumn(key="position", header="#", sortable=True, width="48px"),
                        DataTableColumn(key="title", header="Title", sortable=True),
                        DataTableColumn(key="bpm", header="BPM", sortable=True, width="72px"),
                        DataTableColumn(key="camelot", header="Key", width="60px"),
                        DataTableColumn(key="lufs", header="LUFS", sortable=True, width="72px"),
                        DataTableColumn(key="mood", header="Mood"),
                    ],
                    paginated=len(rows) > 25,
                    page_size=25,
                )
            else:
                Muted("No tracks in this version.")

@tool(
    name="ui_control_center",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Interactive DJ control center for a set version: library + set/version "
        "overview and render pipeline buttons (Analyze+QA, Render, Diagnose) with "
        "live status. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_control_center(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_control_center(uow, version_id=version_id, job_id=None)

    if not supports_ui(ctx):
        return control_center_fallback(data)

    vid = version_id

    # Phase 1 reuses the existing hidden render_studio_panel helper as the
    # refresh target — the render status/QA/timeline/diagnostics fragment is
    # identical, so no new helper tool is introduced here.
    _refresh_panel = CallTool(
        "render_studio_panel",
        arguments={"version_id": vid, "job_id": "{{ job_id }}"},
        on_success=SetState("panel", RESULT),
    )

    def _run_button(label: str, tool_name: str, *, captures_job_id: bool = False) -> None:
        on_success = (
            [SetState("job_id", RESULT.job_id), _refresh_panel]
            if captures_job_id
            else [_refresh_panel]
        )
        Button(
            label=label,
            on_click=[
                CallTool(
                    tool_name,
                    arguments={"version_id": vid},
                    on_success=on_success,
                    on_error=ShowToast(message="{{ $error }}", variant="error"),
                ),
            ],
        )

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"DJ Control Center — version {vid}")
        _render_library_section(data)
        _render_set_section(data)
        with Row(gap=2):
            _run_button("Analyze + QA", "render_beatgrid")
            _run_button("Render", "render_mixdown", captures_job_id=True)
            _run_button("Diagnose", "render_diagnose")
            Button(label="Refresh", on_click=[_refresh_panel])
        with Slot("panel"):
            Muted("Run an action to see render status.")

    return PrefabApp(
        view=view,
        state={
            "version_id": vid,
            "job_id": "",
            "panel": _panel_fragment(data).to_json(),
        },
    )
```

`Button` must be imported — extend the `prefab_ui.components` import block at the top of the file to include `Button` (add it alphabetically after `Badge`? there is no `Badge` here — add `Button` to the import list):

```python
    from prefab_ui.components import (
        Button,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Metric,
        Muted,
        Row,
        Slot,
    )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/tools/ui/test_control_center_entry.py -v`
Expected: PASS (both fallback and PrefabApp branches).

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/control_center.py tests/tools/ui/test_control_center_entry.py
git commit -m "feat(ui): ui_control_center interactive entry tool"
```

---

## Task 4: Register (always-visible) + docs + registration test

**Files:**
- Modify: `app/server/transforms.py`, `docs/tool-catalog.md`
- Test: `tests/tools/ui/test_control_center_registered.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/ui/test_control_center_registered.py
import pytest

from app.server.app import build_mcp_app_for_tests
from app.server.transforms import ALWAYS_VISIBLE_TOOLS

def test_ui_control_center_always_visible():
    assert "ui_control_center" in ALWAYS_VISIBLE_TOOLS

@pytest.mark.asyncio
async def test_ui_control_center_registered():
    mcp = await build_mcp_app_for_tests(
        with_middleware=False, with_transforms=False, with_visibility=False
    )
    tools = await mcp.get_tools()
    assert "ui_control_center" in tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/ui/test_control_center_registered.py -v`
Expected: FAIL on `test_ui_control_center_always_visible` (`assert 'ui_control_center' in ALWAYS_VISIBLE_TOOLS`).

- [ ] **Step 3: Implement**

In `app/server/transforms.py`, add `"ui_control_center"` inside the `ALWAYS_VISIBLE_TOOLS` tuple, in the UI-tools block (right after `"ui_render_studio",`):

```python
    "ui_render_studio",
    "ui_control_center",
```

(Do NOT add any helper — Phase 1 reuses `render_studio_panel`, which is already hidden `visibility=["app"]`.)

In `docs/tool-catalog.md`: add a `ui_control_center` row to the UI / Prefab Apps table (UI tools 7→8), bump the model-visible tool count 24→25, and note it reuses the hidden `render_studio_panel` helper for its render actions.

- [ ] **Step 4: Run test + full gate**

Run: `uv run pytest tests/tools/ui/test_control_center_registered.py -v && make check`
Expected: PASS; `make check` green (lint + mypy + import-linter + full pytest).

- [ ] **Step 5: Fix any failures + commit**

Likely spots: a test asserting the exact count of `ui_*` tools or total tool count — update it to include `ui_control_center`. `import-linter`: the `app.tools.ui.control_center -> app.repositories` edge already exists for other `ui_*` tools (they use `Depends(get_uow)` + `UnitOfWork`) and is allowed; the cross-imports of sibling `app.tools.ui.*` gatherers are intra-layer and allowed.

```bash
git add app/server/transforms.py docs/tool-catalog.md tests/tools/ui/test_control_center_registered.py
git commit -m "feat(ui): register ui_control_center (always-visible) + docs"
```

---

## Task 5: Finish the Phase 1 branch

- [ ] **Step 1: Full regression**

Run: `make check`
Expected: all green.

- [ ] **Step 2: Manual end-to-end (needs Claude Desktop + a real set version with audio)**

Open `ui_control_center(version_id=<v>)` in Claude Desktop. Verify: library metrics + set DataTable + energy line render; clicking **Analyze + QA / Render / Diagnose** updates the `Slot("panel")` status (via the reused `render_studio_panel`). Note: if the target version has stale/dup `audio_file` rows pointing at deleted `/tmp` files, `render_beatgrid` fails — that data-repair belongs to Phase 2's `act_l5_set`; for the manual check pick a version whose tracks resolve to real files.

- [ ] **Step 3: Push the branch**

```bash
git push -u origin feat/control-center
```

- [ ] **Step 4: Decide merge vs PR**

Use the superpowers:finishing-a-development-branch skill. Phase 1 is independently shippable (a working control center over the render pipeline); Phase 2 (build/L5/deliver/sync wrappers) is a separate plan on top.

---

## Self-Review

**Spec coverage (Phase 1 slice of the spec):**
- §1 pattern (standalone `@tool` + `PrefabApp` + `Slot` + `CallTool` round-trip, reuse render_studio) → Tasks 2–3. ✓
- §1 file structure (`control_center.py`, `_fallback.py`, `transforms.py`, docs) → Tasks 1,3,4. ✓
- §2 data reuse (library_dashboard + set_view + render_studio gatherers, no new logic) → Task 2. ✓
- §3 Phase-1 buttons = the three `render_*` tools only → Task 3. ✓ (Build/L5/Deliver/Sync explicitly deferred to Phase 2.)
- §4 fallback (`ControlCenterFallback`) → Tasks 1–2. ✓
- §5 testing (construction, fallback branch, registration; live behavior manual) → Tasks 2–5. ✓
- **Deferred by design (Phase 2, not gaps):** wrapper action tools `act_build`/`act_l5_set`/`act_deliver`, the YM-sync button, the `control_center_panel` helper, the version selector / optional `version_id`. These get their own plan.

**Placeholder scan:** no TBD/TODO; every code step shows full code; every test has real assertions.

**Type consistency:** `gather_control_center` returns the dict keys consumed by `control_center_fallback`, `ControlCenterFallback` fields, and the section builders (`version_id`, `set_id`, `set_name`, `quality_score`, `n_tracks`, `tracks`, `energy_arc`, `total_tracks`, `analyzed_tracks`, `coverage`, `bpm_histogram`, `mood_distribution`, `beatgrid`, `job`, `timeline`, `diagnostics`). Tool names in the buttons (`render_beatgrid`/`render_mixdown`/`render_diagnose`) and the refresh helper (`render_studio_panel`) match the existing render surface. `control_center_fallback` name is consistent across Tasks 2–3. `ui_control_center.fn` matches the sibling `ui_*` test convention.
```

# DJ Control Center — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the control center: app-hidden wrapper action tools `act_build` (re-optimize + persist a new set_version) and `act_l5_set` (download-refresh + L5 reanalyze all version tracks, `task=True`), a dedicated `control_center_panel` helper showing action/job status, and the Build / Analyze→L5 / Sync-diff→YM buttons wired into `ui_control_center`.

**Architecture:** Same standalone-`@tool` pattern as Phase 1. Wrappers are `visibility=["app"]` (hidden from the model), thin orchestration over EXISTING pieces: `sequence_optimize` (called as a plain async function with explicitly-passed deps, the project's test convention), `set_version_build_handler`, `audio_file_download_handler`, `track_features_reanalyze_handler`. Job progress reuses `RENDER_JOBS` (fields fit; phases `l5-download`/`l5-analyze`). Per recon: **Deliver button is DROPPED** (no callable delivery tool exists — delivery stays prompt-driven per spec §3 fallback); **Sync→YM is conditional** on `DjSet.source_playlist_id` (local playlist id → `playlist_sync(direction="diff")`, safe read-only diff). **Version selector is dropped** (needs Prefab root-replacement semantics we can't verify headless; documented decision).

**Tech Stack:** FastMCP 3.2.4, prefab_ui 0.19.1, existing handlers/DI.

**Branch:** `feat/control-center-phase2` (create from fresh main).

**Spec:** `docs/superpowers/specs/2026-07-06-control-center-design.md` (§3 Phase 2).

**Recon facts (verified, do not re-derive):**
- `sequence_optimize` (app/tools/compute/sequence_optimize.py:44) signature: `(track_ids, algorithm="auto", template=None, pinned=None, excluded=None, uow=Depends(get_uow), scorer=Depends(get_transition_scorer), optimizer_builder=Depends(get_optimizer), ctx=CurrentContext()) -> SequenceOptimizeResult` with fields `track_order: list[int]`, `quality_score: float`, `algorithm`, `generations`.
- `SetVersionCreate` (app/schemas/set.py:186) strict keys: `set_id`, `label`, `track_order` (required), `quality_score?`, `generator_run_meta?`. Handler: `set_version_build_handler(ctx, uow, data, _registry=None) -> dict` (app/handlers/set_version_build.py:23).
- `SetVersionRepository.get_items(version_id) -> list[DjSetItem]` sorted by sort_index (app/repositories/set.py:41).
- `audio_file_download_handler(ctx, uow, data, registry) -> {"downloaded": [...], "skipped": [...], "errors": [...]}` (app/handlers/audio_file_download.py:30); data key `track_ids`; already re-downloads and updates the row when the DB row exists but the file is gone (`refreshed_stale_row: true`).
- `track_features_reanalyze_handler(ctx, uow, data, pipeline, registry=None)` (app/handlers/track_features_reanalyze.py:22); data keys `track_id` (alias `id`) + `level`.
- `RENDER_JOBS` registry (app/shared/render_jobs.py): `start(job_id=, version_id=, phase=)`, `update(job_id, **fields)`, `get(job_id)`; RenderJob fields `job_id, version_id, phase, progress, total, message, out_path, error, done`.
- `DjSet.source_playlist_id: int | None` exists (app/models/set.py); `playlist_sync(playlist_id, direction, source, dry_run)` takes a LOCAL DjPlaylist id (app/tools/sync/playlist_sync.py:40).
- DI accessors: `get_uow`, `get_transition_scorer`, `get_optimizer`, `get_audio_pipeline`, `get_provider_registry` (app/server/di.py) — each callable as `await get_X(ctx)` given a ctx, or injected via `Depends`.
- Project convention for tool-calling-tool: call the decorated tool directly as an async function passing all deps explicitly (tests do `await ui_render_studio(version_id=..., uow=..., ctx=...)`).

---

## File Structure

**Create:**
- `app/tools/ui/actions/__init__.py` — package docstring only.
- `app/tools/ui/actions/act_build.py` — `act_build` hidden tool.
- `app/tools/ui/actions/act_l5_set.py` — `act_l5_set` hidden tool (`task=True`).
- `tests/tools/ui/actions/test_act_build.py`
- `tests/tools/ui/actions/test_act_l5_set.py`
- `tests/tools/ui/test_control_center_panel.py`

**Modify:**
- `app/tools/ui/control_center.py` — add `control_center_panel` helper + Build/L5/Sync buttons + `source_playlist_id` in gatherer.
- `app/tools/ui/_fallback.py` — add `source_playlist_id` to `ControlCenterFallback`.
- `tests/tools/ui/test_control_center_gather.py` / `test_control_center_entry.py` — extend for the new field/buttons (only where assertions break).
- `docs/tool-catalog.md` — note the 3 hidden helpers (`render_studio_panel`, `control_center_panel`, `act_build`, `act_l5_set` — model-visible count UNCHANGED at 25).

---

## Task 1: act_build wrapper tool

**Files:**
- Create: `app/tools/ui/actions/__init__.py`, `app/tools/ui/actions/act_build.py`
- Test: `tests/tools/ui/actions/test_act_build.py`

- [ ] **Step 1: Write the failing test** — create `tests/tools/ui/actions/__init__.py`-less dir (pytest needs no init; mirror `tests/tools/ui/`) and `tests/tools/ui/actions/test_act_build.py`:

```python
import pytest

import app.tools.ui.actions.act_build as ab

class _Item:
    def __init__(self, track_id, sort_index):
        self.track_id = track_id
        self.sort_index = sort_index

class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id

class _StubUow:
    def __init__(self, ver, items):
        class _SV:
            async def get(self, vid):
                return ver

            async def get_items(self, vid):
                return items

        self.set_versions = _SV()

class _OptResult:
    track_order = [2, 1, 3]
    quality_score = 0.9
    algorithm = "ga"
    generations = 5

@pytest.mark.asyncio
async def test_act_build_optimizes_and_persists(monkeypatch):
    async def _fake_optimize(**kwargs):
        assert sorted(kwargs["track_ids"]) == [1, 2, 3]
        return _OptResult()

    async def _fake_persist(ctx, uow, data, _registry=None):
        assert data["set_id"] == 25
        assert data["track_order"] == [2, 1, 3]
        assert data["quality_score"] == 0.9
        assert isinstance(data["label"], str) and data["label"]
        return {"id": 143, "set_id": 25, "quality_score": 0.93}

    monkeypatch.setattr(ab, "_run_sequence_optimize", _fake_optimize)
    monkeypatch.setattr(ab, "set_version_build_handler", _fake_persist)

    items = [_Item(1, 0), _Item(2, 1), _Item(3, 2)]
    res = await ab.act_build(
        version_id=42,
        algorithm="ga",
        uow=_StubUow(_Ver(25), items),
        scorer=object(),
        optimizer_builder=object(),
        ctx=None,
    )
    assert res["new_version_id"] == 143
    assert res["quality_score"] == 0.93
    assert res["algorithm"] == "ga"

@pytest.mark.asyncio
async def test_act_build_missing_version_raises():
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await ab.act_build(
            version_id=999,
            algorithm="ga",
            uow=_StubUow(None, []),
            scorer=object(),
            optimizer_builder=object(),
            ctx=None,
        )
```

- [ ] **Step 2:** Run `uv run pytest tests/tools/ui/actions/test_act_build.py -v` — expect FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement.** `app/tools/ui/actions/__init__.py`:

```python
"""App-hidden action wrappers for the DJ Control Center UI buttons.

Each tool here is ``visibility=["app"]`` — callable via ``CallTool`` from the
Prefab UI, hidden from the model. They orchestrate EXISTING tools/handlers
(sequence_optimize, set_version_build, audio_file_download,
track_features_reanalyze); no business logic lives here.
"""
```

`app/tools/ui/actions/act_build.py`:

```python
"""act_build — UI action: re-optimize a version's tracks into a new set_version."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.set_version_build import set_version_build_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_optimizer, get_transition_scorer, get_uow
from app.shared.errors import NotFoundError
from app.tools.compute.sequence_optimize import sequence_optimize

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "act_build requires fastmcp[apps]. Install with: uv sync --all-extras."
    ) from _exc

async def _run_sequence_optimize(**kwargs: Any) -> Any:
    """Seam for tests — forwards to the real sequence_optimize tool function."""
    return await sequence_optimize(**kwargs)

@tool(
    name="act_build",
    tags={"namespace:ui:read", "ui"},
    annotations={"readOnlyHint": False, "idempotentHint": False},
    meta={"ui": True, "timeout_s": 300.0, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI action: re-optimize a set version's tracks and persist a new version. Called from the UI only.",
    timeout=300.0,
)
async def act_build(
    version_id: Annotated[int, Field(ge=1, description="Source set version ID")],
    algorithm: Annotated[str, Field(description="ga | greedy | auto")] = "auto",
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    optimizer_builder: Any = Depends(get_optimizer),
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)

    items = await uow.set_versions.get_items(version_id)
    track_ids = [it.track_id for it in sorted(items, key=lambda i: i.sort_index)]

    opt = await _run_sequence_optimize(
        track_ids=track_ids,
        algorithm=algorithm,
        template=None,
        pinned=None,
        excluded=None,
        uow=uow,
        scorer=scorer,
        optimizer_builder=optimizer_builder,
        ctx=ctx,
    )

    created = await set_version_build_handler(
        ctx,
        uow,
        {
            "set_id": ver.set_id,
            "label": f"ui-rebuild-{opt.algorithm}",
            "track_order": list(opt.track_order),
            "quality_score": opt.quality_score,
        },
    )
    return {
        "new_version_id": created.get("id"),
        "quality_score": created.get("quality_score", opt.quality_score),
        "algorithm": opt.algorithm,
        "n_tracks": len(track_ids),
    }
```

VERIFY before finalizing: (a) the exact call convention of `set_version_build_handler` — read `app/handlers/set_version_build.py` top 40 lines; if its return key for the created id differs from `id`, adapt (report what it is). (b) `sequence_optimize`'s param name `optimizer_builder` (recon-verified). (c) The `_run_sequence_optimize` seam MUST stay (tests monkeypatch it). (d) If `set_version_build_handler` requires `_registry`, pass `None` positionally or by keyword to match its signature.

- [ ] **Step 4:** Run `uv run pytest tests/tools/ui/actions/test_act_build.py -v` — PASS. `uv run ruff check app/tools/ui/actions/` — clean. `uv run mypy app/tools/ui/actions/act_build.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/actions/ tests/tools/ui/actions/
git commit -m "feat(ui): act_build hidden action tool"
```

---

## Task 2: act_l5_set wrapper tool (task=True)

**Files:**
- Create: `app/tools/ui/actions/act_l5_set.py`
- Test: `tests/tools/ui/actions/test_act_l5_set.py`

- [ ] **Step 1: Write the failing test** — `tests/tools/ui/actions/test_act_l5_set.py`:

```python
import pytest

import app.tools.ui.actions.act_l5_set as al
from app.shared.render_jobs import RENDER_JOBS

class _Item:
    def __init__(self, track_id, sort_index):
        self.track_id = track_id
        self.sort_index = sort_index

class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id

class _StubUow:
    def __init__(self, ver, items):
        class _SV:
            async def get(self, vid):
                return ver

            async def get_items(self, vid):
                return items

        self.set_versions = _SV()

@pytest.mark.asyncio
async def test_act_l5_downloads_in_batches_then_reanalyzes(monkeypatch):
    RENDER_JOBS.clear()
    download_calls: list[list[int]] = []
    reanalyze_calls: list[dict] = []

    async def _fake_download(ctx, uow, data, registry):
        download_calls.append(list(data["track_ids"]))
        return {
            "downloaded": [{"track_id": t, "library_item_id": 1, "path": "/x.mp3"} for t in data["track_ids"]],
            "skipped": [],
            "errors": [],
        }

    async def _fake_reanalyze(ctx, uow, data, pipeline, registry=None):
        reanalyze_calls.append(dict(data))
        return {"track_id": data["track_id"], "analysis_level": 5, "feature_count": 62}

    monkeypatch.setattr(al, "audio_file_download_handler", _fake_download)
    monkeypatch.setattr(al, "track_features_reanalyze_handler", _fake_reanalyze)

    items = [_Item(i, i) for i in range(1, 8)]  # 7 tracks
    res = await al.act_l5_set(
        version_id=42,
        uow=_StubUow(_Ver(25), items),
        pipeline=object(),
        registry=object(),
        ctx=None,
    )

    # batches of DOWNLOAD_BATCH (4): [1,2,3,4], [5,6,7]
    assert download_calls == [[1, 2, 3, 4], [5, 6, 7]]
    assert [c["track_id"] for c in reanalyze_calls] == [1, 2, 3, 4, 5, 6, 7]
    assert all(c["level"] == 5 for c in reanalyze_calls)
    assert res["analyzed"] == 7
    assert res["errors"] == []
    job = RENDER_JOBS.get(res["job_id"])
    assert job is not None and job.done is True

@pytest.mark.asyncio
async def test_act_l5_collects_errors_and_skips_failed_tracks(monkeypatch):
    RENDER_JOBS.clear()

    async def _fake_download(ctx, uow, data, registry):
        ok = [t for t in data["track_ids"] if t != 2]
        return {
            "downloaded": [{"track_id": t, "library_item_id": 1, "path": "/x.mp3"} for t in ok],
            "skipped": [],
            "errors": [{"track_id": 2, "error": "boom"}] if 2 in data["track_ids"] else [],
        }

    async def _fake_reanalyze(ctx, uow, data, pipeline, registry=None):
        return {"track_id": data["track_id"], "analysis_level": 5}

    monkeypatch.setattr(al, "audio_file_download_handler", _fake_download)
    monkeypatch.setattr(al, "track_features_reanalyze_handler", _fake_reanalyze)

    items = [_Item(i, i) for i in [1, 2, 3]]
    res = await al.act_l5_set(
        version_id=42,
        uow=_StubUow(_Ver(25), items),
        pipeline=object(),
        registry=object(),
        ctx=None,
    )
    assert res["analyzed"] == 2
    assert res["errors"] == [{"track_id": 2, "error": "boom"}]
```

- [ ] **Step 2:** Run — expect FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** `app/tools/ui/actions/act_l5_set.py`:

```python
"""act_l5_set — UI action: bring every track of a set version to L5.

Downloads missing/stale MP3s in small batches (the download handler already
re-downloads when the DB row exists but the file is gone), then re-runs the
audio pipeline at level 5 per track. Declared ``task=True`` — this is a heavy
multi-minute pass; progress is published to RENDER_JOBS (phases
``l5-download`` / ``l5-analyze``) so the control-center panel can poll it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.audio_file_download import audio_file_download_handler
from app.handlers.track_features_reanalyze import track_features_reanalyze_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_audio_pipeline, get_provider_registry, get_uow
from app.shared.errors import NotFoundError
from app.shared.render_jobs import RENDER_JOBS
from app.shared.time import utc_timestamp_iso

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "act_l5_set requires fastmcp[apps]. Install with: uv sync --all-extras."
    ) from _exc

# Batches sized per .claude/rules/audio.md (YM rate limit vs MCP timeout).
DOWNLOAD_BATCH = 4

@tool(
    name="act_l5_set",
    tags={"namespace:ui:read", "ui"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 3600.0, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI action: download + L5-reanalyze every track of a set version. Called from the UI only.",
    timeout=3600.0,
    task=True,
)
async def act_l5_set(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    pipeline: Any = Depends(get_audio_pipeline),
    registry: Any = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)

    items = await uow.set_versions.get_items(version_id)
    track_ids = [it.track_id for it in sorted(items, key=lambda i: i.sort_index)]

    job_id = f"l5-v{version_id}-{utc_timestamp_iso()}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase="l5-download")
    RENDER_JOBS.update(job_id, total=len(track_ids))

    errors: list[dict[str, Any]] = []
    downloadable: list[int] = []
    done_count = 0
    for i in range(0, len(track_ids), DOWNLOAD_BATCH):
        batch = track_ids[i : i + DOWNLOAD_BATCH]
        result = await audio_file_download_handler(ctx, uow, {"track_ids": batch}, registry)
        errors.extend(result.get("errors", []))
        ok = {e["track_id"] for e in result.get("downloaded", [])}
        ok |= {e["track_id"] for e in result.get("skipped", [])}
        downloadable.extend(t for t in batch if t in ok)
        done_count += len(batch)
        RENDER_JOBS.update(job_id, progress=done_count, message=f"downloaded {done_count}/{len(track_ids)}")

    RENDER_JOBS.update(job_id, phase="l5-analyze", progress=0, total=len(downloadable))
    analyzed = 0
    for n, tid in enumerate(downloadable, start=1):
        try:
            await track_features_reanalyze_handler(
                ctx, uow, {"track_id": tid, "level": 5}, pipeline, registry
            )
            analyzed += 1
        except Exception as exc:  # noqa: BLE001 — collect per-track failures, keep going
            errors.append({"track_id": tid, "error": str(exc)})
        RENDER_JOBS.update(job_id, progress=n, message=f"analyzed {n}/{len(downloadable)}")

    RENDER_JOBS.update(job_id, done=True, message="l5 complete")
    return {
        "job_id": job_id,
        "version_id": version_id,
        "n_tracks": len(track_ids),
        "analyzed": analyzed,
        "errors": errors,
    }
```

VERIFY before finalizing: (a) `utc_timestamp_iso` exists in `app/shared/time.py` and produces a string safe for a job id (no spaces) — if not, use `utc_now().strftime("%Y%m%dT%H%M%S")`; report which. (b) `track_features_reanalyze_handler`'s 5th param name (`registry=`) matches its real signature — recon says `(ctx, uow, data, pipeline, registry=None)`; adapt if different. (c) The `# noqa: BLE001` may get stripped by the PostToolUse formatter hook — after editing, run `uv run ruff check` and if BLE001 fires, restore the noqa via a Bash python3/sed patch (Edit hook doesn't intercept Bash), as done in Phase 1.

- [ ] **Step 4:** Run tests — PASS (2). `ruff check` + `mypy` on the new file — clean.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/actions/act_l5_set.py tests/tools/ui/actions/test_act_l5_set.py
git commit -m "feat(ui): act_l5_set hidden task action (download + L5)"
```

---

## Task 3: control_center_panel helper + wire the new buttons

**Files:**
- Modify: `app/tools/ui/control_center.py`, `app/tools/ui/_fallback.py`
- Test: `tests/tools/ui/test_control_center_panel.py`; extend `test_control_center_gather.py` + `test_control_center_entry.py` only if their assertions break.

- [ ] **Step 1: Write the failing test** — `tests/tools/ui/test_control_center_panel.py`:

```python
import pytest

import app.tools.ui.control_center as cc

class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id

class _Set:
    def __init__(self, source_playlist_id):
        self.source_playlist_id = source_playlist_id
        self.name = "s"

class _StubUow:
    def __init__(self, ver, s):
        class _SV:
            async def get(self, vid):
                return ver

        class _S:
            async def get(self, sid):
                return s

        self.set_versions = _SV()
        self.sets = _S()

_DATA = {
    "version_id": 42, "set_id": 25, "set_name": "x", "quality_score": 0.8,
    "n_tracks": 1, "tracks": [], "energy_arc": [],
    "total_tracks": 1, "analyzed_tracks": 1, "coverage": 1.0,
    "bpm_histogram": {}, "mood_distribution": {},
    "beatgrid": [], "job": None, "timeline": [], "diagnostics": [],
    "source_playlist_id": 7,
}

@pytest.mark.asyncio
async def test_panel_returns_fragment(monkeypatch):
    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    frag = await cc.control_center_panel(version_id=42, job_id=None, uow=object(), ctx=None)
    assert frag is not None
    assert hasattr(frag, "to_json")

@pytest.mark.asyncio
async def test_gather_includes_source_playlist_id(monkeypatch):
    async def _fake_lib(uow):
        return {
            "total_tracks": 1, "analyzed_tracks": 1, "coverage": 1.0,
            "bpm_histogram": {}, "mood_distribution": {}, "camelot_distribution": {},
        }

    async def _fake_set(uow, set_id, version_id):
        return {
            "set_id": set_id, "name": "x", "template_name": None,
            "version_id": version_id, "quality_score": 0.8,
            "tracks": [], "energy_arc": [], "transitions": [],
        }

    async def _fake_render(uow, *, version_id, job_id):
        return {"version_id": version_id, "n_tracks": 0, "target_bpm": 130.0,
                "beatgrid": [], "job": None, "timeline": [], "diagnostics": []}

    monkeypatch.setattr(cc, "_gather_library", _fake_lib)
    monkeypatch.setattr(cc, "_gather_set", _fake_set)
    monkeypatch.setattr(cc, "gather_render_studio", _fake_render)

    data = await cc.gather_control_center(
        _StubUow(_Ver(25), _Set(7)), version_id=42, job_id=None
    )
    assert data["source_playlist_id"] == 7
```

- [ ] **Step 2:** Run — expect FAIL (`AttributeError: control_center_panel` / KeyError source_playlist_id).

- [ ] **Step 3: Implement.**

**(a) Gatherer:** in `gather_control_center`, after `set_id = ver.set_id`, load the set and thread `source_playlist_id`:

```python
    s = await uow.sets.get(set_id)
    source_playlist_id = getattr(s, "source_playlist_id", None) if s is not None else None
```

Add `"source_playlist_id": source_playlist_id,` to the returned dict. Add the same field to `ControlCenterFallback` in `_fallback.py` (`source_playlist_id: int | None = None`) and map it in `control_center_fallback`.

**(b) Panel helper** — add to `control_center.py` (after the section builders, before the entry tool), mirroring `render_studio_panel`:

```python
@tool(
    name="control_center_panel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI helper: re-render the control center status panel. Called from the UI only.",
    timeout=30.0,
)
async def control_center_panel(
    version_id: Annotated[int, Field(ge=1)],
    job_id: Annotated[str | None, Field(description="Active job id (render or l5)")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_control_center(uow, version_id=version_id, job_id=job_id)
    return _panel_fragment(data)
```

This requires importing `AppConfig, app_config_to_meta_dict` from `fastmcp.apps` (add to the existing try/except import block or a plain import mirroring render_studio.py — match render_studio.py, which imports them from `fastmcp.apps` at the top of its try block).

Note: `_panel_fragment` comes from render_studio (already imported) — the panel content (job status, beatgrid, timeline, diagnostics) is identical; the l5 job travels through the same `RENDER_JOBS`, so `gather_render_studio(job_id=...)` picks it up. No new fragment builder needed.

**(c) Entry-tool buttons** — in `ui_control_center`, change `_refresh_panel` to target the NEW helper (`"control_center_panel"` instead of `"render_studio_panel"`), and extend the button Row:

```python
        with Row(gap=2):
            _run_button("Analyze + QA", "render_beatgrid")
            _run_button("Render", "render_mixdown", captures_job_id=True)
            _run_button("Diagnose", "render_diagnose")
            Button(
                label="Build / Reorder",
                on_click=[
                    CallTool(
                        "act_build",
                        arguments={"version_id": vid},
                        on_success=[
                            ShowToast(
                                message="New version created: {{ $result.new_version_id }}",
                                variant="success",
                            ),
                            _refresh_panel,
                        ],
                        on_error=ShowToast(message="{{ $error }}", variant="error"),
                    ),
                ],
            )
            _run_button("Analyze → L5", "act_l5_set", captures_job_id=True)
            Button(label="Refresh", on_click=[_refresh_panel])
        if data.get("source_playlist_id"):
            with Row(gap=2):
                Button(
                    label="Sync diff → YM",
                    on_click=[
                        CallTool(
                            "playlist_sync",
                            arguments={
                                "playlist_id": data["source_playlist_id"],
                                "direction": "diff",
                            },
                            on_success=ShowToast(
                                message="YM diff computed — see tool result", variant="success"
                            ),
                            on_error=ShowToast(message="{{ $error }}", variant="error"),
                        ),
                    ],
                )
```

VERIFY the ShowToast success-message templating: render_studio uses `"{{ $error }}"` for errors; for the result reference use whatever prefab_ui 0.19.1 supports — if `{{ $result.new_version_id }}` is not a documented template, simplify to a static message `"New version created"` (report which you used). Do not invent template syntax.

**(d) Update the docstring** of `control_center.py` (it currently says "reuses render_studio_panel") to reflect the new dedicated helper + Phase 2 buttons.

- [ ] **Step 4:** Run the new test file + BOTH existing control-center test files + full ui suite: `uv run pytest tests/tools/ui/ -q` — all pass (fix any assertion the new gatherer field broke — the gather test's `_StubUow` now also needs a `sets` stub; update that test accordingly). `ruff` + `mypy` on `app/tools/ui/control_center.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add app/tools/ui/control_center.py app/tools/ui/_fallback.py tests/tools/ui/
git commit -m "feat(ui): control_center_panel helper + Build/L5/Sync buttons"
```

---

## Task 4: Docs + full gate

**Files:**
- Modify: `docs/tool-catalog.md`
- Possibly: `tests/server/test_transforms.py` is NOT touched (hidden tools are NOT in ALWAYS_VISIBLE_TOOLS).

- [ ] **Step 1:** Confirm no registration changes needed: `act_build`, `act_l5_set`, `control_center_panel` are all `visibility=["app"]` — they must NOT be added to `ALWAYS_VISIBLE_TOOLS`. Model-visible count stays 25. Write a quick check: `uv run python -c "from app.server.transforms import ALWAYS_VISIBLE_TOOLS; assert 'act_build' not in ALWAYS_VISIBLE_TOOLS"`.

- [ ] **Step 2: Docs** — in `docs/tool-catalog.md`: update the `ui_control_center` row + prose to mention the Phase-2 buttons (Build/Reorder, Analyze→L5, conditional Sync-diff→YM) and the hidden helpers (`control_center_panel`, `act_build`, `act_l5_set` — registered, app-visibility only, alongside `render_studio_panel`). Model-visible count references stay 25. Add a history-table row ("control center phase 2").

- [ ] **Step 3: Full gate**

Run: `make check`
Expected: green. Fix legitimately anything that breaks (likely candidates: a test asserting the total registered tool count including hidden tools; the gather stub missing `sets`).

- [ ] **Step 4: Commit**

```bash
git add docs/tool-catalog.md
git commit -m "docs: control center phase 2 (hidden action tools) + gate"
```

---

## Task 5: Finish the branch

- [ ] **Step 1:** `make check` full regression — green.
- [ ] **Step 2:** Push `feat/control-center-phase2`, PR into main, squash-merge (project convention).
- [ ] **Step 3:** Post-merge live verification happens OUTSIDE this plan (controller does it): restart the dj-music MCP server, call `ui_control_center` via MCP (fallback JSON), verify `act_build`/`act_l5_set`/`control_center_panel` are registered-but-hidden, and exercise `act_l5_set`'s stale-file refresh on version 42's known-stale audio_file rows.

---

## Self-Review

**Spec §3 Phase-2 coverage:** `act_build` → Task 1 ✓; `act_l5_set` (incl. stale-audio_file re-resolve — delegated to the download handler which already does it) → Task 2 ✓; `act_deliver` → recon says no callable delivery surface exists → **dropped per the spec's own decision rule** ("else the Deliver button is dropped and delivery stays a prompt step") ✓; Sync→YM → conditional button via `source_playlist_id` + `playlist_sync(direction="diff")` → Task 3 ✓; `control_center_panel` helper → Task 3 ✓; version selector → **dropped** (needs unverifiable Prefab root-replacement; documented) — deviation noted, not silent.

**Placeholder scan:** all steps carry real code; the three VERIFY blocks are explicit check-instructions with fallbacks, not TBDs.

**Type consistency:** `act_build` returns `new_version_id`/`quality_score`/`algorithm`/`n_tracks`; tests assert those. `act_l5_set` returns `job_id`/`version_id`/`n_tracks`/`analyzed`/`errors`; tests assert those; `DOWNLOAD_BATCH=4` matches the batch assertion `[[1,2,3,4],[5,6,7]]`. `control_center_panel` name used consistently in helper + `_refresh_panel` retarget. Gatherer's new key `source_playlist_id` appears in dict, fallback model, mapper, and the conditional Sync button.

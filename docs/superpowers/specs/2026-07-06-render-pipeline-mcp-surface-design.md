# Render Pipeline → MCP Surface — Design

> Date: 2026-07-06 · Status: approved (design) · Branch: `feat/render-mcp-surface`

## Goal

Expose every capability of `generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py`
through the MCP server, **generically parameterised by set version**, following
the project's bounded-context architecture, plus an **interactive Prefab UI**
control panel (per `prefab.prefect.io/docs/running/fastmcp`).

`render_pipeline.py` is a self-contained script that turns N techno tracks into
ONE continuous, beatmatched, EQ-bass-swap DJ mix (MP3), plus defect diagnostics
and a rekordbox/M3U8/cheatsheet bundle. It is currently hardcoded to one set
(`TRACKS`, `DB_LUFS`, one folder). This is a **new** capability for the project —
`app/audio/` today only *analyses* tracks; it does not *mix/render* them.

### Decisions locked during brainstorming

1. **Fully generic by set/version.** Any `version_id`: tracks / LUFS / mix-in
   points are pulled from the DB (`dj_set_items ⋈ tracks ⋈
   track_audio_features_computed ⋈ dj_library_items`); beatgrid/gain computed
   on the fly. The script becomes a parameterised engine in `app/domain` +
   `app/audio`.
2. **Heavy steps run via FastMCP `task=True`** (SEP-1686 background tasks) with
   a hybrid in-process status registry for degradation (see §3).
3. **Interactive Prefab control panel** (`app=True`), not a read-only dashboard.
4. **Surface shape A:** a dedicated `render` namespace + read-only resources +
   Prefab studio; reuse existing delivery for the bundle; no new DB table.

## 1. MCP Surface Contracts

### Tools — namespace `render` (tag `namespace:render`), all `task=True`

| Tool | Params | Effect / return |
|---|---|---|
| `render_beatgrid` | `version_id:int`, `refresh:bool=False` | librosa kick-phase detect + QA (sub-beat phase refine + LUFS level-match). Writes `beatgrid.json` to workspace. → `RenderBeatgridResult` (per-track `trim_start_s`, `refined_trim_s`, `gain_db`, `phase_ms`, `flags[]`). |
| `render_mixdown` | `version_id:int`, `out_name:str\|None`, `transition_bars:int\|None`, `body_bars:int\|None`, `refresh_grid:bool=False` | ffmpeg beatmatch (rubberband→target BPM) + 2-band EQ bass-swap transitions + brickwall limiter → continuous MP3. Auto-runs beatgrid if missing. → `RenderMixdownResult` (`job_id`, `out_path`, `duration_s`, scan summary: true-peak, level-jumps, near-silent). |
| `render_diagnose` | `job_id:str` **or** `version_id:int` | scan (coarse whole-file) + diagnose (per-4s librosa sweep) of a rendered file. Writes `diagnostics.json`. → `RenderDiagnosticsResult` (overall RMS, flagged windows tagged LEVEL-JUMP / DROPOUT / DECK-MISALIGN / bass-thin). |

All three use the `Progress` dependency. Namespace `render` is added to
`KNOWN_NAMESPACES` + `ALWAYS_VISIBLE_TOOLS`, visible by default (like `sync` /
`compute` — standalone verb-tools that are neither entity nor provider).

### Resources — read-only, cheap only (no heavy librosa inside a resource)

| URI | Returns |
|---|---|
| `local://render/{version_id}/timeline` | boundaries: segment list + transition windows (pure timeline math) |
| `local://render/{version_id}/beatgrid` | saved `beatgrid.json` (or typed 404 "run render_beatgrid") |
| `local://render/jobs/{job_id}/status` | live job progress from `RenderJobRegistry` |
| `local://render/jobs/{job_id}/diagnostics` | saved diagnostics report |
| `reference://render/defaults` | `RenderSettings` (BPM, bars, XSPLIT) for introspection |

### Prompt

`render_set_workflow(version_id)` — ensure L5 `audio_file` rows for every track →
`render_beatgrid` → `render_mixdown` → read diagnostics/timeline →
`deliver_set_workflow`. Honest about engine limits (no real stem separation;
phrasing approximate without DB beatgrid).

### Delivery reuse (no duplicate `bundle()`)

M3U8 / rekordbox XML / cheatsheet / track copy are already covered by
`deliver_set_workflow` + `DeliverySettings`. Add one toggle
`emit_continuous_mix: bool` and thread the rendered MP3 into the existing
deliverable bundle. No standalone `bundle` tool.

### UI

`ui_render_studio(version_id)` (`app=True`, namespace `ui:read`) + a hidden
app-helper (`visibility=["app"]`) — see §4.

**Surface total: +3 tools, +5 resources, +1 prompt, +1 UI tool, +1 delivery
toggle. No new DB table, no delivery duplication.**

## 2. Code Layer & Files

Respects the dependency rule: `tools → handlers → repositories → models`;
`tools → domain` (pure); `domain` imports only `models`+`shared`; `audio` is a
side-effect layer imported **only by handlers**.

### `app/domain/render/` — pure compute (no IO)

- `timeline.py` — segment math: `body_bars`/`d_in`/`d_out`/`L`, running `T`,
  overlap (from `_segment_sequence` / `boundaries`).
- `graph.py` — ffmpeg `filter_complex` string builder (asplit/lowpass/highpass,
  qsin afade in/out, low-swap, amix, adelay, alimiter) — pure string assembly.
- `levels.py` — gain-toward-median from LUFS (from `qa()`).
- `models.py` — dataclasses `TrackSegment`, `Transition`, `RenderPlan`,
  `BeatgridEntry` (pure, like `transition/score.py`).

### `app/audio/render/` — side-effect layer (librosa/scipy/ffmpeg subprocess)

- `kick_phase.py` — kick-grid detect (lowpass 150 Hz + onset + beat_track) from
  `analyze()`.
- `phase_refine.py` — QA sub-beat cross-correlation vs the target grid from
  `qa()`.
- `runner.py` — build ffmpeg command (uses `domain/render/graph.py`) + run
  subprocess, typed `RuntimeError` on failure (like the loader wrapper).
- `diagnostics.py` — `scan()` + `diagnose()` (per-4s sweep).
- librosa JIT warmup before the ffmpeg run (per `.claude/rules/audio.md` —
  multi-thread SEGV guard).

### `app/handlers/` — orchestration

- `render_beatgrid.py` — pull version tracks (repos) → `audio/render` kick_phase
  + phase_refine → write `beatgrid.json` → `RenderBeatgridResult`.
- `render_mixdown.py` — pull + ensure beatgrid → `domain/render` plan →
  `audio/render/runner` → register job in `RenderJobRegistry`, stream `Progress`
  → manifest.
- `render_diagnose.py` — `audio/render/diagnostics` → report.
- All via `safe_info` / `safe_report_progress`.

### `app/tools/render/` — thin dispatchers

`render_beatgrid.py` / `render_mixdown.py` / `render_diagnose.py` — only
`@tool(task=True)` + `Depends(get_uow)` → handler; typed Pydantic return.

### Repositories

New `SetVersionRepository.get_render_inputs(version_id)` — one batch query:
`dj_set_items`(sort_index, track_id, mix_in_point_ms) ⋈ `tracks`(title) ⋈
`track_audio_features_computed`(bpm, key_code, integrated_lufs) ⋈
`dj_library_items`(file_path). Replaces the hardcoded `TRACKS` / `DB_LUFS` /
`AUDIO_DIR` glob.

### Config

`app/config/render.py` — `RenderSettings` (`env_prefix="DJ_RENDER_"`):
`target_bpm=130.0`, `transition_bars=32`, `body_bars=24`, `xsplit_hz=180`,
`low_swap_bars=2`, `outro_fade_bars=12`, `limiter_ceiling=0.85`,
`workspace_root` (under `DeliverySettings.output_dir`). Removes the script's
magic numbers ("no magic numbers" rule).

### Workspace (no DB table)

`generated-sets/render/v{version_id}/` — `beatgrid.json`, `MIX.mp3`,
`diagnostics.json`, `manifest.json`.

### Schemas

`app/schemas/render.py` — `RenderBeatgridResult` / `RenderMixdownResult` /
`RenderDiagnosticsResult` + UI fallback models.

### Arch-linter

Add `app/domain/render` + `app/audio/render` to `import-linter` contracts
(domain does not import audio; audio imported only by handlers). `make arch`
pins the boundaries.

### External deps

ffmpeg built with `librubberband` (external, brew — as in the script header);
librosa/scipy/soundfile already in `[audio]`. `render_*` require the `[audio]`
extra.

## 3. Execution — FastMCP tasks + honest degradation

### Enable tasks

`app/server/app.py:build_mcp_server` → `FastMCP(..., tasks=True)`. Requires the
`fastmcp[tasks]` extra (Docket backend). Default in-memory/local Docket
(single-process, single-set render), no Redis. Add `fastmcp[tasks]` to a
`[tasks]` extra + `--all-extras`.

### Canonical path (task protocol)

`@tool(task=True)` + `Progress` dependency: task-capable hosts get `task_id`,
progress, and `await task.result()`. Handlers report
`progress.set_total/increment/set_message` per track (beatgrid) and per ffmpeg
phase (mixdown).

### Risk flag + hybrid status (from `.claude/rules/tools.md`)

Claude Code's support for the task protocol is **unconfirmed**. If the host
calls `render_mixdown` as a plain tool (no `task=True`), it may block to the
120 s timeout. Mitigation — a status track that does not depend on the task
protocol:

- **`RenderJobRegistry`** — module-level in-process registry
  (`job_id → {phase, progress, total, message, out_path, error, started_at}`).
  The handler writes progress to BOTH the `Progress` dependency AND the registry.
- **`local://render/jobs/{job_id}/status`** — resource reads the registry.
  Cheap, always works, independent of host task support.
- The Prefab studio (§4) polls status via **CallTool → app-helper → this
  registry** (a round-trip we control), not via the host task protocol. Live
  status in the UI works regardless.

### Degradation by environment

- Single set 15–20 tracks — **OK locally** (per `.claude/rules/audio.md`).
  `task=True` keeps the MCP session free.
- Missing ffmpeg/librubberband — typed `ToolError` (pierces
  `mask_error_details`) with `brew install ffmpeg`.
- Full-library runs are out of scope for this render (that is beatgrid/L5 on the
  VM, a separate story).

### Idempotency / cancel

Beatgrid cached in the workspace; `render_mixdown(refresh_grid=False)` reuses it.
`job_id` derived from `version_id` + a timestamp injected by the handler (pure
layer stays deterministic). Cancel: mark `cancelled` in the registry + best-effort
ffmpeg PID kill (optional for v1).

## 4. `ui_render_studio` (Prefab, app=True)

Entry tool `ui_render_studio(version_id)` — `@tool` with `meta={"ui": True}`,
namespace `ui:read`, in `ALWAYS_VISIBLE_TOOLS`. Returns `PrefabApp(view, state)`;
non-Prefab clients get a Pydantic fallback (`RenderStudioFallback`) via
`supports_ui(ctx)`, like the 6 existing `ui_*` tools.

### Layout

- `Heading` + version summary (tracks, total duration, target BPM).
- Action buttons (`Button` → `CallTool`):
  - **Analyze+QA** → `CallTool("render_beatgrid", {version_id})`, `on_success` →
    `CallTool("render_studio_panel", …)` → `SetState` slot; `on_error` →
    `ShowToast(variant="error")`.
  - **Render** → `CallTool("render_mixdown", {version_id})` (same pattern).
  - **Diagnose** → `CallTool("render_diagnose", {version_id})`.
  - **Deliver** → `CallTool` into the deliver path (`deliver_set_workflow`).
- `Slot("status")` — live job status (phase, progress bar, message) from
  `RenderJobRegistry`.
- `Slot("beatgrid")` — QA table: per-track phase ±ms, gain dB, flags
  (`DataTable`, colour via `app/shared/ui_colors.py`).
- `Slot("timeline")` — segments + transition windows (from
  `local://render/{version_id}/timeline`).
- `Slot("diagnostics")` — flagged defect windows.

### App-helper (hidden from the model)

`render_studio_panel(version_id, job_id:str|None)` with
`AppConfig(visibility=["app"])` — reads `RenderJobRegistry` + workspace files
(beatgrid/diagnostics) + timeline and returns a `PrefabApp` with updated slots.
Button `on_success` handlers and a Refresh button call it, so status updates
flow through OUR CallTool round-trip, not the host task protocol (ties to §3).

### Polling

After starting a render, `SetState("polling", true)`; a repeated
`CallTool("render_studio_panel")` (Refresh button + optional auto-repeat if a
Prefab interval/on_success chain is available — otherwise manual Refresh,
stated honestly) pulls fresh status.

### Files

`app/tools/ui/render_studio.py` + helper there or `app/tools/ui/_render_helpers.py`;
fallback models in `app/tools/ui/_fallback.py`. Palette from `ui_colors.py`. No
duplicated business logic — the helper reads the same workspace/registry as the
handlers.

## 5. Testing, Error Handling, Rollout

### Tests (mirror `app/`, in-memory SQLite, no network)

- `tests/domain/render/` — pure layer: `timeline` (segments/overlap/`T` match the
  script's reference numbers), `graph` (generated `filter_complex` = golden
  snapshot), `levels` (gain-to-median). Fast, deterministic.
- `tests/audio/render/` — synthetic WAV fixtures (128-BPM click track):
  `kick_phase` finds the kick at a known position; `phase_refine` snaps to grid;
  `diagnostics` flags an injected DROPOUT/LEVEL-JUMP. ffmpeg `runner` — smoke on
  2 short clips (marked, needs ffmpeg; else skip).
- `tests/handlers/` — `render_beatgrid`/`render_mixdown`/`render_diagnose` with
  `ctx=None` (headless `safe_info` fallback); mocked audio engine; assert
  manifest + `RenderJobRegistry` writes.
- `tests/repositories/` — `get_render_inputs` (seed set_version+items+features+
  library_items, INNER JOINs; FK on).
- `tests/tools/render/` + `tests/tools/ui/test_render_studio.py` — metadata (tags,
  `task=True`, annotations), `structured_content`, Prefab vs fallback branch.
- `tests/prompts/` — `render_set_workflow` in `EXPECTED_PROMPTS` +
  content-correctness (names resolve against runtime, else hard error).
- `tests/resources/` — `local://render/*` returns + 404 branches via
  `DomainErrorMiddleware`.
- `make check` (lint+typecheck+`arch`+test) — the only gate (no CI).
  `import-linter` contracts for the new `domain/render` + `audio/render`
  boundaries.

### Error handling

`ToolError` / `ResourceError` (pierce `mask_error_details`) for user-facing
cases: missing audio_file → "download first" (like L5), missing
ffmpeg/librubberband → brew instruction, version not found → `NotFoundError`.
Internal errors masked in prod.

### Rollout (PR into main, squash — per `.claude/rules/git.md`)

1. Branch `feat/render-mcp-surface`.
2. Atomic commits: config+domain → audio/render → handlers+repo → tools+resources
   → prompt → UI studio → delivery toggle → docs.
3. Docs: new `docs/render-pipeline.md` (engine + surface); update
   `docs/tool-catalog.md` (model-visible tools 20→24: +3 `render_*` +1
   `ui_render_studio`; the `render_studio_panel` app-helper is
   `visibility=["app"]`, hidden from the model; + new resources/prompts),
   `docs/architecture.md` (render bounded context), `.claude/rules/` as needed.
   Bump minor version (new feature).
4. `render_pipeline.py` stays in `generated-sets/…` as reference/golden source
   (not deleted — the source of truth for the numbers).

### Definition of Done

Generic `render_set_workflow(version_id)` builds a continuous beatmatched MP3
from any set version via MCP; the Prefab studio runs the steps interactively with
live status; diagnostics are readable; the deliver bundle includes the mix;
`make check` is green.

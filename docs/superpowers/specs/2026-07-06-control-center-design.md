# DJ Control Center — Design

> Date: 2026-07-06 · Status: approved (design) · Branch: `feat/control-center`

## Goal

One interactive Prefab control panel — `ui_control_center` — from which a DJ
drives the whole set-building lifecycle: see library + set state, then run
build / analyze-to-L5 / render / diagnose / deliver / YM-sync **by clicking
buttons**, without leaving the panel. Rendered in an MCP-apps host (Claude
Desktop); non-Prefab clients get a Pydantic fallback.

This is a **new composite surface** built entirely on the project's existing,
proven interactive-UI pattern. It adds no new DB table, no new runtime
mechanism, and duplicates no business logic — every action button `CallTool`s
an existing tool (or a thin app-only wrapper over existing tools/handlers).

### Explicitly out of scope

- **A raw-browser dashboard.** Verified against installed `fastmcp 3.2.4` +
  `prefab_ui 0.19.1`: FastMCP renders app UI inside an MCP **host** (the host
  builds the renderer iframe; interactivity flows through `CallTool` over MCP).
  A plain browser is not an MCP host. `prefab serve` yields a URL but renders a
  **static** self-contained HTML snapshot with no live tool execution. A
  live-managing browser dashboard would require a separate FastAPI/HTTP layer,
  which the user has ruled out ("use FastMCP, not FastAPI"). Therefore the
  control center is Claude-Desktop-hosted; `prefab serve`/`export` remain
  read-only previews only.
- **`FastMCPApp` provider.** It exists in 3.2.4 (`fastmcp.apps.FastMCPApp`) but
  is used **nowhere** in this codebase. The project is built entirely on
  standalone `@tool` decorators auto-discovered by `FileSystemProvider`.
  Introducing a `FastMCPApp` provider would be a parallel composition mechanism
  fighting that model. We deliberately reuse the standalone-`@tool` +
  `meta={"ui": True}` + `visibility=["app"]`-helper pattern already proven by
  `ui_render_studio`.

## 1. Architecture — reuse the `render_studio` pattern verbatim

Reference implementation: `app/tools/ui/render_studio.py` (the canonical
interactive round-trip). The control center mirrors it 1:1:

```text
ui_control_center(version_id?)          @tool(meta={"ui": True})  — model-visible entry
├─ Depends(get_uow); supports_ui(ctx) gate
├─ non-Prefab  → ControlCenterFallback (Pydantic, in _fallback.py)
└─ Prefab      → PrefabApp(view, state)
                 ├─ section 1: library overview (stats + charts)
                 ├─ section 2: current set/version (DataTable + energy line)
                 ├─ Row[ action Buttons ]  → each CallTool → on_success refresh
                 └─ Slot("panel")  ← pre-seeded via _panel_fragment(data).to_json()

control_center_panel(version_id, job_id?)   @tool(meta={"ui": True,
                                              **app_config_to_meta_dict(
                                                AppConfig(visibility=["app"]))})
└─ returns the Slot("panel") fragment (job status + last-action result),
   hidden from the model, called only from the UI on_success.
```

**Round-trip mechanics** (identical to `render_studio`): a button's
`on_click=[CallTool(<action>, arguments={...}, on_success=[...],
on_error=ShowToast("{{ $error }}", variant="error"))]`; a shared
`_refresh_panel = CallTool("control_center_panel", arguments={...},
on_success=SetState("panel", RESULT))` chained after each action so only the
Slot re-renders. `PrefabApp.state` seeds `panel` with
`_panel_fragment(data).to_json()` (state is naively pydantic-dumped — the
`.to_json()` pre-serialization is required, per the render_studio comment).

### File structure

**Create:**
- `app/tools/ui/control_center.py` — entry tool + panel helper + gatherer +
  fragment/section builders. (Phase 2 adds the wrapper action tools here or in
  sibling files under `app/tools/ui/actions/`.)
- `tests/tools/ui/test_control_center_*.py`.

**Modify:**
- `app/tools/ui/_fallback.py` — add `ControlCenterFallback`.
- `app/server/transforms.py` — add `"ui_control_center"` to
  `ALWAYS_VISIBLE_TOOLS` (do NOT add `control_center_panel` or the wrapper
  actions — they are `visibility=["app"]`).
- `docs/tool-catalog.md` — UI tools 7→8, model-visible count 24→25, note the
  hidden helpers.

## 2. Data — reuse existing gatherers, zero new business logic

`gather_control_center(uow, *, version_id) -> dict` composes three existing
read paths (no queries invented):

| Section | Source (existing) |
|---|---|
| Library overview: totals, coverage, BPM/mood/Camelot dists | same aggregate reads as `ui_library_dashboard` (`entity_aggregate` over `track` / `track_features`) |
| Current set/version: tracks, bpm/key/lufs/mood, energy arc, quality | `ui_set_view._gather` accessors — `uow.set_versions.get_items`, `uow.tracks.get_many`, `uow.track_features.get_scoring_features_batch` |
| Render status / beatgrid / timeline / diagnostics | `gather_render_studio` (imported from `render_studio.py`) |

`version_id` optional: when omitted, resolve the latest version (mirror
`ui_set_view`'s `get_latest`). A version selector in the panel re-invokes the
entry tool with a chosen id (client-side, no new tool).

## 3. Buttons → tools (the load-bearing truth)

`CallTool` invokes exactly ONE tool with static/`{{ state }}` arguments. That
constraint drives the phasing:

| Button | Backing tool | Args | Phase |
|---|---|---|---|
| Analyze + QA | `render_beatgrid` (exists) | `version_id` | 1 |
| Render | `render_mixdown` (exists) | `version_id` → returns `job_id` | 1 |
| Diagnose | `render_diagnose` (exists) | `version_id` | 1 |
| Build / Reorder | **new** `act_build` wrapper | `version_id` | 2 |
| Analyze → L5 | **new** `act_l5_set` wrapper | `version_id` | 2 |
| Deliver bundle | **new** `act_deliver` wrapper | `version_id` | 2 |
| Sync → YM | `playlist_sync` (exists) | `playlist_id`, `direction` | 2 |

**Phase 1 (MVP)** wires only the three `render_*` tools — single `version_id`
arg, already `task=True`, low risk. Entry shell + both data sections +
`Slot("panel")` + fallback + registration + tests + `make check`.

**Phase 2** adds the app-only wrapper tools (`@tool(visibility=["app"])`),
each a thin orchestration over existing pieces:
- `act_build(version_id)` — read the version's track pool → `sequence_optimize`
  → persist a new `set_version` (the `set_version_build` handler). Returns the
  new version id + quality_score.
- `act_l5_set(version_id)` — for every set track: ensure an `audio_file` row
  (download if missing, honoring the L5-finalization batch rules in
  `.claude/rules/audio.md`) → `entity_update(track_features, level=5)`. This is
  also the correct home for fixing the stale-`audio_file`-path failure mode
  currently breaking `render_beatgrid` (dup rows pointing at deleted `/tmp`
  files) — the wrapper re-resolves the real library path before L5.
- `act_deliver(version_id)` — invoke the delivery path
  (`deliver_set_workflow` steps) to emit the bundle; if no single callable
  deliver tool exists, `act_deliver` composes the existing delivery
  handler(s), else the Deliver button is dropped and delivery stays a prompt
  step. Decide during Phase 2 by checking the actual delivery surface.
- Sync → YM button → `playlist_sync` directly (needs the set's `playlist_id`
  threaded from section-2 data).

Long/heavy actions (`act_l5_set`, `act_build`) run under `task=True` like the
render tools; the panel polls `RENDER_JOBS`-style status through the same
`control_center_panel` round-trip, never the host task protocol (degradation
contract, same as render studio).

## 4. Fallback

`ControlCenterFallback(BaseModel)` in `_fallback.py` — mirrors the gatherer
dict: `version_id`, library stats block, `n_tracks`, `quality_score`, `tracks`,
`energy_arc`, plus the render sub-block (`beatgrid`, `job`, `timeline`,
`diagnostics`). Non-Prefab clients (Claude Code stdio, CLI probes) still get a
structured JSON payload; the model can read state even where it can't click.

## 5. Testing

Follow the existing `ui_*` test convention (`tests/tools/ui/`, mirrored dir):
- construction returns without error (Prefab branch builds a `PrefabApp`);
- `supports_ui(ctx)=False` → `ControlCenterFallback` with correct fields;
- registration: `ui_control_center` in `ALWAYS_VISIBLE_TOOLS` and discoverable
  via `build_mcp_app_for_tests`; helpers present but not in the always-visible
  set;
- Phase 2: each wrapper action tested in isolation with monkeypatched DI
  (mock uow / registries), asserting it calls the right underlying
  tool/handler with derived args.
- `make check` green (lint + mypy + import-linter + pytest). UI tests need
  `[audio]`+`[apps]` extras; skip cleanly otherwise.

**Live behavior of the buttons cannot be verified headless** — that needs a
Prefab-aware host (Claude Desktop). Tests cover construction, the fallback
branch, registration, and the wrapper action orchestration; button clicks are
a manual Desktop step (documented in the plan's finishing task).

## 6. Self-review notes

- **Consistency:** every button maps to a named tool in §3; gatherer dict keys
  match `ControlCenterFallback` fields and the section builders; the round-trip
  helper name (`control_center_panel`) is used consistently.
- **No new mechanism:** standalone `@tool` + FileSystemProvider + `Depends
  (get_uow)` + `visibility=["app"]` helpers + `ALWAYS_VISIBLE_TOOLS` — all
  already in the codebase.
- **Phasing is real, not cosmetic:** Phase 1 ships a working panel using only
  existing single-arg tools; Phase 2's wrappers carry the genuine orchestration
  risk (download/L5/YM/deliver) and get their own plan + tests.
```

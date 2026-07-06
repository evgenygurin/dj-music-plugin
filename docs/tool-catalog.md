# MCP Tool Catalog

Quick reference — **25 model-visible tools** (13 core dispatchers + 3 render + 8 UI/Prefab + `tool_invoke`) + **32 resources** + **31 prompts** + **6 handlers** + **11 registered entities**. One extra tool — `render_studio_panel` — is registered but app-visibility only (`visibility=["app"]`), hidden from the model / BM25 so the `ui_render_studio` UI can `CallTool` it.

The 88-tool catalog of v0.8 was collapsed via polymorphism: generic CRUD
(`entity_*`) dispatches via `EntityRegistry`, generic provider access
(`provider_*`) via `ProviderRegistry`, side-effects live in handlers.
Everything else is exposed as **resources** (read-only views) or
**prompts** (workflow recipes) — resources/prompts can be surfaced as
tools via `app/server/transforms.py` for tool-only clients.

## Tools (24)

### Entity CRUD (6, namespace `crud:read` / `crud:write` / `crud:destructive`)

| Tool | Params | RO | Hidden |
|------|--------|----|--------|
| `entity_list` | entity, filters?, search?, fields?, sort?, limit=50, cursor?, with_total=false | yes | no |
| `entity_get` | entity, id, fields?, include_relations? | yes | no |
| `entity_aggregate` | entity, operation(count\|distinct\|histogram\|min_max\|sum\|avg), field?, group_by?, filters? | yes | no |
| `entity_create` | entity, data | no | no |
| `entity_update` | entity, id, data | no | `crud:destructive` |
| `entity_delete` | entity, id | no (destructive) | `crud:destructive` |

Supported entities (via `EntityRegistry`, 11 total): track, track_features,
audio_file, playlist, set, set_version, transition, transition_history,
track_affinity, track_feedback, scoring_profile.

`key` and `provider_metadata` have ORM models + repositories but are
**not** registered as `EntityRegistry` entities — `key` is exposed via
`reference://camelot`, provider responses via the `provider_*` tools.

`entity_get.include_relations` eager-loads declared relations into the
response `data` under the relation name (attached after `fields`
projection, so `fields="summary"` doesn't strip them). Supported:
track × `artists|features`, playlist × `items`, set × `versions`,
set_version × `items`, audio_file × `beatgrids`. Unknown names raise a
typed `ValidationError`. To-one relations (`track.features`) return a
view-dict or `null`; to-many return a list of view-dicts. Loaders live
in `app/registry/defaults.py` (`EntityConfig.relation_loaders`).

Handlers wire side-effects on create/update/delete:

| Entity | create handler | update handler |
|---|---|---|
| track | `track_import` (fetch from provider, persist) | — |
| track_features | `track_features_analyze` (run tiered pipeline) | `track_features_reanalyze` (higher level) |
| audio_file | `audio_file_download` (fetch MP3 from provider) | — |
| set_version | `set_version_build` (GA/greedy + persist transitions) | — |
| transition | `transition_persist` | — |

### Provider access (3, namespace `provider:read` / `provider:write`)

| Tool | Params | RO | Hidden |
|------|--------|----|--------|
| `provider_read` | provider, entity, id?, params? | yes | no |
| `provider_search` | provider, query, type(tracks\|albums\|artists\|playlists\|all), limit=20 | yes | no |
| `provider_write` | provider, entity, operation, params | no | `provider:write` |

`provider_read.entity` values are provider-specific:
- Yandex: `track`, `album`, `playlist`, `artist_tracks`, `track_similar`,
  `track_batch`, `likes`, `dislikes`, `playlist_list`.
- Beatport: `track`, `track_match`, `account`.
- Suno (opt-in provider) — **mode-gated surface** (`app/providers/suno/`).
  Project default is Suno web no-browser **session** auth via
  `DJ_SUNO_COOKIE_HEADER` or `DJ_SUNO_BEARER_TOKEN` /
  `DJ_SUNO_CLIENT_TOKEN` + `DJ_SUNO_DEVICE_ID`, or
  `DJ_SUNO_STORAGE_STATE_PATH` (`https://studio-api-prod.suno.com` +
  `https://auth.suno.com`, Clerk Bearer, payload mode `suno_web`, pollable clip
  ids, model keys such as `chirp-auk-turbo`). In session mode `provider_read`
  entities are `generation`, `account`. `entity="account"` returns live balance
  (`credits_left`, `subscription_type`, `usable_models`, `payload_mode`) merged
  with capabilities.
  - **SunoAPI mode** (`https://docs.sunoapi.org`) is opt-in when an API key
    exists: `DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_API_KEY`, default base
    `https://api.sunoapi.org`, payload mode `sunoapi`, model enum
    `V4|V4_5|V4_5PLUS|V4_5ALL|V5|V5_5`. It unlocks the **full sunoapi.org REST
    surface** (declared in `app/providers/suno/endpoints.py`). `provider_read`
    read entities: `generation` (`/api/v1/generate/record-info?taskId=`),
    `lyrics`, `wav`, `vocal_removal`, `midi`, `video`, `cover`, `voice`
    (`params={"kind":"validate"|"record"}`), `account`
    (`/api/v1/generate/credit`). Calling a sunoapi-only op in session mode
    raises a typed error. `operation="cancel"` is legacy/generic only unless a
    custom `DJ_SUNO_CANCEL_PATH` is configured.

`provider_write.entity/operation` matrix:
- `playlist` × `add_tracks | remove_tracks | create | rename | delete`
- `likes` × `add | remove`
- `generation` × `create | cancel | download` (both Suno modes)
- **Suno session/web mode** (`payload_mode=suno_web`, browser Suno; declared in
  `app/providers/suno/endpoints_web.py`, reverse-engineered from the live
  suno.com bundle + validated live): `generation` × `extend | concat`;
  `stem` × `create | sample_pack`; `wav` × `create`; `edit` ×
  `crop | fade | reverse`; `remaster` × `create`; `persona` × `create`;
  `lyrics` × `create`; `playlist` × `create | add_tracks | remove_tracks`.
  Reads add `clip` (`params.kind` ∈ info/stems/wav/downbeats/sections/waveform/
  aligned_lyrics), `lyrics`, `persona`, `playlist`.
- **SunoAPI mode only** (`DJ_SUNO_AUTH_MODE=api_key`):
  - `generation` × `extend | upload_cover | upload_extend | add_instrumental |
    add_vocals | mashup | replace_section | sounds`
  - `lyrics` × `create | timestamped`
  - `wav` × `create`; `vocal_removal` × `create`; `midi` × `create`;
    `video` × `create`; `cover` × `create`; `persona` × `create`
  - `style` × `boost`
  - `voice` × `validate | generate | regenerate | check`
  - `file` × `upload_base64 | upload_url | upload_stream` (posts to
    `DJ_SUNO_UPLOAD_BASE_URL`, default `https://sunoapiorg.redpandaai.co`)

### Compute (2, namespace `compute`)

| Tool | Params | RO |
|------|--------|-----|
| `transition_score_pool` | track_ids (0..500), intent?, top_k?, components=true | yes |
| `sequence_optimize` | track_ids (2..500), algorithm(ga\|greedy)=ga, template?, pinned?, excluded? | yes |

### Sync (1, namespace `sync`)

| Tool | Params | RO | Hidden |
|------|--------|-----|--------|
| `playlist_sync` | playlist_id, direction(pull\|push\|diff)=diff, source="yandex", dry_run=false | no | `sync` |

### Render (3, namespace `render`)

Continuous-mix render pipeline over a persisted `set_version`. Visible by
default (like `sync` / `compute`). All three are heavy DSP passes
(librosa / ffmpeg+rubberband) declared `task=True` — the host runs them as
background tasks (`FastMCP(tasks=True)`, `fastmcp[tasks]` extra). Whitelisted
in `ALWAYS_VISIBLE_TOOLS` so `BM25SearchTransform` never hides them.

| Tool | Params | RO |
|------|--------|-----|
| `render_beatgrid` | version_id, refresh=false | no (idempotent) |
| `render_mixdown` | version_id, out_name?, transition_bars?, body_bars?, refresh_grid=false | no |
| `render_diagnose` | version_id, mix_path? | yes |

- `render_beatgrid` — kick-phase detect + sub-beat phase refine + LUFS
  level-match; writes `beatgrid.json`.
- `render_mixdown` — beatmatch (rubberband→target BPM) + 32-bar EQ bass-swap
  transitions + limiter → one continuous `MIX.mp3`. Auto-runs the beatgrid if
  missing.
- `render_diagnose` — scan + per-4s librosa defect sweep (level jumps,
  dropouts, bass-thin) of a rendered mix; writes `diagnostics.json`.

### Admin (2, namespace `admin`)

| Tool | Params | RO |
|------|--------|-----|
| `unlock_namespace` | namespace(crud:destructive\|provider:write\|sync\|all), action(unlock\|lock\|status)=status | no |
| `tool_invoke` | name, arguments? | no (proxy) |

`tool_invoke` is an escape hatch for clients (e.g. Claude Code) that cache
the tool list on startup: even when `unlock_namespace` flips visibility
mid-session, such clients do not see newly visible tools until a full
re-sync. `tool_invoke` stays always visible and proxies calls to any
backend tool by name. Self-dispatch is blocked.

### UI / Prefab Apps (8, namespace `ui:read`)

Visual renderers marked with `meta={"ui": True}` (standalone-decorator equivalent of `@mcp.tool(app=True)`). Prefab-aware clients (Claude Desktop v3.1+) render the returned `prefab_ui.components.Column` tree inline. Non-Prefab clients fall back to a Pydantic JSON payload via `ctx.client_supports_extension("io.modelcontextprotocol/ui")`. All read-only, always visible.

| Tool | Params | Rendered UI | Fallback shape |
|------|--------|-------------|----------------|
| `ui_set_view` | set_id, version_id? | Heading + LineChart (energy arc) + DataTable (tracks) + Row[Badge] transitions + Card cheatsheet | `SetViewFallback` |
| `ui_transition_score` | from_track_id, to_track_id, intent? | Heading + Row[Metric×3] + RadarChart (6 components) + Card[hard constraints] + Card[style recipe] | `TransitionScoreFallback` |
| `ui_library_audit` | playlist_id? | Heading + Row[Metric×4] + Card[PieChart subgenres] + DataTable[pass/fail] | `LibraryAuditFallback` |
| `ui_score_pool_matrix` | track_ids (2..50) | Heading + Row[Metric×2] + DataTable (N×N heatmap) + Legend Card | `ScorePoolMatrixFallback` |
| `ui_library_dashboard` | — | Heading + Row[Metric×3] + Card[BarChart BPM] + Row[Card[PieChart moods], Card[BarChart Camelot]] | `DashboardFallback` |
| `ui_camelot_wheel` | playlist_id? | Heading + Row[Metric×2] + Card[RadialChart wheel] + DataTable (slots) | `CamelotWheelFallback` |
| `ui_render_studio` | version_id | Heading + Row[Button] Analyze/QA·Render·Diagnose·Refresh (each `CallTool`s a real `render_*` tool) + Slot[status, beatgrid, timeline, diagnostics] | `RenderStudioFallback` |

| `ui_control_center` | version_id | Heading + Row[Metric×N] library/set/version overview + render pipeline buttons (Analyze+QA·Render·Diagnose) | `ControlCenterFallback` |

`ui_render_studio` is the interactive render-pipeline control panel: its buttons `CallTool` into `render_beatgrid` / `render_mixdown` / `render_diagnose` and refresh through the hidden `render_studio_panel` helper (`visibility=["app"]` — registered but not model-visible; re-reads `RENDER_JOBS` + workspace files so status flows through our own `CallTool` round-trip, not the host task protocol). See `docs/render-pipeline.md`.

`ui_control_center` is the combined library + set/version + render-pipeline entry panel: it composes the library overview, the current set/version summary, and the render controls in one view. Its render buttons reuse the same hidden `render_studio_panel` helper as `ui_render_studio` — no new app-only helper is added.

Enable with `uv sync --all-extras` (pulls `fastmcp[apps]` → `prefab_ui>=0.19`).

## Resources (32)

All read-only, MIME `application/json`, auto-discovered from `app/resources/`.

### Local — entity views (16)

| URI | File | Purpose |
|---|---|---|
| `local://tracks/{id}` | track.py | Single track view |
| `local://tracks/{id}/features` | track.py | Audio features for a track |
| `local://tracks/{id}/audit` | track.py | Techno audit for a track |
| `local://tracks/{id}/suggest_next{?limit,energy_direction}` | track.py | Candidate next tracks from adaptive arc |
| `local://tracks/{id}/suggest_replacement/{set_id}/{position}` | track.py | Replacement candidates for a slot |
| `local://playlists/{id}{?include_tracks}` | playlist.py | Playlist detail |
| `local://playlists/{id}/audit` | playlist.py | Techno audit report for a playlist |
| `local://sets/{id}/{view}` | set.py | view=summary\|tracks\|transitions\|full |
| `local://sets/{id}/cheatsheet{?version}` | set.py | DJ cheat sheet text |
| `local://sets/{id}/narrative` | set.py | Narrative analysis (arc, moods) |
| `local://sets/{id}/review{?version}` | set.py | Set quality review (default: latest version) |
| `local://sets/{id}/versions/compare/{a}/{b}` | set.py | Diff two set versions |
| `local://transition/{from_id}/{to_id}/score` | transition.py | Pairwise transition score |
| `local://transition/{from_id}/{to_id}/explain` | transition.py | Explain scored components |
| `local://transition_history/best_pairs{?track_id,limit}` | transition_history.py | Best historical pairs |
| `local://transition_history/history{?limit,track_id}` | transition_history.py | Transition log |

### Schema — introspection (4)

| URI | Purpose |
|---|---|
| `schema://entities` | List all entity types + their schemas |
| `schema://entities/{entity}` | Single entity: filters, fields, presets |
| `schema://providers` | List providers + capabilities |
| `schema://providers/{name}` | Single provider: supported entities/operations |

### Session — per-client state (3)

| URI | Purpose |
|---|---|
| `session://set-draft` | Current set-in-progress (in-memory) |
| `session://tool-history` | Last N tool calls in session |
| `session://energy-trend{?limit}` | Adaptive arc — energy direction suggestion |

### Reference — static knowledge (5)

| URI | Purpose |
|---|---|
| `reference://camelot` | Camelot wheel topology |
| `reference://subgenres` | 15 techno subgenres + scoring weights |
| `reference://templates` | 8 set templates (warm_up_30, classic_60, …) |
| `reference://audit_rules` | Techno audit thresholds |
| `reference://render/defaults` | RenderSettings constants (target BPM, bars, XSPLIT, limiter) |

### Render — continuous-mix pipeline (4)

Cheap reads only (workspace files + in-process `RENDER_JOBS` + pure timeline
math); the heavy defect sweep is the `render_diagnose` tool, not a resource.

| URI | Purpose |
|---|---|
| `local://render/jobs/{job_id}/status` | Live render-job progress from the in-process registry |
| `local://render/jobs/{job_id}/diagnostics` | Saved `diagnostics.json` for a job's version workspace |
| `local://render/{version_id}/beatgrid` | Saved `beatgrid.json` (per-track trim / gain / phase) |
| `local://render/{version_id}/timeline` | Segment + transition-window timeline (pure math) |

## Prompts (31, namespace `workflow`)

Design rationale + techno-domain research:
[docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md](research/2026-06-22-techno-set-construction-and-mcp-prompts.md)
+ deep dive / persona & axis expansion (v2):
[docs/research/2026-06-22-techno-deep-dive-and-prompt-expansion.md](research/2026-06-22-techno-deep-dive-and-prompt-expansion.md).
Agent-facing operating rules:
[.claude/rules/dj-set-building.md](../.claude/rules/dj-set-building.md)
+ updated synthesis
[docs/research/2026-07-05-techno-fastmcp-claude-rules.md](research/2026-07-05-techno-fastmcp-claude-rules.md).
Authoring rules + content-correctness contract:
[.claude/rules/prompts.md](../.claude/rules/prompts.md). Every
entity / provider / field-preset **and** every `filters={...}` key,
`data={...}` key, and `provider_write` operation in a prompt body is
validated against the live runtime schemas/adapter by
`tests/prompts/test_prompt_content_correctness.py` (a name that doesn't
resolve is a runtime hard error, not a no-op).

**Core (6)**

| Prompt | Purpose |
|---|---|
| `dj_expert_session` | Prime the LLM with domain knowledge (Camelot, subgenres, templates, audit rules) |
| `build_set_workflow` | End-to-end recipe: playlist → optimize → score → persist |
| `deliver_set_workflow` | Export a set (+ optional YM sync) with conflict gate |
| `expand_playlist_workflow` | Provider discovery + import + analyze to grow a playlist |
| `full_pipeline` | Chain expand → build → deliver |
| `quick_mix_check` | Single pairwise mix compatibility (a→b) |

**Library & analysis (3)**

| Prompt | Purpose |
|---|---|
| `library_health_workflow` | Coverage + BPM/key/mood distribution + audit fails (`playlist_id?`) |
| `analyze_library_workflow` | Batch-analyze unanalyzed tracks / upgrade tier (`playlist_id?, level=3, batch_size=20`) |
| `track_prep_workflow` | Single-track mixing prep: analyze→L3, audit, numbers, neighbours (`track_id`) |

**Set design (10)**

| Prompt | Purpose |
|---|---|
| `harmonic_journey_workflow` | Camelot-wheel key journey (`playlist_id, length=12, start_camelot?`) |
| `subgenre_journey_workflow` | Energy-axis subgenre journey (`playlist_id, arc=build`) |
| `tempo_journey_workflow` | BPM-axis ramp set (`playlist_id, start_bpm=122, end_bpm=132, length=12`) |
| `scenario_set_workflow` | Scenario preset: warmup/peak/closing/roller/wave/progressive (`playlist_id, scenario=peak`) |
| `dj_persona_workflow` | Build in a DJ school's style: klock/dettmann/lens/dewitte/mills/hawtin/kraviz (`playlist_id, persona=klock, length=12`) |
| `style_lock_set_workflow` | Mono-genre set locked to one subgenre band (`playlist_id, style=hypnotic, length=12`) |
| `mix_cluster_workflow` | Find mutually-mixable clusters/chains, seed a set bottom-up (`playlist_id, limit=30`) |
| `lineup_handoff_workflow` | Build a lineup slot whose tail hands off at a target BPM (`playlist_id, role=warmup, handoff_bpm=128`) |
| `b2b_planning_workflow` | Back-to-back across two crates (`playlist_a, playlist_b, template=classic_60`) |
| `extend_set_workflow` | Lengthen a set, keep the arc (`set_id, add_tracks=5, where=end`) |

**Set repair (4)**

| Prompt | Purpose |
|---|---|
| `set_review_workflow` | Critique an existing set + propose fixes (`set_id`) |
| `rescue_set_workflow` | Heavy repair of a hard-reject-riddled set: reorder → cull → bridge (`set_id`) |
| `fix_transition_workflow` | Diagnose/repair one weak/hard transition: technique → bridge → replace (`from_track_id, to_track_id`) |
| `replace_track_workflow` | Swap a weak slot for a better candidate (`set_id, position`) |

**Delivery & performance (4)**

| Prompt | Purpose |
|---|---|
| `set_cheatsheet_workflow` | Assemble a performance-ready DJ cue sheet (BPM/key/energy/technique) (`set_id, version_id?`) |
| `set_duration_fit_workflow` | Trim/extend a set to fit an exact time slot, keep the arc (`set_id, target_minutes=60`) |
| `live_next_track_workflow` | Live mid-set: pick the next track from the current one + room energy (`last_track_id, energy_direction=flat`) |
| `render_set_workflow` | Render a set version into one continuous beatmatched MP3 (beatgrid → mixdown → diagnose → deliver) (`version_id`) |

**Discovery & ops (3)**

| Prompt | Purpose |
|---|---|
| `crate_digging_workflow` | Discovery-first digging + curation (`seed, target_count=20, playlist_id?`) |
| `taste_profile_workflow` | Curate feedback + affinity (like/ban/rate) to steer scoring |
| `playlist_sync_workflow` | Pull/push/diff a playlist against YM with a conflict gate (`playlist_id, direction=diff`) |

**Library maintenance (1)**

| Prompt | Purpose |
|---|---|
| `library_cleanup_workflow` | Actionable hygiene: unanalyzed/low-quality/outlier tracks + per-problem fix (`playlist_id?`) |

## Visibility

**Current state (see `app/server/visibility.py`):** `DISABLED_NAMESPACE_TAGS`
is an empty frozenset — **no namespace is hidden at startup**. Rationale: Claude
Code does not always honour `notifications/tools/list_changed` inside an active
session, so `unlock_namespace` would flip server-side visibility without the
client seeing the newly enabled tools. Keeping all namespaces visible avoids
the UX footgun; `unlock_namespace` still exists for audit-log workflows and
for clients that do honour the notification.

`KNOWN_NAMESPACES` (advertised as unlockable by `unlock_namespace`):
`crud:destructive`, `provider:write`, `sync`, `ui:read`.

| Namespace | Tools | Default |
|---|---|---|
| `crud:read` | entity_list, entity_get, entity_aggregate | visible |
| `crud:write` | entity_create | visible |
| `crud:destructive` | entity_update, entity_delete | visible |
| `provider:read` | provider_read, provider_search | visible |
| `provider:write` | provider_write | visible |
| `compute` | transition_score_pool, sequence_optimize | visible |
| `sync` | playlist_sync | visible |
| `render` | render_beatgrid, render_mixdown, render_diagnose | visible |
| `admin` | unlock_namespace, tool_invoke | visible |
| `ui:read` | ui_set_view, ui_transition_score, ui_library_audit, ui_score_pool_matrix, ui_library_dashboard, ui_camelot_wheel, ui_render_studio, ui_control_center | visible |
| `workflow` | all prompts | visible |

`ALWAYS_VISIBLE_TOOLS` in `app/server/transforms.py` whitelists every tool
listed above (including `tool_invoke`, the 8 UI tools, and the 3 render tools)
so `BM25SearchTransform` never hides them behind a search query. The
`render_studio_panel` UI helper is `visibility=["app"]` — deliberately NOT
whitelisted (hidden from the model / BM25; the UI reaches it via `CallTool`).

## Tool count history

| Version | Tools | Resources | Notes |
|---|---|---|---|
| v0.8.0 | 88 | ~9 | 61 visible + 27 hidden; narrow per-operation tools |
| v1.0.0 | 13 | 27 | Generic dispatchers + polymorphism; resources/prompts carry the rest |
| v1.0.1 | 13 | 27 | +`provider_write(... set_description)` operation; auto-reload hook; entrypoint pinned to root `server.py` |
| v1.0.3 | 19 | 27 | +6 Prefab UI tools (`ui_*`, namespace `ui:read`) — additive; core dispatchers unchanged |
| v1.0.4 | 20 | 27 | +`tool_invoke` proxy (admin namespace) for clients that cache the tool list across `unlock_namespace` transitions |
| v1.3.7 | 20 | 27 | Manual MCP hardening (no surface change). FK gate auto-derived from `cls.__table__.foreign_keys` (`app/tools/entity/_fk_gate.py`); `DomainErrorMiddleware` wraps resource + prompt envelopes too; Pydantic `ValidationError` → typed `app.shared.errors.ValidationError`; `AggregateResult.value` union has `bool` BEFORE `int` (`distinct(variable_tempo)` → `[false, true]`); validation gates added on `entity_get.include_relations`, `suggest_next.energy_direction`, `transition.{scoring_profile,fx_type,persist}`, `sequence_optimize.{pinned,excluded}`, `ui_score_pool_matrix` duplicate ids, `ui_transition_score` `from==to`, `entity_update set` BPM partial-update invariant; `unlock_namespace` accepts `ui:read`; `provider_read.id` accepts `int \| str`; `YandexAdapter.read("track_batch")` accepts legacy `ids` key; `app/audio/core/loader.py` wraps `wave.Error` → typed `RuntimeError`; SQLite `PRAGMA foreign_keys=ON` via `connect` event listener. |
| (prompts) | 20 | 27 | Prompt catalog grew 6 → **19** (additive, no tool/resource surface change): +`library_health_workflow`, `analyze_library_workflow`, `harmonic_journey_workflow`, `subgenre_journey_workflow`, `scenario_set_workflow`, `b2b_planning_workflow`, `extend_set_workflow`, `set_review_workflow`, `fix_transition_workflow`, `replace_track_workflow`, `crate_digging_workflow`, `taste_profile_workflow`, `playlist_sync_workflow`. Research-backed (`docs/research/2026-06-22-…`); content pinned by `test_prompt_content_correctness.py`. |
| (prompts v2) | 20 | 27 | Prompt catalog grew 19 → **26** (additive): +`tempo_journey_workflow` (BPM axis), +`dj_persona_workflow` (Klock/Dettmann/Lens/de Witte/Mills/Hawtin/Kraviz schools), +`style_lock_set_workflow` (mono-genre), +`mix_cluster_workflow` (bottom-up cluster discovery), +`rescue_set_workflow` (heavy hard-reject repair), +`set_cheatsheet_workflow` (performance cue sheet), +`library_cleanup_workflow` (actionable hygiene). Deep-dive research (`docs/research/2026-06-22-techno-deep-dive-and-prompt-expansion.md`); content pinned by `test_prompt_content_correctness.py`. |
| (prompts v3) | 20 | 27 | Prompt catalog grew 26 → **30** (additive, live/performance batch): +`live_next_track_workflow` (mid-set live pick via `session://*` + `suggest_next`), +`set_duration_fit_workflow` (fit a set to an exact time slot), +`track_prep_workflow` (single-track end-to-end readiness), +`lineup_handoff_workflow` (slot whose tail hands off at a target BPM). Content pinned by `test_prompt_content_correctness.py`. |
| render | **23** | **32** | +3 render tools (`render_beatgrid`/`render_mixdown`/`render_diagnose`, namespace `render`, `task=True`, visible by default) + 5 render resources (`reference://render/defaults`, `local://render/jobs/{job_id}/status`, `.../diagnostics`, `local://render/{version_id}/beatgrid`, `.../timeline`) + `render_set_workflow` prompt (30 → **31**) + `emit_continuous_mix` delivery toggle. `FastMCP(tasks=True)` + `fastmcp[tasks]` extra. See `docs/render-pipeline.md`. |
| render studio | **24** | **32** | +`ui_render_studio` interactive Prefab studio (namespace `ui:read`, always-visible; UI tools 6 → **7**) — buttons `CallTool` the 3 `render_*` tools, live status/beatgrid/timeline/diagnostics slots, `RenderStudioFallback` for non-Prefab clients. Plus a hidden `render_studio_panel` helper (`visibility=["app"]` — registered but not model-visible; the UI refreshes through it). See `docs/render-pipeline.md`. |
| control center | **25** | **32** | +`ui_control_center` combined library + set/version + render-pipeline entry panel (namespace `ui:read`, always-visible; UI tools 7 → **8**) — reuses the existing hidden `render_studio_panel` helper for its render buttons (no new helper), `ControlCenterFallback` for non-Prefab clients. |

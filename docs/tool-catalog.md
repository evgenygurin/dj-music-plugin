# MCP Tool Catalog

Quick reference — **20 tools total** (13 core dispatchers + 6 UI/Prefab + `tool_invoke`) + **27 resources** + **19 prompts** + **6 handlers** + **11 registered entities**.

The 88-tool catalog of v0.8 was collapsed via polymorphism: generic CRUD
(`entity_*`) dispatches via `EntityRegistry`, generic provider access
(`provider_*`) via `ProviderRegistry`, side-effects live in handlers.
Everything else is exposed as **resources** (read-only views) or
**prompts** (workflow recipes) — resources/prompts can be surfaced as
tools via `app/server/transforms.py` for tool-only clients.

## Tools (20)

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

`provider_read.entity` values: `track`, `album`, `playlist`, `artist_tracks`,
`track_similar`, `track_batch`, `likes`, `dislikes`, `playlist_list`.

`provider_write.entity/operation` matrix:
- `playlist` × `add_tracks | remove_tracks | create | rename | delete`
- `likes` × `add | remove`

### Compute (2, namespace `compute`)

| Tool | Params | RO |
|------|--------|-----|
| `transition_score_pool` | track_ids (0..500), intent? | yes |
| `sequence_optimize` | track_ids (2..500), algorithm(ga\|greedy)=ga, template?, pinned?, excluded? | yes |

### Sync (1, namespace `sync`)

| Tool | Params | RO | Hidden |
|------|--------|-----|--------|
| `playlist_sync` | playlist_id, direction(pull\|push\|diff)=diff, source="yandex", dry_run=false | no | `sync` |

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

### UI / Prefab Apps (6, namespace `ui:read`)

Visual renderers marked with `meta={"ui": True}` (standalone-decorator equivalent of `@mcp.tool(app=True)`). Prefab-aware clients (Claude Desktop v3.1+) render the returned `prefab_ui.components.Column` tree inline. Non-Prefab clients fall back to a Pydantic JSON payload via `ctx.client_supports_extension("io.modelcontextprotocol/ui")`. All read-only, always visible.

| Tool | Params | Rendered UI | Fallback shape |
|------|--------|-------------|----------------|
| `ui_set_view` | set_id, version_id? | Heading + LineChart (energy arc) + DataTable (tracks) + Row[Badge] transitions + Card cheatsheet | `SetViewFallback` |
| `ui_transition_score` | from_track_id, to_track_id, intent? | Heading + Row[Metric×3] + RadarChart (6 components) + Card[hard constraints] + Card[style recipe] | `TransitionScoreFallback` |
| `ui_library_audit` | playlist_id? | Heading + Row[Metric×4] + Card[PieChart subgenres] + DataTable[pass/fail] | `LibraryAuditFallback` |
| `ui_score_pool_matrix` | track_ids (2..50) | Heading + Row[Metric×2] + DataTable (N×N heatmap) + Legend Card | `ScorePoolMatrixFallback` |
| `ui_library_dashboard` | — | Heading + Row[Metric×3] + Card[BarChart BPM] + Row[Card[PieChart moods], Card[BarChart Camelot]] | `DashboardFallback` |
| `ui_camelot_wheel` | playlist_id? | Heading + Row[Metric×2] + Card[RadialChart wheel] + DataTable (slots) | `CamelotWheelFallback` |

Enable with `uv sync --all-extras` (pulls `fastmcp[apps]` → `prefab_ui>=0.19`).

## Resources (27)

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
| `local://sets/{id}/review` | set.py | Set quality review |
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

### Reference — static knowledge (4)

| URI | Purpose |
|---|---|
| `reference://camelot` | Camelot wheel topology |
| `reference://subgenres` | 15 techno subgenres + scoring weights |
| `reference://templates` | 8 set templates (warm_up_30, classic_60, …) |
| `reference://audit_rules` | Techno audit thresholds |

## Prompts (19, namespace `workflow`)

Design rationale + techno-domain research:
[docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md](research/2026-06-22-techno-set-construction-and-mcp-prompts.md).
Every entity / provider / field-preset name in a prompt body is pinned by
`tests/prompts/test_prompt_content_correctness.py`.

**Core (6)**

| Prompt | Purpose |
|---|---|
| `dj_expert_session` | Prime the LLM with domain knowledge (Camelot, subgenres, templates, audit rules) |
| `build_set_workflow` | End-to-end recipe: playlist → optimize → score → persist |
| `deliver_set_workflow` | Export a set (+ optional YM sync) with conflict gate |
| `expand_playlist_workflow` | Provider discovery + import + analyze to grow a playlist |
| `full_pipeline` | Chain expand → build → deliver |
| `quick_mix_check` | Single pairwise mix compatibility (a→b) |

**Library & analysis (2)**

| Prompt | Purpose |
|---|---|
| `library_health_workflow` | Coverage + BPM/key/mood distribution + audit fails (`playlist_id?`) |
| `analyze_library_workflow` | Batch-analyze unanalyzed tracks / upgrade tier (`playlist_id?, level=3, batch_size=20`) |

**Set design (5)**

| Prompt | Purpose |
|---|---|
| `harmonic_journey_workflow` | Camelot-wheel key journey (`playlist_id, length=12, start_camelot?`) |
| `subgenre_journey_workflow` | Energy-axis subgenre journey (`playlist_id, arc=build`) |
| `scenario_set_workflow` | Scenario preset: warmup/peak/closing/roller/wave/progressive (`playlist_id, scenario=peak`) |
| `b2b_planning_workflow` | Back-to-back across two crates (`playlist_a, playlist_b, template=classic_60`) |
| `extend_set_workflow` | Lengthen a set, keep the arc (`set_id, add_tracks=5, where=end`) |

**Set repair (3)**

| Prompt | Purpose |
|---|---|
| `set_review_workflow` | Critique an existing set + propose fixes (`set_id`) |
| `fix_transition_workflow` | Diagnose/repair one weak/hard transition: technique → bridge → replace (`from_track_id, to_track_id`) |
| `replace_track_workflow` | Swap a weak slot for a better candidate (`set_id, position`) |

**Discovery & ops (3)**

| Prompt | Purpose |
|---|---|
| `crate_digging_workflow` | Discovery-first digging + curation (`seed, target_count=20, playlist_id?`) |
| `taste_profile_workflow` | Curate feedback + affinity (like/ban/rate) to steer scoring |
| `playlist_sync_workflow` | Pull/push/diff a playlist against YM with a conflict gate (`playlist_id, direction=diff`) |

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
| `admin` | unlock_namespace, tool_invoke | visible |
| `ui:read` | ui_set_view, ui_transition_score, ui_library_audit, ui_score_pool_matrix, ui_library_dashboard, ui_camelot_wheel | visible |
| `workflow` | all prompts | visible |

`ALWAYS_VISIBLE_TOOLS` in `app/server/transforms.py` whitelists every tool
listed above (including `tool_invoke` and the 6 UI tools) so `BM25SearchTransform`
never hides them behind a search query.

## Tool count history

| Version | Tools | Resources | Notes |
|---|---|---|---|
| v0.8.0 | 88 | ~9 | 61 visible + 27 hidden; narrow per-operation tools |
| v1.0.0 | 13 | 27 | Generic dispatchers + polymorphism; resources/prompts carry the rest |
| v1.0.1 | 13 | 27 | +`provider_write(... set_description)` operation; auto-reload hook; entrypoint pinned to root `server.py` |
| v1.0.3 | 19 | 27 | +6 Prefab UI tools (`ui_*`, namespace `ui:read`) — additive; core dispatchers unchanged |
| v1.0.4 | 20 | 27 | +`tool_invoke` proxy (admin namespace) for clients that cache the tool list across `unlock_namespace` transitions |
| v1.3.7 | 20 | 27 | Manual MCP hardening (no surface change). FK gate auto-derived from `cls.__table__.foreign_keys` (`app/tools/entity/_fk_gate.py`); `DomainErrorMiddleware` wraps resource + prompt envelopes too; Pydantic `ValidationError` → typed `app.shared.errors.ValidationError`; `AggregateResult.value` union has `bool` BEFORE `int` (`distinct(variable_tempo)` → `[false, true]`); validation gates added on `entity_get.include_relations`, `suggest_next.energy_direction`, `transition.{scoring_profile,fx_type,persist}`, `sequence_optimize.{pinned,excluded}`, `ui_score_pool_matrix` duplicate ids, `ui_transition_score` `from==to`, `entity_update set` BPM partial-update invariant; `unlock_namespace` accepts `ui:read`; `provider_read.id` accepts `int \| str`; `YandexAdapter.read("track_batch")` accepts legacy `ids` key; `app/audio/core/loader.py` wraps `wave.Error` → typed `RuntimeError`; SQLite `PRAGMA foreign_keys=ON` via `connect` event listener. |
| (prompts) | 20 | 27 | Prompt catalog grew 6 → **18** (additive, no tool/resource surface change): +`library_health_workflow`, `analyze_library_workflow`, `harmonic_journey_workflow`, `subgenre_journey_workflow`, `scenario_set_workflow`, `b2b_planning_workflow`, `extend_set_workflow`, `set_review_workflow`, `fix_transition_workflow`, `replace_track_workflow`, `crate_digging_workflow`, `taste_profile_workflow`, `playlist_sync_workflow`. Research-backed (`docs/research/2026-06-22-…`); content pinned by `test_prompt_content_correctness.py`. |

# MCP Tool Catalog

Quick reference for v1.0.0 — **13 tool dispatchers + 20 resources + 6 prompts**.

The 88-tool catalog of v0.8 was collapsed via polymorphism: generic CRUD
(`entity_*`) dispatches via `EntityRegistry`, generic provider access
(`provider_*`) via `ProviderRegistry`, side-effects live in handlers.
Everything else is exposed as **resources** (read-only views) or
**prompts** (workflow recipes) — resources/prompts can be surfaced as
tools via `app/server/transforms.py` for tool-only clients.

## Tools (13)

### Entity CRUD (6, namespace `crud:read` / `crud:write` / `crud:destructive`)

| Tool | Params | RO | Hidden |
|------|--------|----|--------|
| `entity_list` | entity, filters?, search?, fields?, sort?, limit=50, cursor?, with_total=false | yes | no |
| `entity_get` | entity, id, fields?, include_relations? | yes | no |
| `entity_aggregate` | entity, operation(count\|distinct\|histogram\|min_max\|sum\|avg), field?, group_by?, filters? | yes | no |
| `entity_create` | entity, data | no | no |
| `entity_update` | entity, id, data | no | `crud:destructive` |
| `entity_delete` | entity, id | no (destructive) | `crud:destructive` |

Supported entities (via `EntityRegistry`): track, track_features, audio_file,
playlist, set, set_version, transition, transition_history, track_affinity,
track_feedback, scoring_profile, key, provider_metadata.

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

### Admin (1, namespace `admin`)

| Tool | Params | RO |
|------|--------|-----|
| `unlock_namespace` | namespace(crud:destructive\|provider:write\|sync\|all), action(unlock\|lock\|status)=status | no |

## Resources (20)

All read-only, MIME `application/json`, auto-discovered from `app/resources/`.

### Local (per-entity views)

| URI | File | Purpose |
|---|---|---|
| `local://playlists/{id}{?include_tracks}` | playlist.py | Playlist detail |
| `local://playlists/{id}/audit` | playlist.py | Techno audit report for a playlist |
| `local://sets/{id}/{view}` | set.py | view=summary\|tracks\|transitions\|full |
| `local://sets/{id}/cheatsheet{?version}` | set.py | DJ cheat sheet text |
| `local://sets/{id}/narrative` | set.py | Narrative analysis (arc, moods) |
| `local://transition/{from_id}/{to_id}/score` | transition.py | Pairwise transition score |
| `local://transition/{from_id}/{to_id}/explain` | transition.py | Explain scored components |
| `local://transition_history/best_pairs{?track_id,limit}` | transition_history.py | Best historical pairs |
| `local://transition_history/history{?limit,track_id}` | transition_history.py | Transition log |

### Schema (introspection)

| URI | Purpose |
|---|---|
| `schema://entities` | List all entity types + their schemas |
| `schema://entities/{entity}` | Single entity: filters, fields, presets |
| `schema://providers` | List providers + capabilities |
| `schema://providers/{name}` | Single provider: supported entities/operations |

### Session (per-client state)

| URI | Purpose |
|---|---|
| `session://set-draft` | Current set-in-progress (in-memory) |
| `session://tool-history` | Last N tool calls in session |
| `session://energy-trend{?limit}` | Adaptive arc — energy direction suggestion |

### Reference (static knowledge)

| URI | Purpose |
|---|---|
| `reference://camelot` | Camelot wheel topology |
| `reference://subgenres` | 15 techno subgenres + scoring weights |
| `reference://templates` | 8 set templates (warm_up_30, classic_60, …) |
| `reference://audit_rules` | Techno audit thresholds |

## Prompts (6, namespace `workflow`)

| Prompt | Purpose |
|---|---|
| `dj_expert_session` | Prime the LLM with domain knowledge (Camelot, subgenres, templates, audit rules) |
| `build_set_workflow` | End-to-end recipe: playlist → optimize → score → persist |
| `deliver_set_workflow` | Export a set (+ optional YM sync) with conflict gate |
| `expand_playlist_workflow` | Provider discovery + import + analyze to grow a playlist |
| `full_pipeline` | Chain expand → build → deliver |
| `quick_mix_check` | Single pairwise mix compatibility (a→b) |

## Visibility

| Namespace | Tools | Default |
|---|---|---|
| `crud:read` | entity_list, entity_get, entity_aggregate | visible |
| `crud:write` | entity_create | visible |
| `crud:destructive` | entity_update, entity_delete | **locked** |
| `provider:read` | provider_read, provider_search | visible |
| `provider:write` | provider_write | **locked** |
| `compute` | transition_score_pool, sequence_optimize | visible |
| `sync` | playlist_sync | **locked** |
| `admin` | unlock_namespace | visible |
| `workflow` | all prompts | visible |

Unlock hidden namespaces for the current session via
`unlock_namespace(namespace="provider:write", action="unlock")` or
`namespace="all"`. FastMCP fires `notifications/tools/list_changed` so the
client re-fetches the tool list.

## Tool count history

| Version | Count | Notes |
|---|---|---|
| v0.8.0 | 88 | 61 visible + 27 hidden; narrow per-operation tools |
| v1.0.0 | 13 | Generic dispatchers + polymorphism; resources/prompts carry the rest |

# MCP Tool Catalog

Quick reference for all MCP tools (~51 total, visible + hidden).

## Core Tools (always visible)

### CRUD — Tracks (tag: `core`, file: `tracks.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_tracks` | limit, cursor, bpm_min/max? | yes |
| `get_track` | id?, query? | yes |
| `manage_tracks` | action(create\|update\|archive\|unarchive), data? | no |
| `get_track_features` | id?, query?, include_sections? | yes |

### CRUD — Playlists (tag: `core`, file: `playlists.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_playlists` | source?, limit, cursor | yes |
| `get_playlist` | id?, query?, include_tracks? | yes |
| `manage_playlist` | action(create\|update\|delete\|add_tracks\|remove_tracks\|reorder), data?, track_refs?, positions? | no |

### CRUD — Sets (tag: `core`, file: `sets.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_sets` | template?, limit, cursor | yes |
| `get_set` | id?, query?, view(summary\|tracks\|transitions\|full) | yes |
| `manage_set` | action(create\|update\|delete\|add_constraint\|remove_constraint\|add_feedback), data? | no |

### Search (tag: `core`, file: `search.py`)

| Tool | Params | RO |
|------|--------|-----|
| `search_library` | query, entity(tracks\|artists\|playlists\|sets\|all), limit | yes |

### Set Building (tag: `sets`, file: `sets.py`)

| Tool | Params | RO | Timeout |
|------|--------|----|---------|
| `build_set` | playlist_id, name, template?, target_duration_min?, algorithm(greedy\|ga), dry_run? | no | 120s |
| `rebuild_set` | set_id, pin_tracks?, exclude_tracks?, algorithm, version_label? | no | 120s |
| `score_transitions` | mode(set\|pair\|track_candidates), set_id?, from/to_track_id?, track_id? | no | — |
| `get_set_cheat_sheet` | set_id, version? | yes | — |
| `get_set_templates` | — | yes | — |

### Set Reasoning (tag: `sets`, file: `reasoning.py`)

| Tool | Params | RO |
|------|--------|-----|
| `suggest_next_track` | set_id, after_position, count?, prefer_mood?, energy_direction? | yes |
| `explain_transition` | from_track_id, to_track_id | yes |
| `find_replacement` | set_id, position, count? | yes |
| `compare_set_versions` | set_id, version_a?, version_b? | yes |
| `quick_set_review` | set_id | yes |
| `analyze_set_narrative` | set_id | yes |

### Admin (tag: `admin`, file: `admin.py`)

| Tool | Params | RO |
|------|--------|-----|
| `unlock_tools` | action(unlock\|lock\|status), category? — **per-session** | no |
| `list_platforms` | — | yes |

## Extended Tools (unlock per category)

### Delivery & Export (tag: `delivery`, file: `delivery.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `deliver_set` | set_id, version?, output_dir?, copy_files?, sync_to_ym?, formats?, dry_run? | 300s |

### Discovery & Download (tag: `discovery`)

| Tool | File | Params | RO |
|------|------|--------|-----|
| `find_similar_tracks` | discovery.py | track_id, strategy(ym\|llm)?, limit?, min/max_duration_ms?, genre_filter?, genre_blacklist?, exclude_patterns? | yes |
| `expand_platform_playlist` | discovery.py | playlist_id, target_count?, genre_filter?, genre_blacklist?, exclude_patterns?, min/max_duration_ms?, use_feedback?, dry_run? | no |
| `filter_by_feedback` | discovery.py | ym_track_ids (returns passed/blocked/boosted) | yes |
| `import_tracks` | importing.py | track_refs, playlist_id?, auto_analyze? | no |
| `download_tracks` | importing.py | track_refs, target_dir?, skip_existing?, prefer_bitrate? | no |

### Curation (tag: `curation`, file: `curation.py`)

| Tool | Params | RO |
|------|--------|-----|
| `classify_mood` | track_ids?\|playlist_id?, reclassify? | no |
| `audit_playlist` | playlist_id?, playlist_query?, check?, template? | yes |
| `distribute_to_subgenres` | source_playlist_id?, mode?, sync_to_ym?, dry_run? | no |
| `get_library_stats` | — | yes |

### Sync (tag: `sync`, file: `sync.py`)

| Tool | Params | RO |
|------|--------|-----|
| `sync_playlist` | playlist_id, direction(pull\|push\|diff)?, conflict_strategy?, dry_run?=true | no |
| `push_set_to_platform` | set_id, platform_playlist_name?, mode(create\|update\|auto)? | no |

### Platform API (tag: `platform`, package: `platform/`)

Each platform tool lives in its own submodule under `app/controllers/tools/platform/`:

| Tool | File | Params | RO |
|------|------|--------|-----|
| `search_platform` | `platform/search.py` | query, type(tracks\|albums\|artists\|playlists\|all)?, limit? | yes |
| `get_platform_tracks` | `platform/tracks.py` | track_ids, fields? | yes |
| `get_platform_artist_tracks` | `platform/tracks.py` | artist_id, offset?, limit?, sort_by(date\|popularity)? | yes |
| `get_platform_album` | `platform/albums.py` | album_id, include_tracks? | yes |
| `platform_playlists` | `platform/playlists.py` | action(get\|get_tracks\|list\|create\|rename\|delete\|add_tracks\|remove_tracks), playlist_id?, name?, track_ids?, revision? | varies |
| `platform_liked_tracks` | `platform/likes.py` | action(get_liked\|add\|remove), track_ids? | varies |

`platform_playlists` and `platform_liked_tracks` dispatch via `ActionDispatcher` (Command + Registry) — adding a new action is `@_dispatcher.register("name")` plus a handler, no `if/elif` edits.

## Hidden Tools (explicit unlock required)

### Audio Analysis (tag: `audio`, file: `audio.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `analyze_track` | track_id?, track_query?, analyzers?, force?, level? | 120s |
| `analyze_batch` | track_ids?\|playlist_id?, analyzers?, level?, force? | 600s |
| `separate_stems` | track_id?, track_query?, stems? | 300s |
| `classify_track` | track_id | — |
| `gate_track` | track_id, criteria? | — |
| `get_similar_tracks` | ym_track_id, limit?, min/max_duration_ms?, genre_filter?, genre_blacklist?, exclude_patterns? | — |

### Memory (tag: `memory`, file: `memory.py`)

Hidden by default; unlock via `unlock_tools`. Dispatch tools consolidate prior per-action MCP tools.

| Tool | Params | RO |
|------|--------|-----|
| `track_feedback` | action(like\|ban\|rate\|get\|list_liked\|list_banned), track_id?, rating?, notes?, ... | varies |
| `transition_history` | action(log\|list\|best_pairs\|react), from_track_id?, to_track_id?, entry_id?, reaction?, ... | varies |
| `track_affinity` | action(refresh\|get_pair\|recommend), track_id?, track_a_id?, track_b_id?, limit?, ... | varies |
| `scoring_profile` | action(create\|list\|get_weights), name?, weights?, description?, profile_name?, ... | varies |
| `session_arc` | action(trend\|suggest\|full_arc), last_n?, limit?, ... | varies |

## Summary

| Category | Tag | Visibility |
|----------|-----|-----------|
| CRUD (tracks + playlists + sets) | `core` | Always |
| Search | `core` | Always |
| Set Building | `sets` | Always |
| Set Reasoning | `sets` | Always |
| Admin | `admin` | Always |
| Delivery & Export | `delivery` | Unlockable |
| Discovery & Download | `discovery` | Unlockable |
| Curation | `curation` | Unlockable |
| Sync | `sync` | Unlockable |
| Platform API | `platform` | Unlockable |
| Audio Analysis | `audio` | Unlockable |
| Memory | `memory` | Unlockable |
| `transition://{from_id}/{to_id}/score` (resource) | — | Always |
| `session://tool-history` (resource) | — | Always |

> **Note:** All 7 extended/hidden categories start disabled. Use `unlock_tools(action="unlock", category="all")`
> to enable them — this triggers `notifications/tools/list_changed` so the client re-fetches the tool list.
> `unlock_tools` is **per-session**: visibility changes affect only the current MCP session, not other clients.

## Legend

- **RO**: readOnlyHint annotation (yes = no side effects)
- **?**: optional parameter
- **\|**: alternative (enum values)

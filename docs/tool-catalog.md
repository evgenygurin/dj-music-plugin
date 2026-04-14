# MCP Tool Catalog

Quick reference for all MCP tools (visible + hidden).

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

### CRUD — Sets (tag: `core`, file: `crud.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_sets` | template?, limit, cursor | yes |
| `get_set` | id?, query?, view(summary\|tracks\|transitions\|full) | yes |
| `manage_set` | action(create\|update\|delete\|add_constraint\|remove_constraint\|add_feedback), data? | no |

### Search (tag: `core`, file: `search.py`)

| Tool | Params | RO |
|------|--------|-----|
| `search` | query, entity(tracks\|artists\|playlists\|sets\|all), limit | yes |
| `filter_tracks` | bpm_min/max?, key?, key_compatible?, energy_min/max?, has_features?, exclude_set_id?, sort_by, limit, cursor | yes |

### Set Building (tag: `sets`, file: `sets.py`)

| Tool | Params | RO | Timeout |
|------|--------|----|---------|
| `build_set` | playlist_id, name, template?, target_duration_min?, algorithm(greedy\|ga), dry_run? | no | 120s |
| `rebuild_set` | set_id, pin_tracks?, exclude_tracks?, algorithm, version_label? | no | 120s |
| `score_transitions` | mode(set\|pair\|track_candidates), set_id?, from/to_track_id?, track_id?, top_n? | no | — |
| `get_set_cheat_sheet` | set_id, version? | yes | — |

### Set Reasoning (tag: `sets`, file: `reasoning.py`)

| Tool | Params | RO |
|------|--------|-----|
| `suggest_next_track` | set_id, after_position, count?, prefer_mood?, energy_direction? | yes |
| `explain_transition` | from_track_id, to_track_id | yes |
| `find_replacement` | set_id, position, count? | yes |
| `compare_set_versions` | set_id, version_a?, version_b? | yes |
| `quick_set_review` | set_id | yes |

### Admin (tag: `admin`, file: `admin.py`)

| Tool | Params | RO |
|------|--------|-----|
| `unlock_tools` | action(unlock\|lock\|status), category? | no |
| `list_platforms` | — | yes |

## Extended Tools (unlock per category)

### Delivery & Export (tag: `delivery`, file: `delivery.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `deliver_set` | set_id, version?, output_dir?, copy_files?, sync_to_ym?, formats?, dry_run? | 300s |
| `export_set` | set_id, format, output_path?, rekordbox_options? | — |

### Discovery & Download (tag: `discovery`)

| Tool | File | Params | RO |
|------|------|--------|-----|
| `find_similar_tracks` | discovery.py | track_id, strategy(ym\|llm)?, limit?, min/max_duration_ms?, genre_filter?, genre_blacklist?, exclude_patterns? | yes |
| `expand_playlist_ym` | discovery.py | ym_playlist_kind, target_count?, genre_filter?, genre_blacklist?, exclude_patterns?, min/max_duration_ms?, use_feedback?, dry_run? | no |
| `filter_by_feedback` | discovery.py | ym_track_ids (returns passed/blocked/boosted) | yes |
| `import_tracks` | import_download.py | track_refs, playlist_id?, auto_analyze? | no |
| `download_tracks` | import_download.py | track_refs, target_dir?, skip_existing?, prefer_bitrate? | no |

### Curation (tag: `curation`, file: `curation.py`)

| Tool | Params | RO |
|------|--------|-----|
| `classify_mood` | track_ids?\|playlist_id?, reclassify? | no |
| `audit_playlist` | playlist_id?, playlist_query?, check?, template? | yes |
| `review_set_quality` | set_id, version? | yes |
| `distribute_to_subgenres` | source_playlist_id?, mode?, sync_to_ym?, dry_run? | no |
| `get_library_stats` | — | yes |

### Sync (tag: `sync`, file: `sync.py`)

| Tool | Params | RO |
|------|--------|-----|
| `sync_playlist` | playlist_id, direction(pull\|push\|diff)?, conflict_strategy?, dry_run?=true | no |
| `push_set_to_ym` | set_id, ym_playlist_name?, mode(create\|update\|auto)? | no |

### YM API (tag: `ym`, package: `yandex/`)

Each YM tool lives in its own submodule under `app/controllers/tools/yandex/`:

| Tool | File | Params | RO |
|------|------|--------|-----|
| `ym_search` | `yandex/search.py` | query, type(tracks\|albums\|artists\|playlists\|all)?, limit? | yes |
| `ym_get_tracks` | `yandex/tracks.py` | track_ids, fields? | yes |
| `ym_artist_tracks` | `yandex/tracks.py` | artist_id, page?, sort_by(date\|popularity)? | yes |
| `ym_get_album` | `yandex/albums.py` | album_id, include_tracks? | yes |
| `ym_playlists` | `yandex/playlists.py` | action(get\|get_tracks\|list\|create\|rename\|delete\|add_tracks\|remove_tracks), kind?, name?, track_ids?, revision? | varies |
| `ym_likes` | `yandex/likes.py` | action(get_liked\|add\|remove), track_ids? | varies |

`ym_playlists` and `ym_likes` dispatch via `ActionDispatcher` (Command + Registry) — adding a new action is `@_dispatcher.register("name")` plus a handler, no `if/elif` edits.

## Hidden Tools (explicit unlock required)

### Audio Analysis (tag: `audio`, file: `audio.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `analyze_track` | track_id?, track_query?, analyzers?, force?, level? | 120s |
| `analyze_batch` | track_ids?\|playlist_id?, batch_size?, analyzers?, level?, force? | 600s |
| `separate_stems` | track_id?, track_query?, stems? | 300s |

### Atomic (tag: `atomic`, file: `audio_atomic.py`)

Low-level building blocks used by composite tools. Not intended for direct use.

| Tool | Params | RO |
|------|--------|-----|
| `analyze_one_track` | track_id, analyzers?, force? | no |
| `classify_one_track` | track_id | no |
| `gate_one_track` | track_id, criteria? | yes |
| `get_similar_one_track` | ym_track_id, limit?, min/max_duration_ms?, genre_filter?, genre_blacklist?, exclude_patterns? | yes |

## New Tools (since v0.7.0)

### Track Feedback (tag: `core`, file: `track_feedback.py`)

| Tool | Params | RO |
|------|--------|-----|
| `like_track` | track_id | no |
| `ban_track` | track_id | no |
| `rate_track` | track_id, rating, notes? | no |
| `get_track_feedback` | track_id | yes |
| `get_banned_tracks` | — | yes |
| `get_liked_tracks` | — | yes |

### Transition History (tag: `core`, file: `transition_history.py`)

| Tool | Params | RO |
|------|--------|-----|
| `log_transition` | from_track_id, to_track_id, overall_score?, style?, ... | no |
| `get_transition_history` | limit?, from_track_id?, to_track_id?, min_score? | yes |
| `get_best_pairs` | track_id, limit? | yes |
| `update_reaction` | entry_id, reaction | no |

### Track Affinity (tag: `core`, file: `track_affinity.py`)

| Tool | Params | RO |
|------|--------|-----|
| `refresh_affinity` | — | no |
| `get_track_affinity` | track_a_id, track_b_id | yes |
| `get_affinity_recommendations` | track_id, limit? | yes |

### Scoring Profiles (tag: `core`, file: `scoring_profile.py`)

| Tool | Params | RO |
|------|--------|-----|
| `create_scoring_profile` | name, bpm/harmonic/energy/spectral/groove/timbral_weight, description? | no |
| `list_scoring_profiles` | — | yes |
| `get_scoring_weights` | profile_name? | yes |

### Adaptive Arc (tag: `core`, file: `adaptive_arc.py`)

| Tool | Params | RO |
|------|--------|-----|
| `get_energy_trend` | last_n? | yes |
| `suggest_energy_direction` | last_n? | yes |
| `get_session_arc` | limit? | yes |

### Set Narrative (tag: `sets`, file: `set_narrative.py`)

| Tool | Params | RO |
|------|--------|-----|
| `analyze_set_narrative` | set_id | yes |

### Misc

| Tool | File | Params | RO |
|------|------|--------|-----|
| `get_set_templates` | sets_meta.py | — | yes |

## Summary

| Category | Tag | Visibility |
|----------|-----|-----------|
| CRUD (tracks + playlists + sets) | `core` | Always |
| Search | `core` | Always |
| Set Building | `sets` | Always |
| Set Reasoning | `sets` | Always |
| Admin | `admin` | Always |
| Track Feedback | `core` | Always |
| Transition History | `core` | Always |
| Track Affinity | `core` | Always |
| Scoring Profiles | `core` | Always |
| Adaptive Arc | `core` | Always |
| Set Narrative | `sets` | Always |
| Misc (templates) | `core` | Always |
| Delivery & Export | `delivery` | Unlockable |
| Discovery & Download | `discovery` | Unlockable |
| Curation | `curation` | Unlockable |
| Sync | `sync` | Unlockable |
| YM API | `ym` | Unlockable |
| Audio Analysis | `audio` | Unlockable |
| Atomic | `atomic` | Unlockable |

> **Note:** All 7 extended/hidden categories start disabled. Use `unlock_tools(action="unlock", category="all")`
> to enable them — this triggers `notifications/tools/list_changed` so the client re-fetches the tool list.

## Legend

- **RO**: readOnlyHint annotation (yes = no side effects)
- **?**: optional parameter
- **\|**: alternative (enum values)

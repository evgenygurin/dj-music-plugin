# MCP Tool Catalog

Quick reference for all 50 tools (46 visible + 4 atomic hidden).

## Core Tools (always visible — 23 tools)

### CRUD — Tracks (4 tools, tag: `core`, file: `tracks.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_tracks` | limit, cursor, bpm_min/max? | yes |
| `get_track` | id?, query? | yes |
| `manage_tracks` | action(create\|update\|archive\|unarchive), data? | no |
| `get_track_features` | id?, query?, include_sections? | yes |

### CRUD — Playlists (3 tools, tag: `core`, file: `playlists.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_playlists` | source?, limit, cursor | yes |
| `get_playlist` | id?, query?, include_tracks? | yes |
| `manage_playlist` | action(create\|update\|delete\|add_tracks\|remove_tracks\|reorder), data?, track_refs?, positions? | no |

### CRUD — Sets (3 tools, tag: `core`, file: `crud.py`)

| Tool | Params | RO |
|------|--------|-----|
| `list_sets` | template?, limit, cursor | yes |
| `get_set` | id?, query?, view(summary\|tracks\|transitions\|full) | yes |
| `manage_set` | action(create\|update\|delete\|add_constraint\|remove_constraint\|add_feedback), data? | no |

### Search (2 tools, tag: `core`, file: `search.py`)

| Tool | Params | RO |
|------|--------|-----|
| `search` | query, entity(tracks\|artists\|playlists\|sets\|all), limit | yes |
| `filter_tracks` | bpm_min/max?, key?, energy_min/max?, mood?, sort_by, limit, cursor | yes |

### Set Building (4 tools, tag: `sets`, file: `sets.py`)

| Tool | Params | RO | Timeout |
|------|--------|----|---------|
| `build_set` | playlist_id, name, template?, algorithm(greedy\|ga), dry_run? | no | 120s |
| `rebuild_set` | set_id, pin/unpin/exclude/include/swap?, algorithm, version_label? | no | 120s |
| `score_transitions` | mode(set\|pair\|track_candidates), set_id?, from/to_track_id?, top_n? | no | — |
| `get_set_cheat_sheet` | set_id, version? | yes | — |

### Set Reasoning (5 tools, tag: `sets`, file: `reasoning.py`)

| Tool | Params | RO |
|------|--------|-----|
| `suggest_next_track` | set_id, after_position, count?, prefer_mood?, energy_direction? | yes |
| `explain_transition` | from_track_id, to_track_id | yes |
| `find_replacement` | set_id, position, count? | yes |
| `compare_set_versions` | set_id, version_a?, version_b? | yes |
| `quick_set_review` | set_id | yes |

### Admin (2 tools, tag: `admin`, file: `admin.py`)

| Tool | Params | RO |
|------|--------|-----|
| `unlock_tools` | action(unlock\|lock\|status), category? | no |
| `list_platforms` | — | yes |

## Extended Tools (unlock per category — 20 tools)

### Delivery & Export (2 tools, tag: `delivery`, file: `delivery.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `deliver_set` | set_id, version?, output_dir?, copy_files?, sync_to_ym?, formats?, dry_run? | 300s |
| `export_set` | set_id, format, output_path?, rekordbox_options? | — |

### Discovery & Download (5 tools, tag: `discovery`)

| Tool | File | Params | RO |
|------|------|--------|-----|
| `find_similar_tracks` | discovery.py | track_id, strategy?, limit?, bpm_tolerance?, key_compatible? | yes |
| `expand_playlist_ym` | discovery.py | playlist_id, target_count?, strategy? | no |
| `filter_by_feedback` | discovery.py | playlist_id?, liked_only? | yes |
| `import_tracks` | import_download.py | track_refs, playlist_id?, auto_analyze? | no |
| `download_tracks` | import_download.py | track_refs, target_dir?, skip_existing? | no |

### Curation (5 tools, tag: `curation`, file: `curation.py`)

| Tool | Params | RO |
|------|--------|-----|
| `classify_mood` | track_ids?\|playlist_id?, reclassify? | no |
| `audit_playlist` | playlist_id?, playlist_query?, check?, template? | yes |
| `review_set_quality` | set_id, version? | yes |
| `distribute_to_subgenres` | source_playlist_id?, mode?, sync_to_ym?, dry_run? | no |
| `get_library_stats` | — | yes |

### Sync (2 tools, tag: `sync`, file: `sync.py`)

| Tool | Params | RO |
|------|--------|-----|
| `sync_playlist` | playlist_id, direction?, conflict_strategy?, dry_run? | no |
| `push_set_to_ym` | set_id, ym_playlist_name?, mode? | no |

### YM API (6 tools, tag: `ym`, file: `ym.py`)

| Tool | Params | RO |
|------|--------|-----|
| `ym_search` | query, type?, limit? | yes |
| `ym_get_tracks` | track_ids | yes |
| `ym_get_album` | album_id, include_tracks? | yes |
| `ym_artist_tracks` | artist_id, page?, sort_by? | yes |
| `ym_playlists` | action(get\|get_tracks\|list\|create\|rename\|delete\|add_tracks\|remove_tracks) | varies |
| `ym_likes` | action(get_liked\|add\|remove), track_ids? | varies |

## Hidden Tools (explicit unlock required — 7 tools)

### Audio Analysis (3 tools, tag: `audio`, file: `audio.py`)

| Tool | Params | Timeout |
|------|---------|---------|
| `analyze_track` | track_id?, track_query?, analyzers?, force? | 120s |
| `analyze_batch` | track_ids?\|playlist_id?, analyzers?, priority? | 600s |
| `separate_stems` | track_id?, track_query?, stems? | 300s |

### Atomic (4 tools, tag: `atomic`, file: `audio_atomic.py`)

Low-level building blocks used by composite tools. Not intended for direct use.

| Tool | Params | RO |
|------|--------|-----|
| `analyze_one_track` | track_id | no |
| `classify_one_track` | track_id | no |
| `gate_one_track` | track_id | yes |
| `get_similar_one_track` | track_id, limit? | yes |

## Summary

| Category | Count | Tag | Visibility |
|----------|-------|-----|-----------|
| CRUD (tracks + playlists + sets) | 10 | `core` | Always |
| Search | 2 | `core` | Always |
| Set Building | 4 | `sets` | Always |
| Set Reasoning | 5 | `sets` | Always |
| Admin | 2 | `admin` | Always |
| Delivery & Export | 2 | `delivery` | Extended |
| Discovery & Download | 5 | `discovery` | Extended |
| Curation | 5 | `curation` | Extended |
| Sync | 2 | `sync` | Extended |
| YM API | 6 | `ym` | Extended |
| Audio Analysis | 3 | `audio` | Hidden |
| Atomic | 4 | `atomic` | Hidden |
| **Total** | **50** | | |

## Legend

- **RO**: readOnlyHint annotation (yes = no side effects)
- **?**: optional parameter
- **\|**: alternative (enum values)

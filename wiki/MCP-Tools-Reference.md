# MCP Tools Reference

Complete reference for all 50 MCP tools (46 visible + 4 atomic hidden).

## Tool Visibility

| Tier | Count | Behavior |
|------|-------|----------|
| **Core** (always visible) | 23 | Available immediately |
| **Extended** (unlock per category) | 20 | Requires `unlock_tools(category="...")` |
| **Hidden** (explicit unlock) | 7 | Requires `unlock_tools(category="audio"/"atomic")` |

```python
# Check current visibility status
unlock_tools(action="status")

# Unlock a category
unlock_tools(action="unlock", category="discovery")

# Lock a category back
unlock_tools(action="lock", category="discovery")
```

---

## Core Tools (Always Visible)

### CRUD -- Tracks (4 tools)

**Tag:** `core` | **File:** `tracks.py`

#### `list_tracks`
List tracks with optional BPM filtering and cursor-based pagination.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | 20 | Max results |
| `cursor` | str | No | None | Pagination cursor |
| `bpm_min` | float | No | None | Minimum BPM filter |
| `bpm_max` | float | No | None | Maximum BPM filter |

**Read-only:** Yes

#### `get_track`
Get a single track by ID or text search.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | int | No | None | Track ID |
| `query` | str | No | None | Text search (ILIKE) |

**Read-only:** Yes | Must provide either `id` or `query`

#### `manage_tracks`
Create, update, or archive tracks.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `create`, `update`, `archive`, `unarchive` |
| `data` | dict | No | None | Track data fields |

**Read-only:** No

#### `get_track_features`
Get computed audio features for a track.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | int | No | None | Track ID |
| `query` | str | No | None | Text search |
| `include_sections` | bool | No | False | Include track sections |

**Read-only:** Yes

---

### CRUD -- Playlists (3 tools)

**Tag:** `core` | **File:** `playlists.py`

#### `list_playlists`
List playlists with optional source filter.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | str | No | None | Filter by source app |
| `limit` | int | No | 20 | Max results |
| `cursor` | str | No | None | Pagination cursor |

**Read-only:** Yes

#### `get_playlist`
Get a playlist by ID or name search.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | int | No | None | Playlist ID |
| `query` | str | No | None | Name search |
| `include_tracks` | bool | No | False | Include track list |

**Read-only:** Yes

#### `manage_playlist`
Manage playlists: create, update, delete, add/remove/reorder tracks.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `create`, `update`, `delete`, `add_tracks`, `remove_tracks`, `reorder` |
| `data` | dict | No | None | Playlist data |
| `track_refs` | list[str] | No | None | Track references (for add/remove) |
| `positions` | list[int] | No | None | Positions (for remove/reorder) |

**Read-only:** No

---

### CRUD -- Sets (3 tools)

**Tag:** `core` | **File:** `crud.py`

#### `list_sets`
List DJ sets with optional template filter.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `template` | str | No | None | Filter by template name |
| `limit` | int | No | 20 | Max results |
| `cursor` | str | No | None | Pagination cursor |

**Read-only:** Yes

#### `get_set`
Get a DJ set with configurable detail level.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | int | No | None | Set ID |
| `query` | str | No | None | Name search |
| `view` | str | No | `"summary"` | `summary`, `tracks`, `transitions`, `full` |

**Read-only:** Yes

#### `manage_set`
Manage DJ sets: create, update, delete, constraints, feedback.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `create`, `update`, `delete`, `add_constraint`, `remove_constraint`, `add_feedback` |
| `data` | dict | No | None | Set data |

**Read-only:** No

---

### Search (2 tools)

**Tag:** `core` | **File:** `search.py`

#### `search`
Universal search across all entity types.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | Yes | -- | Search text |
| `entity` | str | No | `"all"` | `tracks`, `artists`, `playlists`, `sets`, `all` |
| `limit` | int | No | 20 | Max results |

**Read-only:** Yes

#### `filter_tracks`
Parametric filter by audio features.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bpm_min` | float | No | None | Minimum BPM |
| `bpm_max` | float | No | None | Maximum BPM |
| `key` | str | No | None | Camelot key (e.g., "8A") |
| `energy_min` | float | No | None | Minimum energy |
| `energy_max` | float | No | None | Maximum energy |
| `mood` | str | No | None | Subgenre name |
| `sort_by` | str | No | `"bpm"` | Sort field |
| `limit` | int | No | 20 | Max results |
| `cursor` | str | No | None | Pagination cursor |

**Read-only:** Yes

---

### Set Building (4 tools)

**Tag:** `sets` | **File:** `sets.py`

#### `build_set`
Build a DJ set from a playlist using GA or greedy algorithm.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playlist_id` | int | Yes | -- | Source playlist ID |
| `name` | str | Yes | -- | Set name |
| `template` | str | No | None | Template: `classic_60`, `peak_hour_60`, etc. |
| `algorithm` | str | No | `"greedy"` | `greedy` or `ga` |
| `dry_run` | bool | No | False | Preview without saving |

**Read-only:** No | **Timeout:** 120s

#### `rebuild_set`
Rebuild a set with pin/exclude/swap modifications.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `pin` | list[int] | No | None | Track IDs to pin |
| `unpin` | list[int] | No | None | Track IDs to unpin |
| `exclude` | list[int] | No | None | Track IDs to exclude |
| `include` | list[int] | No | None | Track IDs to include |
| `swap` | list[list[int]] | No | None | Pairs to swap [[a,b], ...] |
| `algorithm` | str | No | `"ga"` | `greedy` or `ga` |
| `version_label` | str | No | None | Label for new version |

**Read-only:** No | **Timeout:** 120s

#### `score_transitions`
Score transitions for a set, a pair, or find best candidates.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mode` | str | Yes | -- | `set`, `pair`, `track_candidates` |
| `set_id` | int | No | None | For mode=set |
| `from_track_id` | int | No | None | For mode=pair/track_candidates |
| `to_track_id` | int | No | None | For mode=pair |
| `top_n` | int | No | 10 | For mode=track_candidates |

**Read-only:** No

#### `get_set_cheat_sheet`
Get a human-readable transition cheat sheet.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `version` | str | No | None | Specific version label |

**Read-only:** Yes

---

### Set Reasoning (5 tools)

**Tag:** `sets` | **File:** `reasoning.py`

#### `suggest_next_track`
Suggest the best next track after a given position.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `after_position` | int | Yes | -- | Position to suggest after |
| `count` | int | No | 5 | Number of suggestions |
| `prefer_mood` | str | No | None | Preferred subgenre |
| `energy_direction` | str | No | None | `up`, `down`, `stable` |

**Read-only:** Yes

#### `explain_transition`
Detailed explanation of a transition between two tracks.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from_track_id` | int | Yes | -- | Source track |
| `to_track_id` | int | Yes | -- | Target track |

**Read-only:** Yes

#### `find_replacement`
Find replacement candidates for a track at a specific position.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `position` | int | Yes | -- | Position to replace |
| `count` | int | No | 5 | Number of candidates |

**Read-only:** Yes

#### `compare_set_versions`
Compare two versions of a set side-by-side.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `version_a` | str | No | None | First version label |
| `version_b` | str | No | None | Second version label |

**Read-only:** Yes

#### `quick_set_review`
Quick quality review of a set: scores, conflicts, energy arc.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |

**Read-only:** Yes

---

### Admin (2 tools)

**Tag:** `admin` | **File:** `admin.py`

#### `unlock_tools`
Control tool visibility.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `unlock`, `lock`, `status` |
| `category` | str | No | None | Category to unlock/lock |

**Read-only:** No

Available categories: `delivery`, `discovery`, `curation`, `sync`, `ym`, `audio`, `atomic`

#### `list_platforms`
List supported external platforms.

**Read-only:** Yes | No parameters

---

## Extended Tools (Unlock Per Category)

### Delivery & Export (2 tools)

**Tag:** `delivery` | **File:** `delivery.py`

#### `deliver_set`
Full set delivery: score, export files, optional YM sync.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `version` | str | No | None | Version label |
| `output_dir` | str | No | `"generated-sets/"` | Output directory |
| `copy_files` | bool | No | True | Copy MP3 files |
| `sync_to_ym` | bool | No | False | Push to YM playlist |
| `formats` | list[str] | No | all | Export formats |
| `dry_run` | bool | No | False | Preview only |

**Timeout:** 300s | Uses elicitation for conflict handling

#### `export_set`
Export a set in a specific format.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `format` | str | Yes | -- | `m3u8`, `rekordbox_xml`, `json_guide`, `cheat_sheet` |
| `output_path` | str | No | None | Custom output path |
| `rekordbox_options` | dict | No | None | Rekordbox-specific options |

---

### Discovery & Download (5 tools)

**Tag:** `discovery` | **Files:** `discovery.py`, `import_download.py`

#### `find_similar_tracks`
Find similar tracks via YM recommendations or LLM-assisted discovery.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_id` | int | Yes | -- | Source track ID |
| `strategy` | str | No | `"ym"` | `ym` (recommendations) or `llm` (AI-assisted) |
| `limit` | int | No | 20 | Max results |
| `bpm_tolerance` | float | No | 10.0 | BPM range filter |
| `key_compatible` | bool | No | True | Filter by Camelot compatibility |
| `search_queries` | list[str] | No | None | For strategy="llm": pre-generated queries |

**Read-only:** Yes

#### `expand_playlist_ym`
Expand a playlist with similar tracks from YM.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playlist_id` | int | Yes | -- | Playlist to expand |
| `target_count` | int | No | 100 | Target track count |
| `strategy` | str | No | `"ym"` | Discovery strategy |

#### `filter_by_feedback`
Filter tracks by like/dislike feedback.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playlist_id` | int | No | None | Filter within playlist |
| `liked_only` | bool | No | True | Only liked tracks |

**Read-only:** Yes

#### `import_tracks`
Import tracks from external platforms to local library.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_refs` | list[str] | Yes | -- | Track references (e.g., `["ym:12345"]`) |
| `playlist_id` | int | No | None | Add to playlist |
| `auto_analyze` | bool | No | False | Run audio analysis after import |

#### `download_tracks`
Download MP3 files from YM to local library.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_refs` | list[str] | Yes | -- | Track references |
| `target_dir` | str | No | None | Custom download directory |
| `skip_existing` | bool | No | True | Skip already downloaded |

**Note:** Automatically creates `DjLibraryItem` records. For large batches, split into groups of 5 to avoid UI timeouts.

---

### Curation (5 tools)

**Tag:** `curation` | **File:** `curation.py`

#### `classify_mood`
Classify tracks by 15 techno subgenres.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_ids` | list[int] | No | None | Specific tracks |
| `playlist_id` | int | No | None | All tracks in playlist |
| `reclassify` | bool | No | False | Overwrite existing classifications |

#### `audit_playlist`
Audit a playlist against techno quality criteria.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playlist_id` | int | No | None | Playlist ID |
| `playlist_query` | str | No | None | Playlist name search |
| `check` | str | No | None | Specific check to run |
| `template` | str | No | None | Template for gap analysis |

**Read-only:** Yes

#### `review_set_quality`
Detailed quality review of a DJ set.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `version` | str | No | None | Version label |

**Read-only:** Yes

#### `distribute_to_subgenres`
Distribute tracks to 15 subgenre playlists.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source_playlist_id` | int | No | None | Source playlist |
| `mode` | str | No | `"clean_rebuild"` | Distribution mode |
| `sync_to_ym` | bool | No | False | Push to YM playlists |
| `dry_run` | bool | No | False | Preview only |

#### `get_library_stats`
Get library health and distribution statistics.

**Read-only:** Yes | No parameters

---

### Sync (2 tools)

**Tag:** `sync` | **File:** `sync.py`

#### `sync_playlist`
Bidirectional sync between local and platform playlists.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `playlist_id` | int | Yes | -- | Local playlist ID |
| `direction` | str | No | `"push"` | `push`, `pull`, `bidirectional` |
| `conflict_strategy` | str | No | `"local_wins"` | Conflict resolution |
| `dry_run` | bool | No | False | Preview only |

#### `push_set_to_ym`
Push a DJ set as a YM playlist.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `set_id` | int | Yes | -- | Set ID |
| `ym_playlist_name` | str | No | None | Custom YM playlist name |
| `mode` | str | No | `"create"` | `create` or `update` |

---

### Yandex Music API (6 tools)

**Tag:** `ym` | **File:** `ym.py`

#### `ym_search`
Search Yandex Music catalog.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | Yes | -- | Search query |
| `type` | str | No | `"tracks"` | `tracks`, `albums`, `artists`, `playlists`, `all` |
| `limit` | int | No | 20 | Max results |

**Read-only:** Yes

#### `ym_get_tracks`
Batch fetch tracks by YM IDs.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_ids` | list[str] | Yes | -- | YM track IDs (up to 100) |

**Read-only:** Yes

#### `ym_get_album`
Get album info with optional track listing.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `album_id` | str | Yes | -- | YM album ID |
| `include_tracks` | bool | No | False | Include track list |

**Read-only:** Yes

#### `ym_artist_tracks`
Get an artist's tracks (paginated).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `artist_id` | str | Yes | -- | YM artist ID (string!) |
| `page` | int | No | 0 | Page number |
| `sort_by` | str | No | `"date"` | Sort order |

**Read-only:** Yes

#### `ym_playlists`
Manage YM playlists (consolidated tool with `action` parameter).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `get`, `list`, `create`, `rename`, `delete`, `add_tracks`, `remove_tracks` |

**Read-only:** Varies by action

#### `ym_likes`
Manage YM likes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | str | Yes | -- | `get_liked`, `add`, `remove` |
| `track_ids` | list[str] | No | None | Tracks to like/unlike |

**Read-only:** Varies by action

---

## Hidden Tools (Explicit Unlock Required)

### Audio Analysis (3 tools)

**Tag:** `audio` | **File:** `audio.py`

#### `analyze_track`
Run audio analysis pipeline on a track.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_id` | int | No | None | Track ID |
| `track_query` | str | No | None | Track name search |
| `analyzers` | list[str] | No | all | Specific analyzers to run |
| `force` | bool | No | False | Reanalyze even if features exist |

**Timeout:** 120s | Requires audio file (DjLibraryItem)

#### `analyze_batch`
Batch audio analysis.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_ids` | list[int] | No | None | Specific tracks |
| `playlist_id` | int | No | None | All tracks in playlist |
| `analyzers` | list[str] | No | all | Specific analyzers |
| `priority` | str | No | `"normal"` | Processing priority |

**Timeout:** 600s

#### `separate_stems`
Separate audio stems (vocals, drums, bass, other).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `track_id` | int | No | None | Track ID |
| `track_query` | str | No | None | Track name search |
| `stems` | list[str] | No | all | Specific stems |

**Timeout:** 300s | Requires `[stems]` extra (demucs + torch)

---

### Atomic Tools (4 tools)

**Tag:** `atomic` | **File:** `audio_atomic.py`

Low-level building blocks used by composite tools. Not intended for direct use.

| Tool | Parameters | Read-Only | Description |
|------|-----------|-----------|-------------|
| `analyze_one_track` | `track_id` | No | Analyze single track |
| `classify_one_track` | `track_id` | No | Classify single track mood |
| `gate_one_track` | `track_id` | Yes | Check techno quality gate |
| `get_similar_one_track` | `track_id`, `limit?` | Yes | Find similar for one track |

---

## Summary Table

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

## Related Pages

- **[Architecture](Architecture)** -- How tools are discovered and injected
- **[Audio Analysis Pipeline](Audio-Analysis-Pipeline)** -- Details on audio tools
- **[Transition Scoring](Transition-Scoring)** -- How `score_transitions` works
- **[DJ Set Generation](DJ-Set-Generation)** -- How `build_set` works
- **[Yandex Music Integration](Yandex-Music-Integration)** -- How YM tools work

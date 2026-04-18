# MCP Tools Inventory — Baseline (Phase 0)

> Snapshot для рефакторинга `app/mcp/tools/`. Дата: 2026-04-06.
> Полный план: `docs/reports/mcp-tools-refactor-plan-2026-04-06.md`.

## Итого

- **17 файлов** в `app/mcp/tools/` (включая `_helpers.py`, `sampling_models.py`)
- **2345 LOC**
- **50 `@tool`** функций
- **1 дубликат** (`quick_set_review` — BUG-017)

## Распределение по файлам

| Файл | LOC | Tools | Tag | Примечание |
|---|---:|---:|---|---|
| `_helpers.py` | 87 | — | — | 3 разных entity-резолвера, удаляется в Phase 3 |
| `admin.py` | 63 | 2 | admin | |
| `audio.py` | 236 | 3 | audio | hidden, tiered pipeline fallback |
| `audio_atomic.py` | 122 | 4 | atomic | hidden, low-level |
| `crud.py` | 60 | 3 | core | Set CRUD (странное имя: только Set) |
| `curation.py` | 153 | 5 | curation | **дубликат `quick_set_review`** (BUG-017) |
| `delivery.py` | 243 | 2 | delivery | pipeline orchestration в одном тулзе |
| `discovery.py` | 219 | 3 | discovery | inline Pydantic `SearchQueries`:101 |
| `import_download.py` | 104 | 2 | discovery | композитное имя |
| `playlists.py` | 146 | 3 | core | |
| `reasoning.py` | 86 | 5 | sets | **дубликат `quick_set_review`** (BUG-017) |
| `sampling_models.py` | 23 | — | — | Pydantic-only; удаляется в Phase 1 |
| `search.py` | 69 | 2 | core | возвращает `dict[str, Any]` вместо `PaginatedResponse` |
| `sets.py` | 163 | 4 | sets | |
| `sync.py` | 59 | 2 | sync | |
| `tracks.py` | 173 | 4 | core | |
| `ym.py` | 339 | 6 | ym | **крупнейший**, action-dispatched if/elif |

## Все 50 tools

| # | Tool | Файл | Tag | ReadOnly | Timeout | Task |
|---:|---|---|---|---|---|---|
| 1 | `unlock_tools` | admin.py | admin | False | – | – |
| 2 | `list_platforms` | admin.py | admin | True | – | – |
| 3 | `analyze_track` | audio.py | audio | — | 600 | – |
| 4 | `analyze_batch` | audio.py | audio | — | 600 | ✓ |
| 5 | `separate_stems` | audio.py | audio | — | 600 | – |
| 6 | `analyze_one_track` | audio_atomic.py | atomic | False | 600 | – |
| 7 | `classify_one_track` | audio_atomic.py | atomic | False | – | – |
| 8 | `gate_one_track` | audio_atomic.py | atomic | True | – | – |
| 9 | `get_similar_one_track` | audio_atomic.py | atomic | True | – | – |
| 10 | `list_sets` | crud.py | core | True | – | – |
| 11 | `get_set` | crud.py | core | True | – | – |
| 12 | `manage_set` | crud.py | core | False | – | – |
| 13 | `classify_mood` | curation.py | curation | False | 600 | ✓ |
| 14 | `audit_playlist` | curation.py | curation | True | 600 | ✓ |
| 15 | `quick_set_review` ⚠ | curation.py | curation | True | – | – |
| 16 | `distribute_to_subgenres` | curation.py | curation | False | – | – |
| 17 | `get_library_stats` | curation.py | curation | True | – | – |
| 18 | `deliver_set` | delivery.py | delivery | False | 600 | ✓ |
| 19 | `export_set` | delivery.py | delivery | False | – | – |
| 20 | `find_similar_tracks` | discovery.py | discovery | True | – | – |
| 21 | `filter_by_feedback` | discovery.py | discovery | True | – | – |
| 22 | `expand_playlist_ym` | discovery.py | discovery | False | 600 | ✓ |
| 23 | `import_tracks` | import_download.py | discovery | False | – | – |
| 24 | `download_tracks` | import_download.py | discovery | False | 600 | ✓ |
| 25 | `list_playlists` | playlists.py | core | True | – | – |
| 26 | `get_playlist` | playlists.py | core | True | – | – |
| 27 | `manage_playlist` | playlists.py | core | False | – | – |
| 28 | `suggest_next_track` | reasoning.py | sets | True | – | – |
| 29 | `explain_transition` | reasoning.py | sets | True | – | – |
| 30 | `find_replacement` | reasoning.py | sets | True | – | – |
| 31 | `compare_set_versions` | reasoning.py | sets | True | – | – |
| 32 | `quick_set_review` ⚠ | reasoning.py | sets | True | – | – |
| 33 | `search` | search.py | core | True | – | – |
| 34 | `filter_tracks` | search.py | core | True | – | – |
| 35 | `build_set` | sets.py | sets | False | 600 | ✓ |
| 36 | `rebuild_set` | sets.py | sets | False | 600 | ✓ |
| 37 | `score_transitions` | sets.py | sets | False | – | – |
| 38 | `get_set_cheat_sheet` | sets.py | sets | True | – | – |
| 39 | `sync_playlist` | sync.py | sync | False | – | – |
| 40 | `push_set_to_ym` | sync.py | sync | False | – | – |
| 41 | `list_tracks` | tracks.py | core | True | – | – |
| 42 | `get_track` | tracks.py | core | True | – | – |
| 43 | `manage_tracks` | tracks.py | core | False | – | – |
| 44 | `get_track_features` | tracks.py | core | True | – | – |
| 45 | `ym_search` | ym.py | ym | True | – | – |
| 46 | `ym_get_tracks` | ym.py | ym | True | – | – |
| 47 | `ym_get_album` | ym.py | ym | True | – | – |
| 48 | `ym_artist_tracks` | ym.py | ym | True | – | – |
| 49 | `ym_playlists` | ym.py | ym | False | – | – |
| 50 | `ym_likes` | ym.py | ym | False | – | – |

⚠ = дубликат имени (BUG-017).

## Матрица tag × writability

| Tag | ReadOnly | Write | Total |
|---|---:|---:|---:|
| core | 9 | 3 | 12 |
| sets | 6 | 2 | 8 |
| ym | 4 | 2 | 6 |
| curation | 2 | 3 | 5 |
| discovery | 2 | 3 | 5 |
| atomic | 2 | 2 | 4 |
| audio | — | 3 | 3 |
| admin | 1 | 1 | 2 |
| delivery | — | 2 | 2 |
| sync | — | 2 | 2 |
| **Σ** | **26** | **23** | **49 (+1 дубль)** |

## Целевое маппинг (до → после)

| Старый файл | → | Новое расположение |
|---|---|---|
| `_helpers.py` | → | `_shared/{resolvers,pagination,context}.py` (удаляется) |
| `sampling_models.py` | → | `schemas/sampling.py` (удаляется) |
| `tracks.py` | → | `catalog/tracks.py` + `management/tracks.py` |
| `playlists.py` | → | `catalog/playlists.py` + `management/playlists.py` |
| `crud.py` | → | `catalog/sets.py` + `management/sets.py` |
| `search.py` | → | `catalog/search.py` |
| `sets.py` | → | `setbuilder/build.py` + `setbuilder/score.py` |
| `reasoning.py` | → | `setbuilder/reason.py` |
| `curation.py` | → | `curation/{classify,audit,distribute,stats}.py` |
| `discovery.py` | → | `ingestion/discover.py` |
| `import_download.py` | → | `ingestion/import_.py` + `ingestion/download.py` |
| `delivery.py` | → | `delivery/deliver.py` + `delivery/export.py` |
| `sync.py` | → | `sync/playlist.py` + `sync/dj_set.py` |
| `ym.py` | → | `yandex/{search,tracks,albums,artists,playlists,likes}.py` |
| `audio.py` | → | `audio/{analyze,stems}.py` |
| `audio_atomic.py` | → | `atomic/audio.py` |
| `admin.py` | → | `admin/control.py` |

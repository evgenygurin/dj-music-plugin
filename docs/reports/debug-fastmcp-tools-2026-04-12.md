# Debug FastMCP Tools Report

> Дата: 2026-04-12
> Метод: in-memory FastMCP Client + SQLite, все tools вызваны с минимальными аргументами
> Цель: полная проверка каждого MCP инструмента при вызове из Claude Code (MCP клиент)

## Сводка (после исправлений)

| Метрика | До | После |
|---------|-----|-------|
| Tools зарегистрировано на сервере | 65 | **85** |
| OK (отработали корректно) | 21 | **39** |
| NotFound (ожидаемые, пустая БД) | 14 | **38** |
| InvalidParams (ожидаемые validation) | 0 | **4** |
| Internal errors (реальные баги) | 3 | **0** |
| MISSING (hidden by design: audio+atomic) | 27 | **7** |
| Metadata warnings | 3 | **0** |

---

## Исправления

### FIX 1: unlock_tools теперь реально работает

**Файлы:** `app/controllers/tools/admin.py`, `app/bootstrap/visibility.py`

**Было:** `unlock_tools` вызывал `ctx.enable_components(tags=...)` — session-level visibility rule, не триггерит `tools/list_changed` notification. Клиент не перезапрашивал tool list → 27 tools оставались невидимы.

**Стало:** `unlock_tools` вызывает `ctx.fastmcp.enable(tags=...)` — server-level enable, который триггерит `notifications/tools/list_changed`. Клиент автоматически перезапрашивает tool list. Все 7 disabled categories (delivery, discovery, curation, sync, ym, audio, atomic) реально разблокируются.

**Visibility policy** оставлена без изменений: все 7 категорий скрыты при старте для экономии контекста (~5K vs ~9K tokens).

### FIX 2: FK IntegrityError → NotFoundError

**Файлы:**
- `app/db/repositories/track_feedback.py` — добавлена `_ensure_track_exists()` перед INSERT
- `app/db/repositories/transition_history.py` — добавлена `ensure_tracks_exist()` (batch check)
- `app/services/transition_history.py` — вызов `ensure_tracks_exist` перед `log()`

**Было:** `ban_track`, `like_track`, `log_transition` при вызове с несуществующим track_id прокидывали `IntegrityError: FK constraint` как Internal error.

**Стало:** Чистый `NotFoundError("Track", id)` → MCP error code `-32001 Not found`.

### FIX 3: ym_get_album None guard

**Файл:** `app/controllers/tools/yandex/albums.py`

**Было:** Если `ym.get_album()` возвращает `None` (мок или нерабочий endpoint), код падал с `AttributeError: 'NoneType'` → Internal error.

**Стало:** Проверка `if album is None: raise NotFoundError(...)`.

### FIX 4: Tool descriptions сокращены

| Tool | Было | Стало |
|------|------|-------|
| `watch_decks` | 319 chars | 96 chars |
| `create_scoring_profile` | 409 chars | 95 chars |
| `get_set_templates` | 481 chars | 101 chars |

### FIX 5: test_server_builder.py

Тест ожидал `BM25SearchTransform` в transforms (давно удалён). Обновлён на `ResourcesAsTools` + `PromptsAsTools` + visibility check для `audio`+`atomic`.

### FIX 6: Acceptance tests для audio tools

`test_analysis_flow.py` и `test_download_flow.py` — добавлен `unlock_tools(action="unlock", category="audio")` перед вызовом `analyze_track`.

---

## Оставшиеся 7 MISSING tools (by design)

Hidden categories (audio, atomic) — тяжёлые/опасные tools, требуют `unlock_tools`:

| Category | Tools |
|----------|-------|
| audio | `analyze_track`, `analyze_batch`, `separate_stems` |
| atomic | `analyze_one_track`, `classify_one_track`, `gate_one_track`, `get_similar_one_track` |

---

## Финальный чеклист: 88 tools

### OK — 39 tools

`classify_mood`, `create_scoring_profile`, `download_tracks`, `expand_playlist_ym`,
`filter_by_feedback`, `filter_tracks`, `get_affinity_recommendations`, `get_banned_tracks`,
`get_best_pairs`, `get_energy_trend`, `get_library_stats`, `get_liked_tracks`,
`get_scoring_weights`, `get_session_arc`, `get_set_templates`, `get_track_affinity`,
`get_track_feedback`, `get_transition_history`, `import_tracks`, `like_track`,
`list_platforms`, `list_playlists`, `list_scoring_profiles`, `list_sets`, `list_tracks`,
`manage_playlist`, `manage_set`, `manage_tracks`, `rate_track`, `refresh_affinity`,
`run_tool`, `search`, `suggest_energy_direction`, `unlock_tools`,
`ym_artist_tracks`, `ym_get_tracks`, `ym_likes`, `ym_playlists`, `ym_search`

### NotFound — 38 tools (ожидаемо, пустая БД)

Все корректно обёрнуты в MCP NotFound error.

### InvalidParams — 4 tools (ожидаемо)

`compare_set_versions`, `distribute_to_subgenres`, `push_set_to_ym`, `sync_playlist` — validation errors на пустых данных.

### MISSING — 7 tools (hidden by design)

Audio + Atomic categories.

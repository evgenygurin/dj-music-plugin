# Debug FastMCP Tools Report

> Дата: 2026-04-12
> Метод: in-memory FastMCP Client + SQLite, все tools вызваны с минимальными аргументами
> Цель: полная проверка каждого MCP инструмента при вызове из Claude Code (MCP клиент)

## Сводка

| Метрика | Значение |
|---------|----------|
| Tools зарегистрировано на сервере | 65 |
| Tools ожидалось по tool-catalog.md | 88 (50 tools + decks/mixer/memory/etc) |
| Tools протестировано | 88 |
| OK (отработали корректно) | 21 |
| Tool errors (ожидаемые: NotFound на пустой БД) | 14 |
| Validation errors (несоответствие параметров) | 20 |
| Internal errors (реальные баги) | 3 |
| MISSING (не видны клиенту после unlock) | 27 |
| Extra (автогенерированные transforms) | 4 |

---

## CRITICAL: 27 tools невидимы для клиента

### Проблема

После вызова `unlock_tools(action="unlock", category="all")` клиент по-прежнему видит только 65 tools. 27 tools из disabled-at-startup категорий **не появляются** в `client.list_tools()`.

### Затронутые категории и tools

| Категория | Tools |
|-----------|-------|
| **delivery** | `deliver_set`, `export_set` |
| **discovery** | `find_similar_tracks`, `expand_playlist_ym`, `filter_by_feedback`, `import_tracks`, `download_tracks` |
| **curation** | `classify_mood`, `audit_playlist`, `review_set_quality`, `distribute_to_subgenres`, `get_library_stats` |
| **sync** | `sync_playlist`, `push_set_to_ym` |
| **ym** | `ym_search`, `ym_get_tracks`, `ym_artist_tracks`, `ym_get_album`, `ym_playlists`, `ym_likes` |
| **audio** | `analyze_track`, `analyze_batch`, `separate_stems` |
| **atomic** | `analyze_one_track`, `classify_one_track`, `gate_one_track`, `get_similar_one_track` |

### Причина

`app/bootstrap/visibility.py` вызывает `mcp.disable(tags=_DISABLED_AT_STARTUP)` на уровне сервера при старте. `unlock_tools` использует `ctx.enable_components(tags=tags)` — это добавляет session-level visibility rule, но FastMCP `Client.list_tools()` **не перезапрашивает** server tool list после session rule change. Клиент кеширует initial tool list.

В документации `docs/tool-catalog.md` и `.claude/rules/tools.md` написано:

> Hidden tools: after `unlock_tools`, Claude Code doesn't reload tool list — hidden tools (audio, atomic) only accessible via script `Client(mcp)`

Это **подтверждённое ограничение**, но распространяется не только на audio/atomic, а на ВСЕ 7 disabled категорий (27 tools).

### Файлы

- `app/bootstrap/visibility.py:28-30` — `mcp.disable(tags=...)`
- `app/controllers/tools/admin.py:117-118` — `ctx.enable_components(tags=tags)`

### Рекомендация

Для Claude Code (MCP клиент, stdio transport) все 27 tools в disabled категориях **полностью недоступны**. Варианты:
1. **Не отключать** extended tools при старте (только audio/atomic скрыть)
2. Реализовать `tools/list_changed` notification после `enable_components` (FastMCP v3.x пока не поддерживает)
3. Явно документировать, что Claude Code видит только 61 tool (core+sets+admin+decks+mixer+memory)

---

## BUG: FK Integrity без валидации (3 tools)

### Проблема

Tools не проверяют существование referenced entities перед INSERT. При вызове с несуществующим track_id SQLite/PostgreSQL бросает `IntegrityError: FOREIGN KEY constraint failed`, который **не обёрнут** в domain error и прорывается как `Internal error`.

### Затронутые tools

| Tool | Параметр | Ожидаемое поведение | Фактическое |
|------|----------|---------------------|-------------|
| `ban_track` | `track_id=1` | `NotFoundError("Track", 1)` | `IntegrityError: FK constraint` → `Internal error` |
| `like_track` | `track_id=1` | `NotFoundError("Track", 1)` | `IntegrityError: FK constraint` → `Internal error` |
| `log_transition` | `from_track_id=1, to_track_id=2` | `NotFoundError` | `IntegrityError: FK constraint` → `Internal error` |

### Файлы

- `app/controllers/tools/track_feedback.py` — `like_track`, `ban_track` напрямую вызывают `repo.add()` без проверки
- `app/controllers/tools/transition_history.py` — `log_transition` то же

### Рекомендация

Добавить проверку существования track_id перед INSERT или обернуть `IntegrityError` в `NotFoundError` на уровне репозитория.

---

## WARNING: tool-catalog.md не соответствует реальным сигнатурам

### Несовпадения имён параметров

Документация `docs/tool-catalog.md` указывает одни имена параметров, а реальный код использует другие. Claude Code отправляет параметры по документации — получает validation error.

| Tool | В документации | В коде | Файл |
|------|----------------|--------|------|
| `deck_*` (все 8) | `deck: int` | `deck_id: int` | `app/controllers/tools/decks.py` |
| `deck_set_gain` | `gain_db: float` | `gain: float` | `decks.py` |
| `deck_load` | (нет `duration_ms`) | `duration_ms: int` (required!) | `decks.py` |
| `mixer_crossfader` | `position: float` | `target: float` | `mixer.py` |
| `mixer_channel_gain` | `channel: int, gain_db: float` | `deck_id: int, gain: float` | `mixer.py` |
| `set_eq` | `gain_db: float` | `gain: float` | `mixer.py` |
| `set_filter` | `type: str, frequency: float` | `cutoff_hz: float` (нет `type`) | `mixer.py` |
| `kill_eq` | `deck: int` | `deck_id: int` | `mixer.py` |
| `reset_eq` | `deck: int` | `deck_id: int` | `mixer.py` |
| `run_tool` | `tool_name: str, arguments: dict` | `name: str, arguments: dict\|str\|None` | `run_tool.py` |
| `update_reaction` | `transition_id: int, reaction: str` | `entry_id: int, reaction: str` | `transition_history.py` |
| `get_best_pairs` | (без обязательных) | `track_id: int` (required!) | `transition_history.py` |
| `get_track_affinity` | `track_id: int` | `track_a_id: int, track_b_id: int` | `track_affinity.py` |
| `refresh_affinity` | `track_id: int` | (нет параметров, только Depends) | `track_affinity.py` |
| `get_energy_trend` | `set_id: int` | `last_n: int = 10` (нет `set_id`!) | `adaptive_arc.py` |
| `suggest_energy_direction` | `set_id: int` | `last_n: int = 10` (нет `set_id`!) | `adaptive_arc.py` |

### Файлы

- `docs/tool-catalog.md` — устаревшая документация

### Рекомендация

Обновить `docs/tool-catalog.md` для соответствия реальным сигнатурам. Либо автогенерировать каталог из `client.list_tools()` inputSchema.

---

## WARNING: Descriptions длиннее 300 символов (3 tools)

Claude Code отображает description в UI. Длинные описания снижают usability.

| Tool | Длина | Файл |
|------|-------|------|
| `watch_decks` | 319 chars | `monitoring.py` |
| `create_scoring_profile` | 409 chars | `scoring_profile.py` |
| `get_set_templates` | 481 chars | `sets_meta.py` |

### Рекомендация

Сократить до ≤50 слов (правило из `.claude/rules/tools.md`). Детали — в parameter descriptions.

---

## INFO: Ожидаемые ошибки на пустой БД (14 tools)

Эти tools корректно возвращают `NotFoundError` или `ValidationError` при вызове на пустой базе. **Это не баги.**

| Tool | Ошибка | Причина |
|------|--------|---------|
| `analyze_set_narrative` | NotFoundError: DjSet not found: 1 | Нет сета |
| `build_set` | NotFoundError: Playlist not found | Нет плейлиста |
| `compare_set_versions` | ValidationError | Нет сета для сравнения |
| `explain_transition` | NotFoundError: Track not found | Нет треков |
| `find_replacement` | NotFoundError: DjSet not found | Нет сета |
| `get_playlist` | NotFoundError | Нет плейлиста |
| `get_set` | NotFoundError | Нет сета |
| `get_set_cheat_sheet` | NotFoundError | Нет сета |
| `get_track` | NotFoundError | Нет трека |
| `get_track_features` | NotFoundError | Нет трека |
| `quick_set_review` | NotFoundError | Нет сета |
| `rebuild_set` | NotFoundError | Нет сета |
| `score_transitions` | NotFoundError | Нет сета |
| `suggest_next_track` | NotFoundError | Нет сета |

Domain error mapping (`@map_domain_errors`) работает корректно — все эти ошибки обёрнуты в правильные MCP error codes.

---

## INFO: Engine-dependent tools (ожидаемо)

Deck/mixer tools зависят от `audio_lifespan` (engines). В тестовом окружении без sounddevice они не доступны. При правильных параметрах:

| Tool | Проблема в тесте | В production |
|------|-------------------|-------------|
| `mixer_state` | `_get_mixer(ctx)` fails — no MixerEngine in lifespan | OK если audio lifespan работает |
| `watch_decks` | Аналогично — no DeckEngine | OK |
| `deck_*` | Validation error от неправильных param names в тесте | OK если deck_id вместо deck |

---

## INFO: Extra tools (transforms)

4 tools появились из `PromptsAsTools` и `ResourcesAsTools` transforms:

- `get_prompt` — proxy для prompts
- `list_prompts` — список workflow prompts
- `list_resources` — список MCP resources
- `read_resource` — чтение resource по URI

Это **нормально** — transforms конвертируют prompts и resources в callable tools.

---

## Полный чеклист по tools

### OK (21 tools) — работают корректно

| # | Tool | Время |
|---|------|-------|
| 1 | `create_scoring_profile` | 0.01s |
| 2 | `filter_tracks` | 0.02s |
| 3 | `get_affinity_recommendations` | 0.01s |
| 4 | `get_banned_tracks` | 0.00s |
| 5 | `get_liked_tracks` | 0.00s |
| 6 | `get_scoring_weights` | 0.00s |
| 7 | `get_session_arc` | 0.01s |
| 8 | `get_set_templates` | 0.00s |
| 9 | `get_track_feedback` | 0.00s |
| 10 | `get_transition_history` | 0.01s |
| 11 | `list_platforms` | 0.00s |
| 12 | `list_playlists` | 0.01s |
| 13 | `list_scoring_profiles` | 0.00s |
| 14 | `list_sets` | 0.01s |
| 15 | `list_tracks` | 0.01s |
| 16 | `manage_playlist` | 0.00s |
| 17 | `manage_set` | 0.00s |
| 18 | `manage_tracks` | 0.02s |
| 19 | `rate_track` | 0.01s |
| 20 | `search` | 0.00s |
| 21 | `unlock_tools` | 0.00s |

### MISSING (27 tools) — не видны клиенту

Все из disabled categories (delivery, discovery, curation, sync, ym, audio, atomic). См. секцию "CRITICAL" выше.

### NotFound / Expected errors (14 tools)

Корректная обработка ошибок на пустой БД. Не баги.

### Param name mismatches (20 tools)

tools/catalog.md документирует неправильные param names. См. секцию "WARNING" выше.

### Real bugs (3 tools)

`ban_track`, `like_track`, `log_transition` — FK constraint без валидации. См. секцию "BUG" выше.

---

## Действия

| # | Приоритет | Действие | Файлы |
|---|-----------|----------|-------|
| 1 | CRITICAL | Решить visibility: либо не отключать extended tools, либо документировать ограничение | `app/bootstrap/visibility.py`, `CLAUDE.md` |
| 2 | HIGH | Добавить проверку track existence в feedback/history tools | `track_feedback.py`, `transition_history.py` |
| 3 | MEDIUM | Обновить tool-catalog.md — param names не соответствуют коду | `docs/tool-catalog.md` |
| 4 | LOW | Сократить descriptions > 300 chars | `monitoring.py`, `scoring_profile.py`, `sets_meta.py` |
| 5 | LOW | Обновить тест `test_server_builder.py` — ожидает BM25SearchTransform | `tests/test_server_builder.py` |

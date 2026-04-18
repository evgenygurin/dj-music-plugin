# Глобальный рефакторинг `app/mcp/tools/` — план

> **Статус:** черновик (Phase 0 завершена).
> **Ветка:** `claude/plan-mcp-refactor-jfwzN`
> **Дата:** 2026-04-06

## 0. TL;DR

`app/mcp/tools/` вырос до 17 файлов / 2345 LOC / 50 `@tool`. Структура плоская, именование несогласованно, есть скрытые баги (дубликаты), кросс-функциональные паттерны продублированы. Цель — переделать MCP-слой в тонкий, многоуровневый adapter поверх сервисов с чёткими контрактами, применением паттернов GoF и устранением хардкода.

**Не меняем:** публичные имена tools, их сигнатуры, `structuredContent`-контракты, tag'и видимости (только выносим в константы), DI через `Depends()`, слой `services/`/`repositories/`.

## 1. Ключевые находки (Phase 0)

### 1.1 Инвентарь (50 tools, 17 файлов, 2345 LOC)

Полная таблица — `docs/reports/tools-inventory-2026-04-06.md`.

### 1.2 Критические баги

| # | Баг | Место |
|---|---|---|
| **BUG-017** | `quick_set_review` определён **дважды** — в `curation.py:102` и `reasoning.py:80`. FileSystemProvider регистрирует по-последнему; одна реализация незаметно теряется. | fix в Phase 3 |
| BUG-018 | Lazy-imports внутри тел функций (`ensure_list`, `ensure_dict`, `AnalysisLevel`, `ExportFormat`, `is_icloud_stub`, `validate_id_or_query`, `settings`) — 12+ мест. Скрывают зависимости, ломают IDE-навигацию. | fix в Phase 2–3 |

### 1.3 Структурные проблемы

| # | Проблема | Симптом |
|---|---|---|
| P1 | Несогласованная группировка CRUD | Set CRUD в `crud.py` (tag=`core`), но Set building в `sets.py` (tag=`sets`). Track/Playlist CRUD в собственных файлах. Имя `crud.py` — ложный зонтик. |
| P2 | Три разных entity-резолвера | `_helpers.py:11-88`: `resolve_entity`, `resolve_track_id`, `validate_id_or_query` используются непоследовательно. |
| P3 | Магические строки | 22 варианта `tags={...}`, 6 литералов `timeout=600.0`, `task=True` разбросаны. Нет enum'а. |
| P4 | Pydantic-модели размазаны | `core/schemas.py` + `tools/sampling_models.py` + inline `class SearchQueries(BaseModel)` в `discovery.py:101`. |
| P5 | `dict[str, Any]`-ответы | `delivery.py`, `ym.py`, `sync.py`, `reasoning.py`, `search.py:63` возвращают сырые dict'ы → нет `structuredContent`-гарантии. |
| P6 | `if ctx: await ctx.info(...)` guard | Повторён в 6 файлах 30+ раз. |
| P7 | Дублирующий tiered-trigger | Одинаковый бойлерплейт `ensure_level()` в `curation.py`, `delivery.py`, `audio.py`. |
| P8 | Крупные файлы смешанных обязанностей | `ym.py` 339 LOC, `delivery.py` 243, `audio.py` 236, `curation.py` 153. |
| P9 | Action-dispatched tools через `if/elif` | `ym_playlists` (8 действий), `ym_likes` (3), `manage_*` — нет Command-pattern диспатча. |
| P10 | Композитные имена | `import_download.py`, `audio_atomic.py`, `sampling_models.py` — имя смешивает концепты / абстракции / домены. |

## 2. Принципы целевой архитектуры

1. **MCP tool = тонкий Adapter.** Парсит вход → резолвит ref'ы → делегирует в service → оборачивает в Pydantic. **Ноль** бизнес-логики, **ноль** lazy-imports, **ноль** ручных `if ctx:` guard'ов.
2. **Один файл — одна когезивная подгруппа**, мягкий лимит ≤150 LOC, ≤4 tools.
3. **Группировка по домену**, не по уровню видимости (видимость — через tag'и).
4. **Все магические значения** — в `_shared/taxonomy.py`.
5. **Все Pydantic response/input-модели** — в `app/mcp/schemas/`, домено-разделённые.
6. **Строгие контрактные границы между слоями** (проверяются `import-linter`).
7. **SOLID + KISS + DRY.** Никаких абстракций «на вырост», только под конкретные дубли.

## 3. Целевая структура

```text
app/mcp/tools/
├── __init__.py                 # package-mode (FSProvider импортирует как пакет)
│
├── _shared/                    # приватная инфраструктура tools-слоя
│   ├── __init__.py
│   ├── taxonomy.py             # ToolTag StrEnum, READ_ONLY/WRITE, ToolTimeout
│   ├── resolvers.py            # EntityResolver (Strategy): tracks|playlists|sets
│   ├── pagination.py           # PageBuilder — единая фабрика PaginatedResponse
│   ├── context.py              # ToolContext facade: log_info/progress/elicit (ctx=None guard)
│   ├── elicitation.py          # ElicitationGateway (Facade над safe_elicit)
│   ├── decorators.py           # @dj_tool(category, readonly, timeout) — Decorator
│   ├── dispatch.py             # ActionDispatcher[E, R] (Command registry)
│   └── errors.py               # DomainError → McpError (Adapter)
│
├── catalog/                    # read-only выборки + search (tag=core)
│   ├── tracks.py               # list_tracks, get_track, get_track_features
│   ├── playlists.py            # list_playlists, get_playlist
│   ├── sets.py                 # list_sets, get_set            (ex-crud.py)
│   └── search.py               # search, filter_tracks
│
├── management/                 # CUD мутации сущностей (tag=core, write)
│   ├── tracks.py               # manage_tracks
│   ├── playlists.py            # manage_playlist
│   └── sets.py                 # manage_set
│
├── setbuilder/                 # tag=sets
│   ├── build.py                # build_set, rebuild_set
│   ├── score.py                # score_transitions, get_set_cheat_sheet
│   └── reason.py               # suggest_next_track, explain_transition,
│                               # find_replacement, compare_set_versions, quick_set_review
│
├── curation/                   # tag=curation
│   ├── classify.py             # classify_mood
│   ├── audit.py                # audit_playlist, review_set_quality
│   ├── distribute.py           # distribute_to_subgenres
│   └── stats.py                # get_library_stats
│
├── ingestion/                  # tag=discovery (ex discovery.py + import_download.py)
│   ├── discover.py             # find_similar_tracks, expand_playlist_ym, filter_by_feedback
│   ├── import_.py              # import_tracks
│   └── download.py             # download_tracks
│
├── delivery/                   # tag=delivery
│   ├── deliver.py              # deliver_set (thin; делегирует в DeliveryOrchestrator)
│   └── export.py               # export_set
│
├── sync/                       # tag=sync
│   ├── playlist.py             # sync_playlist
│   └── dj_set.py               # push_set_to_ym
│
├── yandex/                     # tag=ym (ex ym.py, разбит по сущностям)
│   ├── search.py               # ym_search
│   ├── tracks.py               # ym_get_tracks
│   ├── albums.py               # ym_get_album
│   ├── artists.py              # ym_artist_tracks
│   ├── playlists.py            # ym_playlists (ActionDispatcher × 8)
│   └── likes.py                # ym_likes (ActionDispatcher × 3)
│
├── audio/                      # tag=audio (hidden-by-default)
│   ├── analyze.py              # analyze_track, analyze_batch
│   └── stems.py                # separate_stems
│
├── atomic/                     # tag=atomic (hidden, low-level building blocks)
│   └── audio.py                # analyze/classify/gate/get_similar _one_track
│
└── admin/
    └── control.py              # unlock_tools, list_platforms
```

### Pydantic schemas

```text
app/mcp/schemas/
├── __init__.py                 # re-exports
├── common.py                   # PaginatedResponse[T], EntityRef, ViewMode, StatusEnum
├── track.py                    # TrackBrief/Standard/Full, TrackFeaturesView
├── playlist.py                 # PlaylistSummary/Detail
├── set.py                      # SetSummary/Tracks/Transitions/Full
├── transition.py               # TransitionReport/Score
├── audio.py                    # AnalysisResult, MoodClassification
├── discovery.py                # SimilarTracksResult, ImportReport, SearchQueries (ex-inline)
├── delivery.py                 # DeliveryReport, DeliveryStage, ConflictReport
├── sync.py                     # SyncPlan, SyncReport
├── yandex.py                   # YM* (ex core/schemas.py::YMTrackSummary + ym.py inline)
└── sampling.py                 # LLM sampling payloads (ex tools/sampling_models.py)
```

## 4. Контракты слоёв

| Слой | Может импортировать | Запрещено |
|---|---|---|
| `tools/<domain>/*` | `tools/_shared`, `tools/schemas`, `mcp/dependencies`, `services/*`, `core/errors`, `core/constants` | ❌ `repositories/*`, ❌ `models/*`, ❌ `ym/client` напрямую, ❌ бизнес-логика, ❌ lazy-imports в телах |
| `tools/_shared` | `core/*`, `fastmcp` | ❌ `services/*`, ❌ `tools/<domain>/*` |
| `tools/schemas` | `core/constants`, `pydantic` | ❌ любой runtime-код, ❌ сервисы |
| `services/*` | `repositories/*`, `core/*`, `audio/*`, `ym/*` | ❌ `mcp/*`, ❌ `fastmcp` |
| `services/orchestrators/*` (новое) | `services/*` | — оркестрация pipeline'ов (`DeliveryOrchestrator`, `SetBuildOrchestrator`) |

**Проверка контрактов:** `import-linter` с конфигом в `pyproject.toml`, подключён в `make check`.

## 5. Применяемые паттерны GoF / современные практики

| Паттерн | Где | Почему |
|---|---|---|
| **Decorator** | `@dj_tool(category=ToolCategory.SETS, readonly=True, timeout=ToolTimeout.MEDIUM)` | Единая точка конфигурации tools; убирает 50 копий `@tool(tags={...}, annotations={...}, timeout=...)`. |
| **Facade** | `ToolContext` над FastMCP `Context`; `ElicitationGateway` над `safe_elicit` | Устраняет 30+ `if ctx: await ctx.info(...)` guard'ов, централизует elicitation. |
| **Adapter** | `errors.py` — `DomainError → McpError`; сам `@tool` = adapter MCP protocol ↔ service. | Один формат преобразования доменных ошибок. |
| **Strategy** | `EntityResolver` со стратегиями `ByNumericId / ByLocalRef / ByTextQuery` для tracks/playlists/sets | Вместо трёх разных `resolve_*` функций — один интерфейс. |
| **Command / Registry** | `ActionDispatcher[EnumT, ResultT]` для `ym_playlists`, `ym_likes`, `manage_*` | `@dispatcher.handler("create")` вместо `if action == "create": ... elif ...`. |
| **Template Method** | `PipelineOrchestrator` в `services/orchestrators/` для `deliver_set` / `build_set` | Фиксирует шаги (load → analyze → score → export → sync), subclasses переопределяют hooks. |
| **Builder** | `ToolResponseBuilder` для сложных composite-ответов (`deliver_set`, `audit_playlist`) | Управляемая сборка `structuredContent` + `meta` + warnings. |
| **DI** | `Depends()` (уже есть; пресекаем `Annotated[..., Depends(...)]` — не работает в FastMCP) | — |
| **Factory methods** | `TrackBrief.from_model(track)` на каждой схеме | Уже частично есть (`TrackFeatures.from_db`) — распространить. |

## 6. Устранение конкретных дубликатов и хардкода

| Проблема | Решение |
|---|---|
| 3 entity-резолвера | `EntityResolver` (Strategy) в `_shared/resolvers.py`, один API для всех доменов. |
| `if ctx: await ctx.info(...)` ×30+ | `ToolContext.info(msg)` — внутри guard; tool пишет без if. |
| 12+ lazy-imports (`ensure_list` в теле функции) | Поднять в module-level; circular imports устраняются выносом парсинга в `_shared/parsing.py` или `core/parsing.py` (уже там). |
| Inline `class SearchQueries(BaseModel)` в `discovery.py:101` | Перенести в `mcp/schemas/sampling.py`. |
| `tools/sampling_models.py` | Перенести в `mcp/schemas/sampling.py`, файл удалить. |
| `_helpers.py` | Разложить по `_shared/{resolvers,pagination,...}.py`, файл удалить. |
| Дубликат `quick_set_review` (BUG-017) | Оставить версию в `setbuilder/reason.py`; из `curation.py` удалить. |
| Хардкод tag'ов / timeout'ов / annotations | `ToolCategory: StrEnum`, `READ_ONLY/WRITE: Final[dict]`, `ToolTimeout: IntEnum` — в `_shared/taxonomy.py` (или `core/constants.py` если понадобится за пределами tools). |
| Повтор `tiered_pipeline.ensure_level()` | `TieredAnalysisTrigger` helper service или метод `AudioService.ensure_level()`. |
| YM `ensure_list(batched_response)` ×3 | `YandexResponseNormalizer` в `app/ym/client.py`. |

## 7. Поэтапная миграция (фазы = PR'ы)

Каждая фаза заканчивается зелёным `make check` (ruff, mypy, pytest) и отдельным коммитом.

| № | Фаза | Содержание | Риск |
|---|---|---|---|
| **0** | **Inventory** | Этот документ + `tools-inventory-2026-04-06.md`. ✅ сделано | — |
| 1 | Schemas | Создать `app/mcp/schemas/` package. Перенести модели из `core/schemas.py`, `tools/sampling_models.py`, inline `SearchQueries`. Обновить импорты. | low |
| 2 | `_shared/` foundation | `taxonomy.py`, `resolvers.py`, `pagination.py`, `context.py`, `elicitation.py`, `decorators.py`, `dispatch.py`, `errors.py` + тесты. Пока **без** переноса tools. | low |
| 3 | Catalog + Management | Перенести `tracks/playlists/crud/search` → `catalog/*` и `management/*`. Удалить `_helpers.py`. Применить `@dj_tool`, `EntityResolver`, `ToolContext`. **Fix BUG-017** (удалить дубль в `curation.py`). | med |
| 4 | Setbuilder | Разбить `sets.py` + `reasoning.py` → `setbuilder/{build,score,reason}.py`. | med |
| 5 | Curation | `curation.py` → 4 файла; вынести tiered-trigger в сервис. | med |
| 6 | Ingestion | `discovery.py` + `import_download.py` → `ingestion/*`. | med |
| 7 | Delivery orchestrator | Вынести тело `deliver_set` в `services/orchestrators/delivery_orchestrator.py` (Template Method). Tool уменьшается до ~50 LOC. | **high** |
| 8 | Yandex | `ym.py` (339 LOC) → `yandex/*` × 6 файлов. Применить `ActionDispatcher` для `ym_playlists`/`ym_likes`. | med |
| 9 | Audio + Atomic | `audio.py` → `audio/{analyze,stems}.py`; `audio_atomic.py` → `atomic/audio.py`. | low |
| 10 | Sync + Admin | Финальные мелочи. | low |
| 11 | Contracts | Подключить `import-linter` в `make check`. | low |
| 12 | Cleanup | Удалить устаревшие файлы; обновить `docs/architecture.md`, `docs/tool-catalog.md`, `CLAUDE.md` (пути). | low |

## 8. Метрики успеха

| Метрика | До | Цель |
|---|---:|---:|
| LOC в `app/mcp/tools/` | 2345 | ≤1400 |
| Средний LOC файла | 138 | ≤100 |
| Макс LOC файла | 339 (`ym.py`) | ≤150 |
| Lazy-imports в телах | 12+ | 0 |
| `if ctx:` guard'ов | 30+ | 0 |
| Entity-резолверов | 3 | 1 |
| Inline Pydantic в tool-файлах | 2 | 0 |
| `dict[str, Any]` возвратов | 6+ | 0 |
| Дубликатов `@tool` | 1 (BUG-017) | 0 |
| Контрактных нарушений `import-linter` | — | 0 |

## 9. Инструменты выполнения

| Задача | Инструмент |
|---|---|
| Поиск `@tool` и сигнатур | `rg` + Python AST (`ast-grep` если установлен) |
| Массовые переименования импортов | `fd -e py -x sed -i` (или `rg --files -0 \| xargs -0 sed`) |
| Контентный поиск | `rg` |
| Размер файлов | `wc -l` / `fd` |
| JSON-инвентарь | генератор на Python → `jq` для выборок |
| Валидация `pyproject.toml`/TOML | `tomlq` |
| Навигация по изменениям | `git diff \| fzf` (ручная ревизия) |
| Docs lookup | FastMCP `llms-full.txt`, Context7 MCP для SQLAlchemy/Pydantic |

## 10. Что НЕ трогаем

- Имена `@tool` функций — стабильный контракт для LLM-клиентов.
- Сигнатуры параметров (поправки типов допустимы только аддитивно).
- Слой `services/`/`repositories/`/`models/` — оставляем как есть, кроме новых `services/orchestrators/`.
- Middleware pipeline в `server.py` — без изменений.
- Tag'и категорий (`core`/`sets`/...) — только формализуются через enum.
- DB схема и миграции.
- Panel / REST API — их код не затрагивается.

---

**Следующий шаг:** после утверждения плана — Phase 1 (`app/mcp/schemas/` package).

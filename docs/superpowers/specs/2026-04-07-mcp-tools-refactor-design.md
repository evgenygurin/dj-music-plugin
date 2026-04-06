# MCP Tools Layer Refactor — Design

> **Status**: Draft for review
> **Date**: 2026-04-07
> **Scope**: `app/mcp/tools/` + parallel sweep of 4 god-files in `app/services/`
> **Out of scope**: Tool Search transform (separate future design), changes to `app/mcp/resources/`, `app/mcp/prompts/`, `app/audio/`, `app/domain/`, `app/repositories/`, panel, REST API

---

## 1. Цель и мотивация

`app/mcp/tools/` накопил структурный долг: 19 файлов в плоской директории, ~40 tools, 2345 строк. Дублирующиеся утилиты, длинные `if/elif`-цепи, смешанные ответственности, отсутствие группировки по доменам. В parallel — 4 god-файла в `app/services/` (>300 строк каждый), которые делают tools-рефакторинг половинчатым: пока сервисы остаются клубками ответственностей, tools будут оставаться обёртками над клубками.

**Цель**: привести `app/mcp/tools/` (и затронутые сервисы) к канонической многослойной архитектуре с явными границами ответственности, без god-файлов, без дублирования, с применением подходящих GoF-паттернов там и только там, где они действительно упрощают код.

**Не цель**: переписать бизнес-логику, поменять контракты MCP-tools (имена, параметры, return-схемы остаются стабильными для panel и MCP-клиентов), ввести новые фичи.

**Принципы дизайна**:
- **KISS** — никаких абстракций "на вырост". Паттерн вводится только если убирает реальное дублирование/нарушение SOLID в текущем коде.
- **DRY** — общие утилиты в `_shared/`, единственный источник истины для каждой повторяющейся операции.
- **SOLID** — SRP (один файл = одна тема), OCP (новые actions = добавление, не правка), DIP (tools зависят от service-интерфейсов через `Depends()`).
- **Vertical Slice** — связность по домену важнее связности по типу.
- **Stable contracts** — tool names, schemas и поведение не меняются. Это чисто структурный refactor.

---

## 2. Текущее состояние (краткий аудит)

### 2.1 Метрики
- 19 файлов в `app/mcp/tools/`, ~40 `@tool` функций, **2345 строк**
- Самый большой tool-файл: `ym.py` — **339 строк**, 6 tools
- Самые большие service-файлы (god-files):
  - `app/services/set/facade.py` — 360
  - `app/services/import_service.py` — 342
  - `app/services/discovery_service.py` — 341
  - `app/services/metadata_service.py` — 315
  - `app/services/sync_service.py` — 310
- `_helpers.py` — 87 строк, 3 функции; используется неконсистентно
- `app/mcp/tools/CLAUDE.md` — пустой (43 байта)

### 2.2 Подтверждённые проблемы

| # | Проблема | Локация | Тип |
|---|---|---|---|
| P1 | Flat-структура из 19 файлов без группировки | `app/mcp/tools/*` | Структурная |
| P2 | God-tool: `ym.py` (339 строк, 6 tools, разнородные операции YM) | `tools/ym.py` | SRP violation |
| P3 | God-action: `ym_playlists` — ~70-строчный `if/elif` на 8 actions | `tools/ym.py` | OCP violation |
| P4 | God-action: `manage_playlist` — 6 actions через `if/elif` | `tools/playlists.py` | OCP violation |
| P5 | God-action: `manage_tracks` — 4 actions через `if/elif` | `tools/tracks.py` | OCP violation |
| P6 | Дублирование `validate_id_or_query` — переопределяется in-place вместо импорта из `_helpers` | `tools/audio.py:221`, `tools/curation.py:82` | DRY violation |
| P7 | Дублирование batch artist-name fetch | `tools/playlists.py:65`, `tools/tracks.py:49` | DRY violation |
| P8 | Ad-hoc сборка `PaginatedResponse[T]` в каждом list-tool | весь `tools/*` | DRY violation |
| P9 | Ad-hoc маппинг исключений в `ToolError` в каждом tool | весь `tools/*` | DRY violation |
| P10 | Magic strings для lifespan-объектов: `ctx.lifespan_context["ym_client"]` | `dependencies.py` | Type-safety |
| P11 | God-files в service-слое (4 файла >300 строк) | `app/services/{import,discovery,metadata,sync}_service.py` | SRP violation |
| P12 | Пустой `CLAUDE.md` для tools-слоя | `app/mcp/tools/CLAUDE.md` | Документация |

### 2.3 Что сохраняем (хорошие паттерны)

- 3-слойная архитектура `Tool → Service → Repository` без cross-layer leaks
- Standalone `@tool` декораторы + `FileSystemProvider` (FastMCP best practice)
- DI через `Depends()` с per-request кэшированием сессии
- Pydantic structured output, cursor pagination, async-everywhere
- Существующие подпакеты `services/set/*`, `services/curation/*`, `repositories/track/*` — эталон, который распространяем

---

## 3. Целевая архитектура

### 3.1 Целевая структура `app/mcp/tools/`

```text
app/mcp/tools/
├── CLAUDE.md                       # заполненные guidelines слоя
│
├── _shared/                        # приватный пакет (FastMCP игнорирует _-prefix)
│   ├── __init__.py
│   ├── resolvers.py                # resolve_track_id, resolve_playlist, resolve_set, resolve_entity
│   ├── responses.py                # ResponseBuilder: paginated, brief, standard, mutation_result
│   ├── parsing.py                  # JSON-параметры на boundary (re-export из app.core.parsing)
│   ├── errors.py                   # ToolErrorMapper: domain → MCP, decorator @map_errors
│   ├── progress.py                 # ProgressReporter wrapper над ctx.report_progress
│   ├── elicitation.py              # safe_elicit + типовые prompts (confirm, choose)
│   └── lifespan.py                 # LifespanRegistry: type-safe accessors для ym_client/registry/cache
│
├── library/                        # домен «локальная библиотека»
│   ├── __init__.py
│   ├── tracks_query.py             # list_tracks, get_track, get_track_features
│   ├── tracks_command.py           # manage_tracks (через Command-dispatch)
│   ├── playlists_query.py          # list_playlists, get_playlist
│   ├── playlists_command.py        # manage_playlist (через Command-dispatch)
│   ├── search.py                   # search, filter_tracks
│   └── _commands/                  # Command pattern для multi-action tools
│       ├── __init__.py
│       ├── base.py                 # ToolCommand ABC
│       ├── track_commands.py       # CreateTrack, UpdateTrack, ArchiveTrack, UnarchiveTrack
│       └── playlist_commands.py    # Create, Update, Delete, AddTracks, RemoveTracks, Reorder
│
├── sets/                           # домен «DJ-сеты»
│   ├── __init__.py
│   ├── crud.py                     # list_sets, get_set, manage_set
│   ├── building.py                 # build_set, rebuild_set
│   ├── scoring.py                  # score_transitions, get_set_cheat_sheet
│   ├── reasoning.py                # 5 reasoning tools
│   └── delivery.py                 # deliver_set, export_set
│
├── audio/                          # домен «аудио-анализ»
│   ├── __init__.py
│   ├── analysis.py                 # analyze_track, analyze_batch
│   ├── stems.py                    # separate_stems
│   └── _atomic.py                  # 4 hidden atomic tools (приватный, FastMCP игнорирует)
│
├── curation/                       # домен «курация и качество»
│   ├── __init__.py
│   ├── classification.py           # classify_mood
│   ├── audit.py                    # audit_playlist, review_set_quality
│   ├── distribution.py             # distribute_to_subgenres
│   └── stats.py                    # get_library_stats
│
├── discovery/                      # домен «поиск нового материала»
│   ├── __init__.py
│   ├── similar.py                  # find_similar_tracks
│   ├── expansion.py                # expand_playlist_ym, filter_by_feedback
│   └── ingestion.py                # import_tracks, download_tracks
│
├── integrations/                   # домен «внешние сервисы»
│   ├── __init__.py
│   ├── ym/
│   │   ├── __init__.py
│   │   ├── search.py               # ym_search, ym_get_tracks
│   │   ├── catalog.py              # ym_get_album, ym_artist_tracks
│   │   ├── playlists.py            # ym_playlists (Command-dispatch)
│   │   ├── likes.py                # ym_likes (Command-dispatch)
│   │   └── _commands/
│   │       ├── __init__.py
│   │       ├── base.py             # YMCommand ABC
│   │       ├── playlist_commands.py
│   │       └── like_commands.py
│   └── sync.py                     # sync_playlist, push_set_to_ym
│
└── admin/
    ├── __init__.py
    ├── visibility.py               # unlock_tools
    └── platforms.py                # list_platforms
```

**Важно про FastMCP**:
- `FileSystemProvider` рекурсивно сканит `.py` файлы — любая вложенность работает
- Файлы и директории с `_`-префиксом FastMCP игнорирует — идеально для `_shared/`, `_atomic.py`, `_commands/`
- `__init__.py` оставляем пустыми (FastMCP пропускает их при auto-discovery, но они нужны Python для package-import)
- Tool name остаётся именем функции — путь файла **не** влияет на schema

### 3.2 Целевая структура затронутых сервисов

```text
app/services/
├── import_/                        # бывший import_service.py (342 строки)
│   ├── __init__.py
│   ├── facade.py                   # ImportService — публичный API
│   ├── downloader.py               # YM download orchestration
│   ├── enricher.py                 # metadata enrichment
│   └── linker.py                   # local file linking
│
├── discovery_/                     # бывший discovery_service.py (341 строка)
│   ├── __init__.py
│   ├── facade.py                   # DiscoveryService
│   ├── ym_recommender.py           # YM API similar/recommendations
│   ├── llm_strategy.py             # client-driven LLM discovery
│   └── feedback_filter.py          # filter by liked/disliked
│
├── metadata/                       # бывший metadata_service.py (315 строк)
│   ├── __init__.py
│   ├── facade.py                   # MetadataService
│   ├── cache.py                    # raw_provider_responses cache
│   └── enricher.py                 # YM → local model mapping
│
└── sync/                           # бывший sync_service.py (310 строк)
    ├── __init__.py
    ├── facade.py                   # SyncService
    ├── push.py                     # local → YM push
    ├── pull.py                     # YM → local pull
    └── conflict_resolver.py        # diff/merge conflict logic
```

**Шаблон**: повторяем то, что уже работает в `services/set/*` и `services/curation/*`. Каждый подпакет — facade + 3-4 узких файла. Целевой размер каждого файла: ≤200 строк, hard cap 250.

**Trailing underscore** в `import_/` и `discovery_/` — потому что `import` зарезервированное слово Python, а `discovery` оставляем с `_` для симметрии. Альтернатива (в плане реализации можно обсудить): `track_import/`, `track_discovery/` без подчёркивания.

### 3.3 Применяемые паттерны GoF

| Паттерн | Где | Зачем |
|---|---|---|
| **Command** | `library/_commands/`, `integrations/ym/_commands/` | Заменяет `if/elif`-диспетчеры в `manage_tracks`, `manage_playlist`, `ym_playlists`, `ym_likes`. Каждый action — отдельный класс с `execute(args, deps) -> Result`. Регистрация через dict `{action_name: CommandClass}`. Open/Closed соблюдается. |
| **Builder** | `_shared/responses.py:ResponseBuilder` | Фабрика типовых ответов: `paginated(items, cursor, total)`, `mutation_result(entity, action)`, `brief_list(items)`. Убирает ad-hoc сборку `PaginatedResponse[T]`. |
| **Facade** | каждый `services/{...}/facade.py` | Скрывает sub-сервисы под единым публичным интерфейсом. Паттерн уже работает в `services/set/`, распространяем. |
| **Strategy** | `services/discovery_/llm_strategy.py` + `ym_recommender.py` | Уже есть в коде неявно — формализуем через ABC `DiscoveryStrategy` если это упрощает (если нет — не вводим, KISS). |
| **Template Method** | `_shared/errors.py:@map_errors` decorator | Стандартизирует lifecycle tool: catch domain errors → wrap to ToolError. Без полного `BaseToolHandler` (over-engineering для standalone функций). |
| **Adapter** | `_shared/parsing.py` | Адаптация JSON-строк от MCP-клиентов в Python-объекты на boundary. Re-export из `app.core.parsing` + tool-specific helpers. |
| **Registry** | `_shared/lifespan.py:LifespanRegistry` | Type-safe доступ к lifespan-объектам вместо `ctx.lifespan_context["ym_client"]`. Один класс с classmethod-аксессорами. |

**Что сознательно НЕ делаем**:
- ~~`BaseToolHandler` ABC~~ — over-engineering для standalone-функций. Decorator `@map_errors` решает ту же задачу проще.
- ~~Полный CQRS со всеми атрибутами~~ — только лёгкий split `*_query.py` / `*_command.py` в `library/`, и только потому что там реально смешаны read и mutation в одном файле. В `sets/`, `audio/`, `curation/` оставляем функционально-тематическое разбиение — там нет такой боли.
- ~~Mediator, Chain of Responsibility, Visitor~~ — нет реальной потребности.
- ~~Tool Search transform~~ — out of scope (отдельный future design).

### 3.4 `_shared/` — детали

#### `_shared/resolvers.py`
Единственная точка для resolve-логики. Все tools получают entities через эти функции.
```text
async def resolve_track_id(*, id: int | None, query: str | None, svc: TrackService) -> int
async def resolve_playlist(*, id: int | None, query: str | None, svc: PlaylistService) -> Playlist
async def resolve_set(*, id: int | None, query: str | None, svc: SetService) -> DjSet
def validate_id_or_query(id: int | None, query: str | None, entity_name: str) -> None
```

#### `_shared/responses.py`
```text
class ResponseBuilder:
    @staticmethod
    def paginated(items, *, next_cursor, total, item_type) -> PaginatedResponse[T]
    @staticmethod
    def mutation_result(*, entity_id, action, status="ok") -> MutationResult
    @staticmethod
    def brief_track_list(tracks, artist_map) -> list[TrackBrief]
```
Убирает дублирование batch-fetch artist names и ad-hoc `PaginatedResponse[T]` сборки.

#### `_shared/errors.py`
```text
def map_errors(func):
    """Decorator: ловит NotFoundError/ValidationError/ConflictError → ToolError."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NotFoundError as e:
            raise ToolError(f"{e.entity_type} not found: {e.identifier}") from e
        except ValidationError as e:
            raise ToolError(f"Invalid {e.field}: {e.message}") from e
        except ConflictError as e:
            raise ToolError(str(e)) from e
    return wrapper
```
Применяется как `@tool` + `@map_errors` на каждой tool-функции. Boilerplate уходит из тел tools.

#### `_shared/lifespan.py`
```text
class LifespanRegistry:
    @staticmethod
    def ym_client(ctx: Context) -> YandexMusicClient:
        return ctx.lifespan_context["ym_client"]
    @staticmethod
    def analyzer_registry(ctx: Context) -> AnalyzerRegistry: ...
    @staticmethod
    def transition_cache(ctx: Context) -> TransitionCache: ...
```
Type-safe замена magic strings. `dependencies.py` использует эти аксессоры внутри `get_ym_client()` etc., а tools получают объекты через `Depends(get_ym_client)` как сейчас — никаких изменений в публичном API DI.

#### `_shared/elicitation.py`
Тонкая обёртка над `ctx.elicit()` с типовыми сценариями: `confirm_destructive`, `choose_one`, `confirm_with_warnings(warnings: list[str])`. Убирает дублирование elicitation-логики в `delivery.py`, `manage_*`, `sync_playlist`.

### 3.5 Command pattern — детали

**Проблема**: `ym_playlists(action: str, ...)` принимает 8 разных action и делает 70-строчный `if/elif`. Добавление 9-го action требует правки этой функции (OCP violation), и type-safety параметров теряется (одни параметры применимы для одного action, другие — для другого).

**Решение**: каждый action — отдельный класс.

```text
# integrations/ym/_commands/base.py
class YMPlaylistCommand(ABC):
    name: ClassVar[str]
    @abstractmethod
    async def execute(self, args: dict, ctx: Context, ym: YandexMusicClient) -> dict: ...

# integrations/ym/_commands/playlist_commands.py
class GetPlaylistCommand(YMPlaylistCommand):
    name = "get"
    async def execute(self, args, ctx, ym): ...

class CreatePlaylistCommand(YMPlaylistCommand):
    name = "create"
    async def execute(self, args, ctx, ym): ...
# ... 6 more

# integrations/ym/_commands/__init__.py
PLAYLIST_COMMANDS: dict[str, type[YMPlaylistCommand]] = {
    cmd.name: cmd for cmd in [
        GetPlaylistCommand, ListPlaylistsCommand, CreatePlaylistCommand,
        RenamePlaylistCommand, DeletePlaylistCommand,
        AddTracksCommand, RemoveTracksCommand, GetPlaylistTracksCommand,
    ]
}

# integrations/ym/playlists.py — сам tool становится тонким
@tool(tags={"ym"}, annotations={"readOnlyHint": False})
@map_errors
async def ym_playlists(
    action: Literal["get", "list", "create", "rename", "delete", "add_tracks", "remove_tracks", "get_tracks"],
    ctx: Context = CurrentContext(),
    ym: YandexMusicClient = Depends(get_ym_client),
    **args,
) -> dict:
    """Yandex Music playlist operations."""
    cmd_cls = PLAYLIST_COMMANDS.get(action)
    if cmd_cls is None:
        raise ToolError(f"Unknown action: {action}")
    return await cmd_cls().execute(args, ctx, ym)
```

То же для `manage_playlist`, `manage_tracks`, `ym_likes`. Каждый command — ≤30 строк, single responsibility, легко тестируется в изоляции.

**Возражение, которое нужно учесть**: Command-классы делают tool-схему менее декларативной — `**args` непрозрачны для MCP-клиента. Это **сознательный trade-off**: schema сейчас уже непрозрачна (в docstring перечисляются «для action=get нужны owner_id, kind, для action=create нужно name…»). Альтернатива (typed Pydantic Union) перегружает schema. Вариант: можно для каждой команды генерировать input-schema через discriminated union, если будет жалоба от пользователей. Это можно добавить итеративно.

### 3.6 Стабильность контрактов

**Что НЕ меняется**:
- Имена всех 50 tools
- Параметры (имена, типы, опциональность)
- Return-схемы (Pydantic models)
- Tags (`core`, `sets`, `ym`, `audio`, `atomic`, ...)
- Annotations (`readOnlyHint`, ...)
- Поведение (включая edge cases и error messages по возможности)
- DI factory имена (`get_track_service`, ...) — panel server actions от них зависят
- `serve_http.py` REST endpoints

**Что меняется** (внутреннее, не визуально для клиента):
- Расположение файлов
- Импорты
- Внутренняя организация кода tool-функций (становятся тоньше за счёт `_shared/` и `_commands/`)
- Сигнатуры внутренних методов сервисов (split god-files)

---

## 4. Constants и hardcoded values

**Аудит**: пройти все tool-файлы и убедиться, что:
- Дефолтные `limit`, `cursor` берутся из `settings.list_page_size`
- Имена error-сообщений шаблонизированы и собраны в `_shared/errors.py:ERROR_MESSAGES`
- Дефолтные timeouts ссылаются на `settings.tool_*_timeout`
- Magic numbers (например, `top_n=5` в `score_transitions`) выносятся либо в `settings`, либо в `app/core/constants.py`, либо в новый `app/mcp/tools/_shared/constants.py` для tool-specific (если значение не имеет смысла за пределами слоя tools)

**Правило**: ничего числового или строкового, что может потребовать настройки, не остаётся в теле tool-функции.

---

## 5. CLAUDE.md для tools-слоя

Создаём содержательный `app/mcp/tools/CLAUDE.md` с разделами:
1. **Layer responsibilities** — что tools могут делать, что не могут
2. **Directory layout** — карта доменов и правила размещения новых tools
3. **Naming conventions** — `*_query.py` / `*_command.py` (только в `library/`), глаголы для tool-функций
4. **DI rules** — `Depends()` через factories, не import прямо из service-слоя
5. **Error handling** — `@map_errors` decorator, когда поднимать `ToolError` напрямую
6. **Response building** — `ResponseBuilder`, не собирать `PaginatedResponse` вручную
7. **Adding multi-action tool** — Command pattern в `_commands/`
8. **File size limits** — ≤200 строк target, 250 hard cap
9. **Tests mirror** — `tests/test_mcp/tools/<domain>/test_<file>.py`

---

## 6. Тесты

### 6.1 Цель тестирования
- **Поведение tools не меняется** — все существующие тесты должны проходить без изменений (кроме обновления import paths)
- **Новые тесты** на `_shared/` (resolvers, ResponseBuilder, ErrorMapper, LifespanRegistry, command dispatch)
- **Тесты на каждый Command class** в изоляции — теперь возможно, потому что они отдельные классы

### 6.2 Структура тестов
```text
tests/test_mcp/tools/
├── _shared/
│   ├── test_resolvers.py
│   ├── test_responses.py
│   ├── test_errors.py
│   └── test_lifespan.py
├── library/
│   ├── test_tracks_query.py
│   ├── test_tracks_command.py
│   ├── test_playlists_query.py
│   ├── test_playlists_command.py
│   ├── test_search.py
│   └── _commands/
│       ├── test_track_commands.py
│       └── test_playlist_commands.py
├── sets/
│   ├── test_crud.py
│   ├── test_building.py
│   ├── test_scoring.py
│   ├── test_reasoning.py
│   └── test_delivery.py
├── audio/...
├── curation/...
├── discovery/...
├── integrations/
│   └── ym/
│       ├── test_search.py
│       ├── test_catalog.py
│       ├── test_playlists.py
│       ├── test_likes.py
│       └── _commands/
│           ├── test_playlist_commands.py
│           └── test_like_commands.py
└── admin/...
```

### 6.3 Регрессионный gate
- `make check` (lint + typecheck + test) проходит после каждого этапа
- Полный pytest-suite зелёный
- `serve_http.py` стартует, `/api/tools` возвращает те же 50 tools с теми же schemas (snapshot test)
- Panel `dev`-сборка стартует (smoke test для server actions, которые ходят в REST API)

---

## 7. Этапы реализации (краткий контур, детали в плане)

| Этап | Содержание | Риск | Регрессионный gate |
|---|---|---|---|
| **0** | Snapshot existing tool catalog: имена, schemas, tags. Сохранить как fixture для regression test | Низкий | — |
| **1** | Создать `_shared/` (resolvers, responses, errors, lifespan, parsing, progress, elicitation) с тестами. Не трогать существующие tools. | Низкий | tests + lint |
| **2** | Заполнить `app/mcp/tools/CLAUDE.md` | Низкий | — |
| **3** | Refactor service god-files (parallel — не блокирует tools): `import_service.py` → `services/import_/*` | Средний | tests + lint + typecheck |
| **4** | То же для `discovery_service.py`, `metadata_service.py`, `sync_service.py` | Средний | tests + lint + typecheck |
| **5** | Создать domain-директории `library/`, `sets/`, `audio/`, `curation/`, `discovery/`, `integrations/`, `admin/`. Перенести tool-файлы (move + rename). Обновить импорты. **Никаких изменений в логике на этом этапе.** | Высокий (много impact на импорты) | tests + lint + typecheck + snapshot test |
| **6** | Применить `@map_errors` ко всем tools, заменить вручную try/except на decorator | Низкий | tests |
| **7** | Применить `ResponseBuilder` — заменить ad-hoc `PaginatedResponse[T]` сборки | Низкий | tests |
| **8** | Внедрить Command pattern в `library/_commands/track_commands.py` (для `manage_tracks`) | Средний | tests + Command-unit-tests |
| **9** | То же для `library/_commands/playlist_commands.py` (для `manage_playlist`) | Средний | tests + Command-unit-tests |
| **10** | То же для `integrations/ym/_commands/playlist_commands.py` (для `ym_playlists`) | Средний | tests + Command-unit-tests |
| **11** | То же для `integrations/ym/_commands/like_commands.py` (для `ym_likes`) | Низкий | tests + Command-unit-tests |
| **12** | Hardcoded values audit: вынести в `settings`/constants. Заменить magic strings в lifespan-доступе на `LifespanRegistry` (внутри `dependencies.py`) | Низкий | tests + lint |
| **13** | Финальный audit: размер файлов, test coverage, snapshot tool catalog vs baseline | Низкий | full `make check` + snapshot diff (должен быть пустым) |

Каждый этап = отдельный atomic commit. Этапы 3-4 (service refactor) можно делать параллельно с 1-2 (`_shared/`), они не пересекаются. Этапы 8-11 независимы между собой и можно делать в любом порядке.

**Важное правило**: на этапе 5 — **только перемещение**, никакого изменения логики. Это отдельный коммит, который большой по diff, но семантически тривиален. Все рефакторинговые изменения внутри tool-функций — на этапах 6-12, после того как файлы уже на своих местах.

---

## 8. Риски и mitigation

| Риск | Вероятность | Mitigation |
|---|---|---|
| Сломаются импорты в panel/REST API | Средняя | DI factory имена сохраняем 1:1; snapshot test на `/api/tools` |
| Сломаются тесты при перемещении файлов | Высокая | Обновить test imports в том же коммите; запуск `make check` после каждого этапа |
| Command pattern усложнит schema для MCP-клиентов | Низкая | Сохраняем тот же `action: Literal[...]` параметр; **args скрыт от schema через тип `dict` |
| God-file refactor сломает чужой код, который импортирует напрямую из `import_service` | Средняя | grep по всему репо на `from app.services.import_service import` перед refactor; добавить `__init__.py` re-export для обратной совместимости только если найдены consumers вне tools |
| Слишком большой PR для review | Высокая | 14 этапов = 14 коммитов, каждый review-friendly. Опционально: поэтапные PR в feature branch |
| Регрессия в edge case behavior | Средняя | Нулевые изменения логики на этапе 5; отдельные unit tests для каждого Command class |
| FastMCP не подхватит файлы из новой структуры | Низкая | Подтверждено: FileSystemProvider рекурсивно сканит `.py`, `_`-prefix игнорируется. Smoke test на этапе 5: `python -c "from app.server import mcp; print(len(mcp.list_tools()))"` |

---

## 9. Что вне scope

- **Tool Search transform** — отдельный future design. Решает другую проблему (50 tools в context) и не блокируется этим refactor.
- **Изменения в `app/mcp/resources/`, `app/mcp/prompts/`, `app/audio/`, `app/domain/`, `app/repositories/`** — стабильны, не имеют такого же долга.
- **Изменения REST API `serve_http.py`** — структурно тонкий wrapper, не нуждается в refactor.
- **Panel** — server actions ходят в REST API, который остаётся стабильным.
- **Новые tools / новые фичи** — это refactor, не feature work.
- **Изменения tool schemas** — стабильность контрактов важнее структурной чистоты.
- **Замена `Depends()` на что-то другое** — текущий механизм оптимален.
- **Миграция на typed Union для action-параметров Command tools** — может быть добавлено позже, если будет request от клиентов.

---

## 10. Метрики успеха

После завершения всех этапов:

| Метрика | Сейчас | Цель |
|---|---|---|
| Файлов в `app/mcp/tools/` (рекурсивно) | 19 + 1 helper | ~40 (с группировкой по доменам) |
| Самый большой tool-файл | 339 строк (`ym.py`) | ≤200 строк (любой) |
| God-files в `app/services/` (>300 строк) | 5 | 0 |
| Самый длинный `if/elif` action chain | ~70 строк | 0 (заменены Command pattern) |
| Дублирующиеся helper-функции | 3+ известных | 0 |
| Ad-hoc `PaginatedResponse[T]` сборок | ~10 локаций | 0 (через `ResponseBuilder`) |
| Magic strings в lifespan-доступе | ~6 | 0 (через `LifespanRegistry`) |
| Tool catalog snapshot diff с baseline | — | 0 (полная стабильность контрактов) |
| `make check` | проходит | проходит |
| Test coverage `app/mcp/tools/` | (текущий уровень) | ≥ текущий + новые тесты на `_shared/` и Commands |

---

## 11. Открытые вопросы (для уточнения перед планом)

1. **Trailing underscore в `services/import_/` и `services/discovery_/`** — приемлемо или предпочесть `track_import/` / `track_discovery/`? *(моя рекомендация: trailing underscore — короче и яснее, что это про import операцию, а не про trackы; но решение незначительное)*
2. **Регрессионный snapshot tool catalog** — куда сохранить fixture? Предлагаю `tests/test_mcp/fixtures/tool_catalog_baseline.json`.
3. **Этапы 3-4 (service refactor)** — делать ДО или ПОСЛЕ tool-refactor? *(моя рекомендация: до — это даёт чистые service interfaces, на которые проще ложатся новые tool-обёртки)*

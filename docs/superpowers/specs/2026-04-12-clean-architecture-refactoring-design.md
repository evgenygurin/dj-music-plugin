# Clean Architecture Refactoring — Design Spec

> Полная перестройка dj-music-plugin из flat monolith в Modular Monolith с Clean Architecture.

## Проблема

Текущий проект (~304 Python файла, ~28.6K LOC без миграций):

1. **Flat monolith** — 18 пакетов на одном уровне в `app/` без bounded contexts
2. **Три слоя данных без границ** — `db/models/` (ORM), `schemas/` (dataclass), `schemas/` (Pydantic) пересекаются
3. **controllers/ гигант** — tools, dependencies, resources, prompts, middleware, schemas в одном пакете
4. **services/ flat bag** — 15+ сервисов без группировки
5. **Дублирование** — `build_ym_client()` x2, `_classify_mood` x2, `resolve_track_refs` x2
6. **Layer violations** — 21 прямой импорт `app.db.models` в services
7. **Config god-object** — 100+ настроек в одном `Settings` классе
8. **Ghost directories** — 6 пустых директорий без кода

## Что уже хорошо (не ломать)

- `transition/` — чистый домен, хорошая декомпозиция
- `audio/` — layered, GoF паттерны (Registry, Strategy, Template Method)
- `export/` — pure domain writers
- `optimization/` — Strategy pattern, чистый домен
- `import-linter` — 6 контрактов
- UnitOfWork pattern реализован
- FileSystemProvider auto-discovery работает

## Принятые решения

| Решение | Выбор | Причина |
|---------|-------|---------|
| Архитектура | Clean Architecture | Строгие слои, dependency rule |
| Корневой пакет | `src/dj_music/` | Правильное Python packaging |
| Entity = Schema | Один пакет `schemas/` | Entity + DTO + Filter + Validator в одном месте (Entity-First) |
| Mapper | `from_attributes=True` | `Schema.model_validate(orm_obj)` — Pydantic маппит автоматически |
| Ports (Protocol) | Да, на границах | Repositories + YM client + Cache |
| Config split | Да, по доменам | Решает god-object |
| FileSystemProvider | `tools/` + `prompts/` + `resources/` | Scan flat top-level packages |

---

## Целевая архитектура

### Плоская структура — компоненты на top-level

Каждый компонент = отдельный пакет. Без обёрток `infrastructure/`, `presentation/`, `application/`.
Dependency rule через import-linter, не через вложенность.

```text
src/dj_music/
├── core/              # Config, Error, Types, Utils, Logging, Monitoring
│                      # entities/ УБРАН — Entity-First: всё в schemas/
├── models/            # SQLAlchemy ORM models
├── repositories/      # Data access + CRUD + Protocol ports
├── services/          # Business logic (use cases)
├── schemas/           # Pydantic DTOs + Validators
├── tools/             # MCP @tool handlers (Controller)
├── prompts/           # MCP @prompt handlers
├── resources/         # MCP @resource handlers
├── middleware/        # Request pipeline (FastMCP + custom)
├── audio/             # Analyzers, DSP, Pipeline, Classification
├── transition/        # Scoring, components, weights (pure)
├── optimization/      # GA, greedy, fitness (pure)
├── export/            # M3U8, Rekordbox, JSON writers (pure)
├── templates/         # Set templates (pure data)
├── engines/           # DeckEngine, MixerEngine (runtime)
├── ym/                # Yandex Music client
├── api/               # FastAPI REST wrapper
├── bootstrap/         # Server assembly, Lifespans, DI
└── server.py          # Entry point
```

### Dependency Rule

```text
Tool (Controller) --> Schema --> Service --> Repository --> Entity
     |                  |                       |
  Prompt             Validator               Model (ORM)
  Resource                                   CRUD (in BaseRepo)

Core --> Config, Error, Middleware --> Logging, Monitoring, Rate Limit
         Util --> Time, UUID
         (BaseEntity, BaseValueObject, BaseFilter → schemas/base.py)

Audio --> Pipeline (analyzers + DSP)
Transition, Optimization, Export, Templates --> pure (only core deps)
```

Стрелки = зависимости. Import-linter контракты обеспечивают:
- `schemas/`, `transition/`, `optimization/`, `export/` → зависят ТОЛЬКО от `core/`
- `services/` → зависит от `schemas/`, `core/`, `repositories/` (через Protocol)
- `services/` НЕ импортирует `models/`, `tools/`, `ym/`, `api/`
- `tools/` → зависит от `services/`, `schemas/`, `core/`
- `tools/` НЕ импортирует `models/`, `repositories/` напрямую
- `repositories/` → зависит от `models/`, `schemas/`, `core/`

---

## Детальная структура

Каждый компонент = top-level пакет. Вложенность только где напрашивается (tools/yandex/, repositories/track/, audio/analyzers/).

**Pydantic everywhere:** Entity, ValueObject, Schema, Config — всё Pydantic BaseModel.
Repository конвертирует ORM → Entity через `model_validate(orm_obj)` (from_attributes=True).

```text
src/dj_music/
│
├── core/                        # Config, Error, Types, Utils, Logging
│   # types.py убран — BaseEntity/BaseValueObject/BaseFilter/BaseSort/BasePagination в schemas/base.py
│   ├── errors.py                # DJMusicError hierarchy + ctx chain
│   ├── constants.py             # SortField, SortDir, TechnoSubgenre, etc.
│   ├── camelot.py               # Camelot wheel pure math
│   ├── logging.py               # structlog setup, processor chain
│   ├── config/                  # Split Settings by domain
│   │   ├── __init__.py          # Composite Settings facade
│   │   ├── audio.py, scoring.py, ym.py, server.py, db.py
│   └── utils/
│       ├── time.py, parsing.py, cache.py, files.py, pagination.py
│
├── schemas/                     # Entity-First: Entity + DTO + Filter + Validator
│   ├── base.py                  # BaseEntity, BaseValueObject, BaseFilter, BaseSort, BasePagination
│   ├── track.py                 # Track, TrackCreate, TrackBrief, TrackFilter
│   ├── audio.py                 # TrackFeatures, AudioFeatures, Embedding
│   ├── playlist.py              # Playlist, PlaylistItem, PlaylistSummary, PlaylistFilter
│   ├── set.py                   # DjSet, SetVersion, SetItem, SetSummary, SetFilter
│   ├── transition.py            # Transition, TransitionCandidate, TransitionScoreDTO
│   ├── library.py               # LibraryItem, Beatgrid, CuePoint, SavedLoop
│   ├── platform.py              # YandexMetadata, SpotifyMetadata
│   ├── common.py                # CursorPage, PaginatedResponse
│   └── yandex.py, deck.py, mixer.py
│   #
│   # Base classes в base.py:
│   #   BaseEntity(BaseModel, from_attributes=True, extra="forbid")
│   #   BaseValueObject(BaseModel, frozen=True)
│   #   BasePagination(BaseModel) — limit + cursor
│   #   BaseSort(BaseModel) — sort_dir (enum)
│   #   BaseFilter(BaseModel, extra="forbid") — все поля optional
│   #
│   # Каждый XxxFilter наследует BaseFilter + BaseSort + BasePagination:
│   #   class TrackFilter(BaseFilter, BaseSort, BasePagination):
│   #       bpm_min, bpm_max, key_code, energy_min, sort_by, ...
│   #       @model_validator — validate ranges (bpm_min <= bpm_max)
│   #
│   # Repository.filter(params: BaseFilter) → CursorPage[TSchema]
│
├── models/                      # SQLAlchemy ORM (44 tables)
│   ├── base.py
│   ├── track.py, audio.py, playlist.py, set.py
│   ├── transition.py, platform.py, library.py, key.py
│   └── export.py, ingestion.py, feedback.py, scoring_profile.py
│
├── repositories/                # Data access: BaseRepository[TModel, TSchema] + ports
│   ├── base.py                  # Generic CRUD via model_validate/model_dump
│   ├── ports.py                 # Protocol interfaces (TrackRepo, SetRepo, etc.)
│   ├── unit_of_work.py          # UnitOfWork aggregator
│   ├── session.py               # async_session_factory
│   ├── seed.py                  # Reference data (keys, providers)
│   ├── track/                   # Mixin composition (core, filtering, library, stats)
│   ├── playlist.py, set.py, feature.py, audio.py
│   ├── transition.py, candidate.py, embedding.py, export.py
│   └── metadata.py, ingestion.py, track_affinity.py, track_feedback.py
│
├── services/                    # Business logic (composition, not inheritance)
│   ├── track.py, playlist.py, search.py, metadata.py
│   ├── audio_analysis.py, tiered_pipeline.py
│   ├── set_builder.py, set_scoring.py, set_crud.py, set_facade.py
│   ├── reasoning.py, delivery.py, discovery.py
│   ├── import_.py, sync.py, export.py
│   ├── curation.py, curation_mood.py, curation_audit.py
│   ├── transition.py, transition_cache.py, optimizer.py
│   ├── affinity.py, feedback.py, background_tasks.py
│   └── workflows/               # Multi-step orchestrators
│       ├── analyze_track.py, build_set.py, deliver_set.py
│       └── import_tracks.py, sync_playlist.py
│
│   # (schemas/ уже описан выше — не дублируем)
│
├── tools/                       # MCP @tool handlers (FileSystemProvider scans here)
│   ├── _shared/                 # taxonomy, context, dispatch, entity_resolver, errors
│   ├── tracks.py, playlists.py, sets.py, search.py, reasoning.py
│   ├── audio.py, audio_atomic.py, curation.py, delivery.py
│   ├── discovery.py, import_download.py, sync.py, admin.py
│   ├── monitoring.py, decks.py, mixer.py
│   └── yandex/                  # search, tracks, albums, playlists, likes
│
├── prompts/                     # MCP @prompt handlers
│   └── workflows/               # build_set, deliver_set, expand_playlist
│
├── resources/                   # MCP @resource handlers
│   ├── status.py, templates.py
│   └── reference/               # camelot, subgenres, templates
│
├── middleware/                  # FastMCP built-in + custom middleware
│   ├── request_id.py, logging.py, error_handler.py, rate_limit.py
│
├── audio/                       # Analyzers, DSP, Pipeline, Classification
│   ├── model.py, context.py
│   ├── dsp/                     # spectral, rhythm, tonal, framing (pure numpy)
│   ├── analyzers/               # 18 analyzers (Registry pattern)
│   ├── classification/          # MoodClassifier + profiles
│   ├── quality/                 # Audit rules
│   ├── pipeline.py, loader.py, temp_download.py, timeseries.py
│
├── transition/                  # Scoring (pure, only core/ deps)
│   ├── model.py, scorer.py, constraints.py, intent.py, style.py
│   ├── components/              # bpm, harmonic, energy, spectral, groove, timbral
│   └── recipe.py, recipe_engine.py, weights.py, math.py
│
├── optimization/                # GA, greedy, fitness (pure)
│   └── protocol.py, fitness.py, genetic.py, greedy.py, result.py
│
├── export/                      # Writers (pure, no I/O)
│   └── model.py, m3u8.py, rekordbox.py, json_guide.py, cheatsheet.py
│
├── templates/                   # Set templates (pure data)
│   └── model.py, registry.py
│
├── engines/                     # DeckEngine, MixerEngine (runtime singletons)
│   ├── base.py, lifespan.py
│   ├── deck/                    # engine.py, state.py
│   └── mixer/                   # engine.py
│
├── ym/                          # Yandex Music client
│   └── client.py, models.py, rate_limiter.py, filters.py
│
├── api/                         # FastAPI REST wrapper
│   ├── server.py, state.py, lifespan.py, openapi.py, schemas.py
│   ├── routes/                  # health, discovery, execution, audio
│   └── services/                # tool_registry, signed_url_cache, ym_audio_proxy
│
├── bootstrap/                   # Server assembly, Lifespans, DI
│   ├── server_builder.py, lifespans.py, transforms.py
│   ├── middleware.py, visibility.py, observability.py, sampling.py
│   └── di/                      # Composition root
│       └── db.py, repos.py, services.py, audio.py, external.py, uow.py
│
├── migrations/                  # Alembic
│   └── env.py, versions/
│
└── server.py                    # Entry point
```

## Import-Linter контракты

```ini
[importlinter]
root_packages = dj_music

# 1. Domain must be pure
[importlinter:contract:domain-pure]
name = Domain must have no external dependencies
type = forbidden
source_modules = dj_music.schemas
forbidden_modules =
    dj_music.services
    dj_music.ym
    dj_music.tools
    dj_music.engines
    sqlalchemy
    httpx
    fastmcp
    fastapi

# 2. Application must not depend on infrastructure
[importlinter:contract:application-no-infrastructure]
name = Application uses ports not infrastructure
type = forbidden
source_modules =
    dj_music.services
    dj_music.services.workflows
forbidden_modules =
    dj_music.ym
    dj_music.tools
    sqlalchemy
    httpx
    fastmcp

# 3. Kernel is a leaf
[importlinter:contract:core-leaf]
name = Core must not depend on any app layer
type = forbidden
source_modules = dj_music.core
forbidden_modules =
    dj_music.schemas
    dj_music.services
    dj_music.ym
    dj_music.tools
    dj_music.engines

# 4. Presentation tools must not access infra directly
[importlinter:contract:presentation-no-infra]
name = Presentation depends on application not infrastructure
type = forbidden
source_modules =
    dj_music.tools
    dj_music.resources
    dj_music.prompts
forbidden_modules =
    dj_music.models
    dj_music.repositories

# 5. Engines must not depend on transport
[importlinter:contract:engines-no-transport]
name = Engines must not depend on presentation or infra IO
type = forbidden
source_modules = dj_music.engines
forbidden_modules =
    dj_music.tools
    dj_music.ym
    dj_music.repositories
```

---

## Error Handling, Logging, Observability

### 3-слойная обработка ошибок

```text
Domain layer      → raise DJMusicError с structured context (ctx dict)
Infrastructure    → catch low-level, wrap в domain errors (ConnectionError → DatabaseUnavailable)
Presentation      → convert domain errors в transport responses (DJMusicError → ToolError / HTTP 4xx)
```

### DJMusicError с контекстной цепочкой

```python
class DJMusicError(Exception):
    def __init__(self, message: str, ctx: dict | None = None):
        self.ctx = ctx or {}
        super().__init__(message)

    def get_context_chain(self) -> dict:
        """Собирает ctx из всей цепочки __cause__."""
        ctx = self.ctx.copy()
        if self.__cause__ and isinstance(self.__cause__, DJMusicError):
            ctx.update(self.__cause__.get_context_chain())
        return ctx
```

Позволяет: `raise NotFoundError("Track", 42, ctx={"query": "ym:12345"})` → лог содержит полный контекст.

### Middleware Chain (порядок критичен)

```text
Client → RequestID → Logging → ErrorHandler → RateLimit → App
   ↑                                                       |
   +--- RateLimit ← ErrorHandler ← Logging ← RequestID ←---+
```

- **RequestID** — генерирует/принимает trace ID, ставит в `contextvars` (не request.state)
- **Logging** — structured access log (method, path, status, duration, request_id)
- **ErrorHandler** — catch exceptions, wrap в clean responses, log с traceback
- **RateLimit** — MCP tool rate limiting

### Structured Logging (structlog)

```text
structlog processor chain:
  1. contextvars.merge_contextvars    — request_id, tool_name автоматически
  2. stdlib.add_log_level            — DEBUG/INFO/WARNING/ERROR
  3. stdlib.add_logger_name          — module path
  4. process_custom_exceptions       — auto-extract ctx из DJMusicError
  5. TimeStamper(fmt="iso")          — ISO timestamps
  6. JSONRenderer (prod) / ConsoleRenderer (dev)
```

- **Production**: JSON → stdout → log aggregation (Sentry, ELK)
- **Development**: colored console output, human-readable
- **contextvars**: request_id propagates через все слои без передачи параметром
- **Шумные библиотеки** (httpx, httpcore): уровень WARNING

### Sentry интеграция

```text
structlog chain включает SentryProcessor:
  - ERROR/CRITICAL → автоматически отправляются в Sentry
  - DJMusicError.ctx → Sentry breadcrumbs/tags
  - request_id → Sentry event tag (связь с логами)
```

### Observability файлы в новой структуре

```text
src/dj_music/
├── core/
│   ├── errors.py            # DJMusicError hierarchy с ctx + get_context_chain()
│   ├── logging.py           # structlog configuration, processor chain, setup_logging()
│   ├── sentry.py            # Sentry DSN init, SentryProcessor
│   └── telemetry.py         # OTEL traces (optional)
│
└── middleware/               # FastMCP built-in + custom middleware
    ├── request_id.py        # RequestID → contextvars
    ├── logging.py           # Access log middleware
    ├── error_handler.py     # Exception → ToolError conversion
    └── rate_limit.py        # Rate limiting
```

---

## SQLAlchemy 2.0 — обязательные паттерны

| Паттерн | Когда | Пример |
|---------|-------|--------|
| `selectinload()` | Перед `model_validate()` для relationships | `select(Track).options(selectinload(Track.artists))` |
| `load_only()` | Heavy entities (TrackFeatures 80+ полей) | `select(Track).options(load_only(Track.id, Track.title))` |
| `WriteOnlyMapped` | Большие коллекции (track_sections 108K строк) | `sections: WriteOnlyMapped[Section] = relationship(...)` |
| `expire_on_commit=False` | Async sessions | В `async_session_factory` |
| `flush()` never `commit()` | Все repositories | Commit на уровне DI `get_db_session()` |
| `Mapped[]` + `mapped_column()` | Все модели | SQLAlchemy 2.0 style, не legacy `Column()` |

---

## Pydantic v2 — обязательные возможности

| Возможность | Когда | Пример |
|-------------|-------|--------|
| `from_attributes=True` | Entity schema маппинг из ORM | `Track.model_validate(orm_track)` |
| `frozen=True` | Value Objects (immutable) | `class Bpm(BaseValueObject): value: float` |
| `computed_field` | Вычисляемые свойства | `@computed_field def camelot(self) -> str` |
| `field_validator` | Валидация одного поля | `@field_validator('bpm') def check_bpm(cls, v)` |
| `model_validator(mode="after")` | Cross-field валидация | `bpm_min <= bpm_max` в Filter |
| `model_validator(mode="before")` | Pre-parse данных | Нормализация input перед валидацией |
| `Field(ge=, le=)` | Constraint validation | `bpm: float = Field(ge=20, le=300)` |
| `model_dump(include/exclude)` | Brief/full views | `track.model_dump(include={"id","title","bpm"})` |
| `Discriminator` | Полиморфные unions | `platform: Annotated[Union[YM, Spotify], Discriminator("type")]` |
| `TypeAdapter` | Standalone type validation | `TypeAdapter(list[Track]).validate_python(data)` |
| `extra="forbid"` | Strict filters | `class TrackFilter(BaseFilter): model_config = ...` |

### Validator guidelines

- `@field_validator` — валидация одного поля (range, format, normalization)
- `@model_validator(mode="after")` — cross-field (bpm_min <= bpm_max, key + camelot consistency)
- `@model_validator(mode="before")` — pre-parse (string → int, normalize case)
- Переиспользование: вынести общие validators в `schemas/base.py` как standalone functions
- Никогда `@validator` (deprecated) — только `@field_validator` / `@model_validator`

---

## Почему НЕТ BaseService

Сервисы слишком разные для общего базового класса:

```python
# TrackService: 2 зависимости
class TrackService:
    def __init__(self, tracks: TrackRepository, features: FeatureRepository): ...

# SetService: 5 зависимостей, facade over 4 sub-services
class SetService:
    def __init__(self, sets, tracks, playlists, features, transitions): ...

# AudioService: pipeline + repo + downloader
class AudioService:
    def __init__(self, pipeline: AnalysisPipeline, features: FeatureRepository): ...
```

BaseService с `self.repo` не подходит — у каждого сервиса свой набор зависимостей.
**Composition > Inheritance** для сервисного слоя. Protocol ports обеспечивают testability.

---

## GoF паттерны

### Сохраняем (уже в кодовой базе)

| Паттерн | Где |
|---------|-----|
| Strategy | optimization/ (GA vs Greedy) |
| Registry | audio/analyzers/ |
| Facade | set_facade, curation |
| Template Method | BaseAnalyzer |
| Command + Registry | ActionDispatcher |
| Unit of Work | UnitOfWork |
| Repository | BaseRepository[T] |

### Добавляем

| Паттерн | Где | Зачем |
|---------|-----|-------|
| Port/Adapter | repositories/ports.py | Инверсия зависимостей |
| Abstract Factory | di/ | Composition root |

---

## Dependency Injection — архитектура

### DI Chain (4 уровня)

```text
Level 1: Session     — get_db_session() → async context manager (commit/rollback/close)
Level 2: Repository  — get_track_repo(session=Depends(get_db_session)) → конкретный repo
Level 3: Service     — get_track_service(repo=Depends(get_track_repo)) → service с Protocol deps
Level 4: Tool        — @tool list_tracks(service=Depends(get_track_service)) → hidden from LLM
```

### 3 способа инъекции в FastMCP

| Способ | Когда | Видимость LLM |
|--------|-------|---------------|
| `ctx: Context` | Request context | Hidden |
| `param = Depends(factory)` | Repos, services, clients | Hidden |
| `ctx: Context = CurrentContext()` | Explicit context | Hidden |

**Depends() параметры автоматически скрыты от LLM schema.** Клиент видит только бизнес-параметры.

### Session lifecycle

```python
# bootstrap/di/db.py — ЕДИНСТВЕННОЕ место commit/rollback
@asynccontextmanager
async def get_db_session():
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

### Lifespan vs Depends — разное время жизни

| Компонент | Время жизни | Механизм |
|-----------|-------------|----------|
| YM client, Analyzer registry | Server lifetime | `@lifespan` → state dict |
| DB session, repos, services | Per-request (tool call) | `Depends()` → context manager |
| UnitOfWork | Per-request | `Depends(get_uow)` |

### Lifespan → DI bridge

```python
# Singletons из lifespan доступны через ctx:
def get_ym_client(ctx: Context = CurrentContext()) -> YandexMusicClient:
    return ctx.request_context.lifespan_context["ym_client"]
```

### DI modules в bootstrap/di/

```text
bootstrap/di/
├── db.py          # get_db_session (context manager, commit/rollback)
├── repos.py       # get_track_repo, get_set_repo, etc.
├── services.py    # get_track_service, get_set_service, etc.
├── audio.py       # get_audio_service, get_tiered_pipeline
├── external.py    # get_ym_client (from lifespan state)
└── uow.py         # get_uow (UnitOfWork aggregator)
```

### Ключевые правила DI

| Правило | Причина |
|---------|---------|
| Session = async context manager | Гарантирует commit/rollback/close |
| Repos flush(), never commit() | Транзакция на уровне tool call |
| Services принимают Protocol, не конкретный класс | Testability, ISP |
| DI factories в bootstrap/di/, не в domain/ | Domain не знает о DI framework |
| Lifespan для singletons, Depends для per-request | Разное время жизни |
| Один session на весь tool call | Consistency, UoW |

---

## Middleware, Pagination, Validation, Sorting, Filtering

### Middleware — FastMCP built-in stack

FastMCP v3 предоставляет 6 готовых middleware. Порядок добавления = onion (первый = outermost):

```python
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
# + RetryMiddleware, SlidingWindowRateLimitingMiddleware

mcp.add_middleware(ErrorHandlingMiddleware(include_traceback=True, error_callback=sentry_cb))
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=10, burst_capacity=20))
mcp.add_middleware(ResponseLimitingMiddleware(max_size=500_000))
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(LoggingMiddleware())
```

Custom middleware наследует `Middleware` с `on_request` / `on_message`:

```python
class RequestIdMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        request_id = str(uuid4())
        request_id_var.set(request_id)  # contextvars
        return await call_next(context)
```

### Pagination — два уровня

| Уровень | Механизм | Для чего |
|---------|----------|----------|
| FastMCP list pagination | `list_page_size=50` в конструкторе | tools/list, resources/list (MCP protocol) |
| Tool-level cursor pagination | `BaseRepository._paginate()` + `CursorPage[T]` | list_tracks, list_playlists (бизнес-данные) |

Оба нужны. FastMCP pagination — для MCP protocol compliance. Tool pagination — для данных.

### Validation — Pydantic Field constraints

MCP tools валидируют через Pydantic `Field()` constraints прямо в параметрах:

```python
@tool
async def filter_tracks(
    bpm_min: float | None = Field(None, ge=20, le=300, description="Minimum BPM"),
    bpm_max: float | None = Field(None, ge=20, le=300, description="Maximum BPM"),
    energy_min: float | None = Field(None, ge=0, le=1, description="Minimum energy"),
    sort_by: Literal["bpm", "title", "energy", "id"] = "id",
    limit: int = Field(20, ge=1, le=100),
    cursor: str | None = None,
    service: TrackService = Depends(get_track_service),  # hidden
) -> CursorPage[TrackBrief]:
    ...
```

Для сложных фильтров — Pydantic model с `extra="forbid"`:

```python
class TrackFilterParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm_min: float | None = Field(None, ge=20, le=300)
    bpm_max: float | None = Field(None, ge=20, le=300)
    key: str | None = None
    energy_min: float | None = Field(None, ge=0, le=1)
```

### Sorting — enum + direction

```python
class SortField(StrEnum):
    BPM = "bpm"
    TITLE = "title"
    ENERGY = "energy"
    CREATED_AT = "created_at"
    ID = "id"

class SortDir(StrEnum):
    ASC = "asc"
    DESC = "desc"
```

Repository принимает `sort_by: SortField` + `sort_dir: SortDir` и маппит на SQLAlchemy `order_by()`.

### Filtering — в Repository layer

```python
# repositories/track/filtering.py
async def filter_advanced(
    self, *,
    bpm_range: tuple[float, float] | None = None,
    key_code: int | None = None,
    energy_range: tuple[float, float] | None = None,
    has_features: bool | None = None,
    exclude_set_id: int | None = None,
    sort_by: SortField = SortField.ID,
    sort_dir: SortDir = SortDir.ASC,
    limit: int = 20,
    cursor: str | None = None,
) -> CursorPage[TrackSchema]:
    ...
```

**Принцип:** Tool → Service → Repository. Фильтрация в SQL (Repository), не в Python (Service).

---

## SOLID

| Принцип | Как |
|---------|-----|
| S | Каждый сервис = один use case |
| O | Analyzers/Templates через Registry |
| L | Protocol-порты = substituability |
| I | Split Protocols по необходимости |
| D | Services -> Protocol ports <- Infrastructure |

---

## Дедупликация

| Дубликат | Решение |
|----------|---------|
| `build_ym_client()` x2 | Одна фабрика в di/external.py |
| `_classify_mood` x2 | Делегирование к MoodClassifier |
| `resolve_track_refs` x2 | Единый helper |
| Ghost directories x6 | Удалить |
| `templates.py` resources x2 | Объединить |

---

## Миграция: фазы

| # | Фаза | Описание |
|---|------|----------|
| 0 | Setup | `src/dj_music/`, pyproject.toml, import-linter |
| 1 | core/ | config split, errors, constants, camelot, utils, logging |
| 2a | schemas/ | Entity-First: Entity + DTO + Filter + Validator для всех доменов |
| 2b | domain logic | transition/, optimization/, export/, templates/, audio domain |
| 3 | repositories/ports.py | Protocol interfaces |
| 4 | services/ | services переезжают, убираем ORM imports |
| 5 | services/workflows/ | workflows переезжают в services/workflows/ |
| 6 | models/ + repositories/ | db/models/ → models/, db/repositories/ → repositories/, db/session → repositories/session |
| 7 | engines/ + ym/ + audio/ | engines, ym, audio переезжают на top-level |
| 8 | tools/ + api/ + bootstrap/ | controllers/tools/ → tools/, api/ stays, bootstrap/ + di/ |
| 9 | middleware/ + cleanup | middleware/ на top-level, ghost dirs, shims, docs, CLAUDE.md |

Каждая фаза — отдельный PR с re-export shims для backward compatibility.

---

## ⚠️ ОБЯЗАТЕЛЬНАЯ документация FastMCP — изучить ПЕРЕД реализацией

Полный sitemap: https://gofastmcp.com/llms.txt
Полная документация: https://gofastmcp.com/llms-full.txt

**ВСЕ ссылки ниже ОБЯЗАТЕЛЬНЫ для изучения перед выполнением соответствующей фазы.**

### Phase 0 — Setup

| Документ | URL | Зачем |
|----------|-----|-------|
| Welcome | https://gofastmcp.com/getting-started/welcome | Обзор FastMCP 3.x |
| Installation | https://gofastmcp.com/getting-started/installation | Версии, зависимости |
| Quickstart | https://gofastmcp.com/getting-started/quickstart | Базовые паттерны |
| Settings | https://gofastmcp.com/more/settings | Все настройки FastMCP |
| Project Configuration | https://gofastmcp.com/deployment/server-configuration | pyproject.toml / конфигурация |

### Phase 1 — core/

| Документ | URL | Зачем |
|----------|-----|-------|
| OpenTelemetry | https://gofastmcp.com/servers/telemetry | Интеграция OTEL traces |
| Client Logging | https://gofastmcp.com/servers/logging | Логирование ctx.info/warning/error |

### Phase 2 — domain/

| Документ | URL | Зачем |
|----------|-----|-------|
| Prompts | https://gofastmcp.com/servers/prompts | Standalone @prompt паттерн |
| Resources & Templates | https://gofastmcp.com/servers/resources | @resource, ResourceResult |

### Phase 3+4 — application/

| Документ | URL | Зачем |
|----------|-----|-------|
| Dependency Injection | https://gofastmcp.com/servers/dependency-injection | Depends(), DI chain |
| MCP Context | https://gofastmcp.com/servers/context | ctx.info, ctx.report_progress, ctx.sample |
| Progress Reporting | https://gofastmcp.com/servers/progress | Отслеживание прогресса long tools |
| User Elicitation | https://gofastmcp.com/servers/elicitation | ctx.elicit() для user input |
| Sampling | https://gofastmcp.com/servers/sampling | LLM sampling fallback |
| Background Tasks | https://gofastmcp.com/servers/tasks | Docket tasks, task=True |

### Phase 6 — infrastructure/

| Документ | URL | Зачем |
|----------|-----|-------|
| Storage Backends | https://gofastmcp.com/servers/storage-backends | Backend для state persistence |
| Lifespans | https://gofastmcp.com/servers/lifespan | @lifespan, composition operator `\|` |

### Phase 8 — presentation/

| Документ | URL | Зачем |
|----------|-----|-------|
| The FastMCP Server | https://gofastmcp.com/servers/server | FastMCP() конструктор, все опции |
| Tools | https://gofastmcp.com/servers/tools | @tool, ToolResult, structuredContent |
| Middleware | https://gofastmcp.com/servers/middleware | Middleware chain, порядок |
| Pagination | https://gofastmcp.com/servers/pagination | list_page_size, cursor pagination |
| Component Visibility | https://gofastmcp.com/servers/visibility | enable_components, hidden/visible |
| Versioning | https://gofastmcp.com/servers/versioning | API versioning |
| Icons | https://gofastmcp.com/servers/icons | Tool icons |
| Composing Servers | https://gofastmcp.com/servers/composition | mount(), namespace, import_server |
| Testing | https://gofastmcp.com/servers/testing | Client fixture, in-memory testing |

### Phase 8 — presentation/mcp/ (Providers & Transforms)

| Документ | URL | Зачем |
|----------|-----|-------|
| Providers Overview | https://gofastmcp.com/servers/providers/overview | Provider architecture |
| Filesystem Provider | https://gofastmcp.com/servers/providers/filesystem | FileSystemProvider auto-discovery |
| Local Provider | https://gofastmcp.com/servers/providers/local | @mcp.tool direct registration |
| MCP Proxy Provider | https://gofastmcp.com/servers/providers/proxy | Proxy to remote MCP |
| Custom Providers | https://gofastmcp.com/servers/providers/custom | Custom component providers |
| Skills Provider | https://gofastmcp.com/servers/providers/skills | SkillsDirectoryProvider |
| Transforms Overview | https://gofastmcp.com/servers/transforms/transforms | Transform pipeline |
| Tool Transformation | https://gofastmcp.com/servers/transforms/tool-transformation | Modify tool schemas |
| Namespace Transform | https://gofastmcp.com/servers/transforms/namespace | Prefix naming |
| Tool Search | https://gofastmcp.com/servers/transforms/tool-search | Tool search transform |
| Prompts as Tools | https://gofastmcp.com/servers/transforms/prompts-as-tools | P->T transform |
| Resources as Tools | https://gofastmcp.com/servers/transforms/resources-as-tools | R->T transform |
| Code Mode | https://gofastmcp.com/servers/transforms/code-mode | Code execution mode |

### Phase 8 — api/ (Deployment)

| Документ | URL | Зачем |
|----------|-----|-------|
| Running Your Server | https://gofastmcp.com/deployment/running-server | stdio vs HTTP |
| HTTP Deployment | https://gofastmcp.com/deployment/http | StreamableHTTP, ASGI mount |
| FastAPI Integration | https://gofastmcp.com/integrations/fastapi | FastAPI + MCP mount |
| Claude Code Integration | https://gofastmcp.com/integrations/claude-code | .mcp.json config |
| MCP JSON Configuration | https://gofastmcp.com/integrations/mcp-json-configuration | JSON config format |

### Phase 8 — presentation/ (Auth, если потребуется)

| Документ | URL | Зачем |
|----------|-----|-------|
| Authentication | https://gofastmcp.com/servers/auth/authentication | Auth overview |
| Authorization | https://gofastmcp.com/servers/authorization | Permission model |
| Token Verification | https://gofastmcp.com/servers/auth/token-verification | JWT/token verify |
| Supabase Integration | https://gofastmcp.com/integrations/supabase | Supabase auth |

### Phase 9 — Cleanup (Client, CLI)

| Документ | URL | Зачем |
|----------|-----|-------|
| The FastMCP Client | https://gofastmcp.com/clients/client | Client API |
| Client Transports | https://gofastmcp.com/clients/transports | stdio/HTTP transports |
| Calling Tools | https://gofastmcp.com/clients/tools | Tool invocation |
| CLI Overview | https://gofastmcp.com/cli/overview | fastmcp CLI |
| Running Servers | https://gofastmcp.com/cli/running | fastmcp run/dev |
| Inspecting Servers | https://gofastmcp.com/cli/inspecting | fastmcp list/inspect |

### Apps (если потребуется)

| Документ | URL | Зачем |
|----------|-----|-------|
| Apps Overview | https://gofastmcp.com/apps/overview | MCP Apps architecture |
| Apps Quickstart | https://gofastmcp.com/apps/quickstart | Building apps |
| Prefab UI | https://gofastmcp.com/apps/prefab | Pre-built UI components |
| Patterns | https://gofastmcp.com/apps/patterns | Common app patterns |

---

## Сквозной Data Flow — build_set пример

Полный путь запроса через все слои (проверка целостности):

```text
CLIENT
  ↓ MCP Protocol (stdio / StreamableHTTP)
MIDDLEWARE (onion):
  RequestIdMiddleware     → uuid → contextvars
  LoggingMiddleware       → "build_set started"
  ErrorHandlingMiddleware → try/catch
  RateLimitingMiddleware  → token bucket
  ResponseLimitingMiddleware → size guard
  ↓
PRESENTATION (mcp/tools/sets.py):
  @tool build_set(playlist_id, template, service=Depends(...), ctx=CurrentContext())
  - Pydantic validation на входе
  - Вызывает service.build(...)
  ↓
DI RESOLUTION (di/services.py → di/repos.py → di/db.py):
  get_db_session() → AsyncSession (shared)
  get_track_repo(session) → SqlAlchemyTrackRepo(session)
  get_set_repo(session) → SqlAlchemySetRepo(session)
  get_set_service(repos...) → SetService(protocols...)
  ↓
APPLICATION (services/set_builder.py):
  SetService.build()
  - Загрузка через Protocol ports (не знает об ORM)
  - Получает Pydantic entities (Track, TrackFeatures)
  - Вызывает domain optimizer
  ↓
DOMAIN (optimization/genetic.py + transition/scorer.py):
  GeneticAlgorithm.optimize(tracks, scorer, template)
  - Pure: list[TrackFeatures] → OptimizationResult
  - ZERO I/O, ZERO framework deps
  ↓
APPLICATION (back in set_builder.py):
  - Persists через repos (flush, не commit)
  - Returns SetSummary (Pydantic DTO)
  ↓
PRESENTATION (back in tool):
  - DTO → FastMCP structuredContent + content
  ↓
DI CLEANUP (di/db.py):
  - SUCCESS → session.commit()
  - ERROR → session.rollback()
  - ALWAYS → session.close()
  ↓
MIDDLEWARE (reverse):
  ResponseLimiting → truncate if > 500KB
  ErrorHandler → if exception: ToolError + Sentry
  Logging → "build_set completed 3.2s ok"
  ↓
CLIENT
```

### Ключевые инварианты этого flow:

1. **Один session на весь call** — все repos на shared session → UoW
2. **Domain = pure** — optimizer и scorer не знают о DB/HTTP/MCP
3. **Services видят только Protocol** — не знают что под капотом SQLAlchemy
4. **Schemas = single source** — repos конвертируют ORM → Schema перед return
5. **Commit/rollback в DI** — ни service, ни repo не делают commit
6. **Middleware = cross-cutting** — logging, errors, rate limit без кода в tools
7. **contextvars** — request_id propagates через все слои автоматически

---

## Разрешённые конфликты спеки

| Конфликт | Решение |
|----------|---------|
| BaseEntity location | `schemas/base.py` = canonical. `core/types.py` удалён — base classes в schemas/ |
| TrackFeatures в schemas/audio.py И transition/model.py | Canonical в `schemas/audio.py`. `transition/` импортирует оттуда |
| entities/ vs schemas/ | Один пакет `schemas/` — Entity-First architecture. `entities/` удалён |
| SortField/SortDir — в каком слое? | `core/constants.py` — cross-cutting enums, доступны всем |

---

## Что НЕ меняется

- Бизнес-логика (scoring, optimization, audio analysis)
- MCP tool API (названия, параметры, возвращаемые типы)
- REST API endpoints
- DB schema и миграции
- Panel (Next.js)
- FastMCP patterns (FileSystemProvider, @tool, Depends)

---

## Метрики успеха

| Метрика | До | После |
|---------|-----|-------|
| God-files (>400 LOC) | 4 | 2 (deferred) |
| Ghost directories | 6 | 0 |
| ORM imports in services | 21 | 0 (services use domain entities only) |
| Import-linter contracts | 6 | 5 (stricter) |
| Config files | 1 (100+ fields) | 6 (15-20 each) |
| Duplicate code | 3+ | 0 |

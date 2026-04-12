# Clean Architecture Refactoring — Design Spec

> Полная перестройка dj-music-plugin из flat monolith в Modular Monolith с Clean Architecture.

## Проблема

Текущий проект (~304 Python файла, ~28.6K LOC без миграций):

1. **Flat monolith** — 18 пакетов на одном уровне в `app/` без bounded contexts
2. **Три слоя данных без границ** — `db/models/` (ORM), `entities/` (dataclass), `schemas/` (Pydantic) пересекаются
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
| Domain entities | Да (Pydantic BaseModel) | Сервисы не знают об ORM. Pydantic = валидация + сериализация |
| Mapper | `from_attributes=True` | `Entity.model_validate(orm_obj)` — Pydantic маппит автоматически |
| Ports (Protocol) | Да, на границах | Repositories + YM client + Cache |
| Config split | Да, по доменам | Решает god-object |
| FileSystemProvider | `presentation/mcp/` | Одна строка в server_builder |

---

## Целевая архитектура

### 6 слоёв

```text
src/dj_music/
├── kernel/           # Shared Kernel — 0 зависимостей
├── domain/           # Domain Layer — чистая логика
├── application/      # Application Layer — use cases, порты, DTO
├── infrastructure/   # Infrastructure Layer — DB, YM, audio I/O
├── engines/          # Runtime engines — long-lived state
└── presentation/     # Presentation Layer — MCP tools, REST API, DI
```

### Dependency Rule

```text
presentation --> application --> domain <-- infrastructure
                    ^                        |
                    +-------- ports <--------+

kernel <-- все слои (cross-cutting)
engines --> domain + kernel
```

### Компоненты (из скетча пользователя)

```text
PRESENTATION:
  Tool (Controller) --> Schema --> Service
  Prompt --> Tool
  Resource --> Tool

APPLICATION:
  Service --> Repository (via Port)
  Schema --> Validator
  CRUD операции

DOMAIN:
  Entity (dataclass) + Types
  Transition scoring, Optimization, Export

INFRASTRUCTURE:
  Model (ORM) --> Repository (implementation)
  Audio --> Pipeline
  YM Client --> Rate Limit

KERNEL (Core):
  Config, Error, Middleware, Logging, Monitoring
  Util --> Time, UUID
```

---

## Детальная структура

### 1. kernel/ — Shared Kernel

```text
src/dj_music/kernel/
├── __init__.py
├── types.py                 # BaseEntity(BaseModel, from_attributes=True, extra="forbid")
│                            # BaseValueObject(BaseModel, frozen=True)
│                            # Все entities и VOs наследуют от этих двух базовых классов
├── errors.py                # DJMusicError hierarchy
├── constants.py             # Enums, domain constants
├── camelot.py               # Camelot wheel pure math
├── config/
│   ├── __init__.py          # Composite Settings facade
│   ├── base.py              # BaseSettings
│   ├── audio.py             # AudioSettings
│   ├── scoring.py           # ScoringSettings
│   ├── ym.py                # YandexMusicSettings
│   ├── server.py            # ServerSettings
│   └── db.py                # DatabaseSettings
└── utils/
    ├── time.py, parsing.py, cache.py, files.py, pagination.py
```

### 2. domain/ — Domain Layer

Чистая бизнес-логика. Зависит только от kernel. Ни SQLAlchemy, ни httpx, ни FastMCP.

**Сервисы работают ТОЛЬКО с domain entities (Pydantic BaseModel), никогда с ORM моделями.**
Repository конвертирует ORM → Pydantic через `Entity.model_validate(orm_obj)` (from_attributes=True).

**Единая модель данных — Pydantic everywhere:**
- Entity = Pydantic BaseModel с `ConfigDict(from_attributes=True)` — маппинг из ORM автоматический
- Value Object = Pydantic BaseModel с `ConfigDict(frozen=True)` — immutable
- Schema (DTO) = Pydantic BaseModel (TrackBrief, SetSummary) — для tool returns
- Config = pydantic-settings BaseSettings — конфигурация
- Никаких dataclasses — всё Pydantic

**Ключевые Pydantic v2 возможности:**
- `from_attributes=True` — автоматический маппинг ORM → entity (заменяет Mapper)
- `frozen=True` — immutable Value Objects (Bpm, Key, Lufs)
- `computed_field` — вычисляемые свойства (camelot из key_code)
- `field_validator` / `model_validator` — бизнес-правила прямо в entity
- `Field(ge=20, le=300)` — constraint validation без CheckConstraint
- `model_dump(include/exclude)` — гибкая сериализация для brief/full views
- `Discriminator` — discriminated unions для полиморфных типов
- `TypeAdapter` — валидация standalone типов (list, dict)

```text
src/dj_music/domain/
├── entities/                    # Domain entities (Pydantic BaseModel)
│   ├── __init__.py
│   ├── base.py                  # BaseEntity (id + timestamps), BaseValueObject (frozen)
│   ├── track.py                 # Track, Artist, Genre, Label, Release
│   ├── audio.py                 # TrackFeatures, AudioFeatures, Embedding
│   ├── playlist.py              # Playlist, PlaylistItem
│   ├── set.py                   # DjSet, SetVersion, SetItem, SetConstraint, SetFeedback
│   ├── transition.py            # Transition, TransitionCandidate
│   ├── library.py               # LibraryItem, Beatgrid, CuePoint, SavedLoop
│   ├── platform.py              # YandexMetadata, SpotifyMetadata, etc.
│   └── export.py                # AppExport
│   # Pydantic дает: field_validator, model_validator, .model_dump(),
│   # ConfigDict(frozen=True) для VOs, Annotated[float, Field(ge=0, le=1)]
│
├── audio/
│   ├── model.py             # AudioSignal, AnalyzerResult
│   ├── context.py           # AnalysisContext
│   ├── dsp/                 # Pure DSP (spectral, rhythm, tonal, framing)
│   ├── analyzers/           # 18 analyzers (Registry pattern)
│   │   ├── base.py          # BaseAnalyzer ABC + AnalyzerRegistry
│   │   ├── bpm.py, beat.py, key.py, loudness.py, spectral.py
│   │   ├── energy.py, mfcc.py, structure.py, tonnetz.py
│   │   ├── tempogram.py, phrase.py, bpm_histogram.py
│   │   └── (essentia): beats_loudness, danceability, dissonance, etc.
│   ├── classification/      # MoodClassifier + profiles
│   └── quality/             # Audit rules
│
├── transition/              # Transition scoring (already pure)
│   ├── model.py             # TransitionScore, TrackFeatures
│   ├── scorer.py            # TransitionScorer (~140 LOC)
│   ├── components/          # bpm, harmonic, energy, spectral, groove, timbral
│   ├── constraints.py, intent.py, style.py
│   ├── recipe.py, recipe_engine.py
│   ├── section_context.py, subgenre_rules.py, weights.py, math.py
│
├── optimization/            # GA, greedy, fitness (already pure)
│   ├── protocol.py, fitness.py, genetic.py, greedy.py, result.py
│
├── export/                  # Pure writers (no I/O)
│   ├── model.py             # ExportTrack, ExportTransition DTOs
│   ├── m3u8.py, rekordbox.py, json_guide.py, cheatsheet.py
│
├── templates/               # Set templates (pure data)
│   ├── model.py, registry.py
│
├── narrative/               # Set narrative engine
│   └── engine.py
│
└── mix_point/               # Mix-point detection (pure math)
    └── detector.py
```

### 3. application/ — Application Layer

```text
src/dj_music/application/
├── ports/                   # Protocol interfaces (return domain entities, not ORM)
│   ├── repositories.py      # All repository Protocols (return Pydantic entities)
│   ├── music_provider.py    # MusicProvider Protocol (YM abstraction)
│   ├── audio_storage.py     # TimeseriesStorage Protocol
│   └── cache.py             # TransitionCache Protocol
│
├── services/                # Use cases (flat with prefixes)
│   ├── track.py, playlist.py, search.py, metadata.py
│   ├── audio_analysis.py, tiered_pipeline.py
│   ├── set_builder.py, set_scoring.py, set_crud.py
│   ├── set_cheatsheet.py, set_facade.py
│   ├── reasoning.py, delivery.py, discovery.py
│   ├── import_.py, sync.py, export.py
│   ├── curation.py, curation_mood.py, curation_audit.py, curation_distribution.py
│   ├── embedding.py, candidate.py
│   ├── transition.py, transition_cache.py, transition_history.py
│   ├── optimizer.py, adaptive_arc.py, mix_point.py
│   ├── affinity.py, feedback.py, background_tasks.py
│
├── workflows/               # Multi-step orchestrators
│   ├── analyze_track.py, build_set.py, deliver_set.py
│   ├── import_tracks.py, sync_playlist.py
│
└── dto/                     # Pydantic DTOs (replaces app/schemas/)
    ├── track.py, playlist.py, set.py, transition.py
    ├── common.py, yandex.py, deck.py, mixer.py
```

### 4. infrastructure/ — Infrastructure Layer

```text
src/dj_music/infrastructure/
├── persistence/
│   ├── session.py           # async_session_factory
│   ├── seed.py              # Reference data
│   ├── models/              # 44 SQLAlchemy ORM models
│   │   ├── base.py, track.py, audio.py, playlist.py, set.py
│   │   ├── transition.py, platform.py, library.py, key.py
│   │   ├── export.py, ingestion.py, feedback.py, scoring_profile.py
│   ├── repositories/        # Concrete repos (ORM -> Pydantic entity via model_validate)
│   │   #
│   │   # BaseRepository[TModel, TEntity] — Generic base class:
│   │   #   - TModel = SQLAlchemy ORM model
│   │   #   - TEntity = Pydantic domain entity
│   │   #   - CRUD бесплатно: get_by_id, list_all, create, update, delete
│   │   #   - Маппинг: entity_class.model_validate(orm_obj) / entity.model_dump()
│   │   #   - Cursor pagination через _paginate()
│   │   #
│   │   # SQLAlchemy 2.0 паттерны:
│   │   #   - selectinload() перед model_validate() для relationships
│   │   #   - load_only() для heavy entities (TrackFeatures 80+ полей)
│   │   #   - WriteOnlyMapped для больших коллекций (track_sections 108K строк)
│   │   #   - expire_on_commit=False в async sessions
│   │   #   - flush() never commit() — commit на уровне DI
│   │   #
│   │   # НЕТ BaseService — сервисы используют composition, не inheritance
│   │   #
│   │   ├── base.py              # BaseRepository[TModel, TEntity]
│   │   ├── unit_of_work.py
│   │   ├── track/ (core, filtering, library, external_ids, stats)
│   │   ├── playlist.py, set.py, feature.py, audio.py
│   │   ├── transition.py, candidate.py, embedding.py, export.py
│   │   ├── ingestion.py, metadata.py, transition_history.py
│   │   └── track_affinity.py, track_feedback.py
│   └── migrations/
│
├── yandex_music/            # YM adapter (implements MusicProvider port)
│   ├── client.py, models.py, rate_limiter.py, filters.py
│
├── storage/
│   ├── factory.py, transition_cache.py
│
├── audio/                   # Audio I/O adapters
│   ├── loader.py, pipeline.py (668 LOC), temp_download.py, timeseries.py
│
└── observability/
    ├── sentry.py, telemetry.py
```

### 5. engines/

```text
src/dj_music/engines/
├── base.py
├── deck/ (engine.py, state.py)
├── mixer/ (engine.py)
└── lifespan.py
```

### 6. presentation/

```text
src/dj_music/presentation/
├── mcp/                     # FastMCP server (FileSystemProvider scans here)
│   ├── server.py            # build_mcp_server()
│   ├── tools/               # @tool handlers
│   │   ├── _shared/ (taxonomy, context, dispatch, entity_resolver, resolvers, errors)
│   │   ├── tracks.py, playlists.py, sets.py, search.py, reasoning.py
│   │   ├── audio.py, audio_atomic.py, curation.py, delivery.py
│   │   ├── discovery.py, import_download.py, sync.py, admin.py
│   │   ├── monitoring.py, decks.py, mixer.py, feedback tools
│   │   └── yandex/ (search, tracks, albums, playlists, likes)
│   ├── resources/
│   ├── prompts/
│   ├── middleware/
│   └── schemas/
│
├── http/                    # FastAPI REST wrapper
│   ├── server.py, state.py, lifespan.py, openapi.py, schemas.py
│   ├── routes/ (health, discovery, execution, audio)
│   └── services/ (tool_registry, signed_url_cache, ym_audio_proxy)
│
├── bootstrap/               # Server assembly
│   ├── server_builder.py, lifespans.py, transforms.py
│   ├── middleware.py, visibility.py, observability.py, sampling.py
│
└── di/                      # Dependency Injection — composition root
    ├── db.py, repos.py, services.py, audio.py, external.py, uow.py
```

---

## Import-Linter контракты

```ini
[importlinter]
root_packages = dj_music

# 1. Domain must be pure
[importlinter:contract:domain-pure]
name = Domain must have no external dependencies
type = forbidden
source_modules = dj_music.domain
forbidden_modules =
    dj_music.application
    dj_music.infrastructure
    dj_music.presentation
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
    dj_music.application.services
    dj_music.application.workflows
forbidden_modules =
    dj_music.infrastructure
    dj_music.presentation
    sqlalchemy
    httpx
    fastmcp

# 3. Kernel is a leaf
[importlinter:contract:kernel-leaf]
name = Kernel must not depend on any app layer
type = forbidden
source_modules = dj_music.kernel
forbidden_modules =
    dj_music.domain
    dj_music.application
    dj_music.infrastructure
    dj_music.presentation
    dj_music.engines

# 4. Presentation tools must not access infra directly
[importlinter:contract:presentation-no-infra]
name = Presentation depends on application not infrastructure
type = forbidden
source_modules =
    dj_music.presentation.mcp.tools
    dj_music.presentation.mcp.resources
    dj_music.presentation.mcp.prompts
forbidden_modules =
    dj_music.infrastructure.persistence.models
    dj_music.infrastructure.persistence.repositories

# 5. Engines must not depend on transport
[importlinter:contract:engines-no-transport]
name = Engines must not depend on presentation or infra IO
type = forbidden
source_modules = dj_music.engines
forbidden_modules =
    dj_music.presentation
    dj_music.infrastructure.yandex_music
    dj_music.infrastructure.persistence
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
├── kernel/
│   ├── errors.py            # DJMusicError hierarchy с ctx + get_context_chain()
│   └── logging.py           # structlog configuration, processor chain, setup_logging()
│
├── infrastructure/
│   └── observability/
│       ├── sentry.py        # Sentry DSN init, SentryProcessor
│       └── telemetry.py     # OTEL traces (optional)
│
└── presentation/
    ├── mcp/
    │   └── middleware/
    │       ├── request_id.py    # RequestID → contextvars
    │       ├── logging.py       # Access log middleware
    │       ├── error_handler.py # Exception → ToolError conversion
    │       └── rate_limit.py    # Rate limiting
    └── http/
        └── middleware similarly
```

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
| Port/Adapter | application/ports/ | Инверсия зависимостей |
| Abstract Factory | di/ | Composition root |

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
| 1 | kernel/ | config split, errors, constants, camelot, utils |
| 2a | domain/entities/ | Dataclass entities для Track, Set, Playlist, Transition, etc. |
| 2b | domain/ | transition/, optimization/, export/, templates/, audio domain |
| 3 | application/ports/ | Protocol interfaces |
| 4 | application/services/ | services переезжают |
| 5 | application/workflows+dto/ | workflows/, schemas/ -> dto/ |
| 6 | infrastructure/ | db/ -> persistence/, ym/ -> yandex_music/, audio I/O |
| 7 | engines/ | engines переезжают |
| 8 | presentation/ | controllers/ -> mcp/, api/ -> http/, bootstrap/, di/ |
| 9 | Cleanup | ghost dirs, shims, docs |

Каждая фаза — отдельный PR с re-export shims для backward compatibility.

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

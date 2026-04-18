# Архитектурный аудит и каноничная многослойная архитектура

> Дата: 2026-04-07
> Автор: Claude (deep architectural review)
> Скоуп: `app/`, `panel/`, `serve_http.py`, `scripts/`, `tests/`
> Цель: собрать полную карту проекта, выявить смешения слоёв и дубликаты, спроектировать каноничную Clean/Hexagonal архитектуру с строгим разделением ответственностей.

---

## 0. TL;DR

Проект уже на 70% соответствует Clean Architecture, но застрял в середине рефакторинга:

- **`core/`** превращается в shared kernel, но всё ещё хранит инфраструктурные шимы (`storage.py`, `seed.py`, `elicitation.py` — 8 строк каждый, реэкспорт).
- **`domain/`** появилась как чистая бизнес-логика (transition, optimization, templates, export, audit) — но `services/*.py` шимы (`transition.py`, `optimizer.py`, `export.py`, `templates.py`) ещё указывают туда.
- **`services/`** одновременно содержит 13 плоских классов и 2 sub-package (`set/`, `curation/`) с фасадами — асимметрия.
- **MCP tools** в 4 местах прыгают мимо services: импортируют `repositories`, `audio`, `models`, `domain` напрямую.
- **`domain/`** в 3 местах ссылается на `app.config` (`audit/rules.py`, `transition/scorer.py`, `optimization/genetic.py`) — нарушение Dependency Rule (доменный слой не должен знать про инфраструктурный конфиг).
- **Каноничная цель**: 5 явных слоёв — **Domain → Application → Infrastructure → Integration → Interface (Adapters)** — с явными портами, конфиг-инъекцией в домен через value objects, и единым правилом «зависимость только вниз».

Полный план миграции — в разделе 11.

---

## 1. Карта проекта (что есть сейчас)

### 1.1 Корневая структура

```text
dj-music-plugin/
├── app/                       ← Python backend (23 651 LOC)
│   ├── __init__.py
│   ├── config.py              ← pydantic-settings, env vars
│   ├── server.py              ← FastMCP entrypoint
│   ├── audio/                 ← Аудио-анализ (2 + 21 + 6 + 3 файлов)
│   ├── core/                  ← Shared kernel (14 файлов, 1 175 LOC)
│   ├── domain/                ← Чистая доменная логика (5 sub-package, 1 964 LOC)
│   ├── infrastructure/        ← Адаптеры I/O (2 файла, неполный)
│   ├── mcp/                   ← MCP-адаптер (tools, resources, prompts, schemas)
│   ├── migrations/            ← Alembic
│   ├── models/                ← SQLAlchemy ORM (12 файлов, 1 328 LOC)
│   ├── repositories/          ← Data access (12 файлов + sub-package track/, 1 682 LOC)
│   ├── services/              ← Use cases (23 + sub: set/, curation/ — 5 041 LOC)
│   ├── utils/                 ← Утилиты (3 файла, time/io)
│   └── ym/                    ← Yandex Music HTTP-клиент (4 файла)
│
├── panel/                     ← Next.js 16 dashboard (отдельный мир)
│   ├── app/                   ← Pages (SSR)
│   ├── actions/               ← Server actions → MCP REST API
│   ├── lib/queries/           ← Прямые SQL к Supabase
│   └── components/            ← shadcn UI
│
├── serve_http.py              ← FastAPI обёртка над FastMCP
├── fastmcp.json               ← FastMCP манифест
├── start.sh                   ← dev all-in-one
├── docs/                      ← Документация (architecture, glossary, …)
├── scripts/                   ← Бенчмарки и проверки
├── tests/                     ← pytest (in-memory SQLite)
└── .claude-plugin/plugin.json ← Plugin manifest (mcp + db servers)
```

### 1.2 Размеры по слоям (LOC, без `__pycache__`)

| Слой | Файлы | LOC | Доля |
|------|------:|----:|-----:|
| `app/services/` | 25 | 5 041 | 21 % |
| `app/mcp/tools/` | 18 (+ shared, yandex) | 3 402 | 14 % |
| `app/audio/` | 32 | 2 800 | 12 % |
| `app/domain/` | 21 | 1 964 | 8 % |
| `app/repositories/` | 17 | 1 682 | 7 % |
| `app/models/` | 12 | 1 328 | 6 % |
| `app/core/` | 19 | 1 175 | 5 % |
| `app/migrations/versions/` | 11 | ~1 200 | 5 % |
| `app/mcp/prompts/`, `resources/`, `schemas/` | 8 | ~1 100 | 5 % |
| `app/ym/` | 4 | ~750 | 3 % |
| `app/utils/`, `infrastructure/` | 5 | ~250 | 1 % |
| **Итого `app/`** | **172** | **~23 650** | 100 % |

### 1.3 Граф зависимостей (`from app.*` импорты)

Глобальная статистика «кто из меня импортирует» по топ-уровневым пакетам:

| Импортируемый модуль | Сколько раз импортируется (всего) |
|----------------------|----------------------------------:|
| `app.core` | 84 |
| `app.repositories` | 82 |
| `app.models` | 73 |
| `app.audio` | 69 (но 58 — внутри самого audio/) |
| `app.domain` | 56 (31 — внутри domain/) |
| `app.mcp` | 52 (48 — внутри mcp/) |
| `app.services` | 49 |
| `app.config` | 21 |
| `app.ym` | 12 |
| `app.utils` | 5 |
| `app.infrastructure` | 2 |

**Per-layer срез:**

```text
services/       →  repositories(53)  core(34)  domain(24)  models(17)  services(13)
                   config(5)  audio(5)  ym(3)
mcp/tools/      →  mcp(48)  services(21)  core(20)  ym(6)  repositories(4)
                   audio(4)  config(3)  utils(1)  models(1)  domain(1)
domain/         →  domain(31)  core(8)  config(3)  ← ❌ ЛИК
audio/          →  audio(58)  config(4)  core(3)
```

---

## 2. Семантическая классификация модулей

Мне нужно сгруппировать всё содержимое `app/` не по тому, *где оно лежит*, а по тому, *чем оно по природе является*. Это даст истинную карту слоёв.

### 2.1 Pure Domain (бизнес-логика, framework-free)

Эти модули не должны импортировать ничего из `sqlalchemy`, `fastmcp`, `httpx`, `app.config`.

| Модуль | Характер |
|--------|----------|
| `core/camelot.py` | Value Object: Camelot wheel, distance algebra |
| `core/track_features.py` | Value Object: TrackFeatures dataclass + `from_db` factory |
| `core/transition_intent.py` | Enum: TransitionIntent |
| `core/constants.py` | Domain constants (BPM range, key codes, subgenres) |
| `core/parsing.py` | Pure parsers (cue points, time formats) |
| `core/ym_filters.py` | Domain predicates над треками |
| `core/errors.py` | Error hierarchy (NotFound, Validation, Conflict) |
| `domain/transition/scorer.py` | TransitionScorer (6-component formula) |
| `domain/transition/math_helpers.py` | Pure math (sigmoid, cosine sim) |
| `domain/optimization/fitness.py` | Fitness function |
| `domain/optimization/genetic.py` | GA-оптимизатор |
| `domain/optimization/greedy.py` | Greedy chain builder |
| `domain/optimization/result.py` | OptimizationResult VO |
| `domain/optimization/protocol.py` | Optimizer Protocol (= Strategy) |
| `domain/templates/models.py` | SetTemplate, TemplateSlot |
| `domain/templates/registry.py` | Static template registry |
| `domain/audit/rules.py` | Audit rules (techno quality criteria) |
| `domain/export/models.py` | ExportTrack, ExportTransition VOs |
| `domain/export/m3u8_writer.py` | M3U8 serializer (pure!) |
| `domain/export/json_writer.py` | JSON guide serializer |
| `domain/export/cheatsheet_writer.py` | Cheat sheet serializer |
| `domain/export/rekordbox_writer.py` | Rekordbox XML serializer |
| `audio/classification/profiles.py` | Subgenre weight profiles |
| `audio/classification/classifier.py` | MoodClassifier (rule-based, pure) |

> Все экспорт-«райтеры» сейчас лежат в `domain/export/`, но они производят строки/файлы — это формально на границе. Поскольку они **детерминированы**, **не делают I/O** (только формируют контент), а I/O делает `DeliveryService`, — это всё ещё чистый domain (как сериализатор JSON).

### 2.2 Application / Use Cases (оркестрация)

Тонкие классы, которые комбинируют domain + ports. Знают про транзакции через DI-обёртку, но не открывают сессию сами. Возвращают DTO или domain-объекты.

| Модуль | Use case |
|--------|----------|
| `services/track_service.py` | CRUD треков |
| `services/playlist_service.py` | CRUD плейлистов |
| `services/set/crud.py` | CRUD сетов |
| `services/set/builder.py` | build_set / rebuild_set (вызывает GA + Greedy) |
| `services/set/scoring.py` | score_transitions для готового сета |
| `services/set/cheatsheet.py` | Генерация cheat sheet |
| `services/set/facade.py` | SetService = Facade перед 4 sub-сервисами |
| `services/curation/mood.py` | classify_mood |
| `services/curation/audit.py` | audit_playlist |
| `services/curation/distribution.py` | distribute_to_subgenres |
| `services/curation/facade.py` | CurationService Facade |
| `services/discovery_service.py` | find_similar_tracks |
| `services/import_service.py` | import_tracks (YM → DB) |
| `services/delivery_service.py` | deliver_set (orchestration: score → write → sync) |
| `services/sync_service.py` | sync_playlist (push/pull/diff) |
| `services/search_service.py` | Универсальный поиск |
| `services/audio_service.py` | analyze_track / analyze_batch |
| `services/tiered_pipeline.py` | L1→L4 dispatcher |
| `services/reasoning_service.py` | suggest_next, explain_transition, find_replacement |
| `services/metadata_service.py` | YM metadata enrichment |
| `services/candidate_service.py` | Candidate pre-filter (BPM/key/energy index) |
| `services/embedding_service.py` | Embedding compute/store |
| `services/transition_cache.py` | LRU cache для TransitionScore |
| `services/background_tasks.py` | FastMCP background-task wrappers |

### 2.3 Infrastructure (Persistence, Cache, Storage)

| Модуль | Назначение |
|--------|-----------|
| `models/*.py` (12 файлов) | SQLAlchemy ORM (44 таблицы) |
| `repositories/*.py` (12 файлов + `track/`) | Data access, flush only |
| `repositories/base.py` | BaseRepository, cursor pagination |
| `migrations/versions/*.py` | Alembic |
| `infrastructure/storage.py` | Storage backend factory (filesystem) |
| `infrastructure/seed.py` | Seed reference data (keys, providers) |
| `core/cache.py` | LRU cache primitive |
| `core/storage.py` ⚠️ | Re-export shim → `infrastructure/storage` |
| `core/seed.py` ⚠️ | Re-export shim → `infrastructure/seed` |
| `audio/timeseries.py` | NPZ frame-data persistence |

### 2.4 Integration (External Services)

| Модуль | Назначение |
|--------|-----------|
| `ym/client.py` | Async YM HTTP клиент |
| `ym/models.py` | YM response Pydantic models |
| `ym/rate_limiter.py` | Token-bucket + exponential backoff |
| `audio/temp_download.py` | Скачать → temp → удалить |
| `audio/analyzers/*.py` (21) | librosa/essentia адаптеры под единый интерфейс |
| `audio/core/loader.py` | Загрузка WAV/MP3 |
| `audio/core/context.py` | AnalysisContext (per-clip кеш STFT) |
| `audio/core/framing.py` | Стiched multi-window clip strategy |
| `audio/core/spectral.py` | Pure DSP примитивы (numpy) |
| `audio/pipeline.py` | Оркестратор анализаторов (Composite + Strategy) |
| `audio/level_config.py` | L1-L4 mapping |

### 2.5 Interface / Adapters (входные)

| Модуль | Тип |
|--------|-----|
| `mcp/tools/*.py` (18) | MCP tools (`@tool`) |
| `mcp/tools/yandex/*.py` (5) | YM-подгруппа |
| `mcp/tools/_shared/*.py` (6) | Tool infra: ToolContext, dispatch, resolvers, taxonomy, errors |
| `mcp/resources/*.py` (3) | MCP resources (`@resource`) |
| `mcp/prompts/workflows.py` | MCP prompts |
| `mcp/schemas/*.py` (2) | Tool-only Pydantic схемы (LLM sampling) |
| `mcp/dependencies.py` | DI-фабрики (`Depends(get_*_service)`) |
| `mcp/elicitation.py` | safe_choice/safe_confirm/safe_elicit |
| `mcp/middleware.py` | Logging, timing, rate-limit, retry, error-mask |
| `server.py` | FastMCP entrypoint, lifespan |
| `serve_http.py` | FastAPI REST wrapper (отдельный файл в корне!) |

### 2.6 Cross-cutting / Shared Kernel

| Модуль | Назначение |
|--------|-----------|
| `config.py` | Settings (singleton, env_prefix=DJ_) |
| `core/pagination.py` | CursorPaginator |
| `core/entity_resolver.py` | id?/query? резолвер |
| `core/schemas/*.py` | Cross-layer Pydantic DTO (track/playlist/set/yandex/common) |
| `utils/time.py` | utc_now, utc_timestamp_iso, sa_now |
| `utils/io.py` | sync I/O helpers |

---

## 3. Зависимости и взаимодействия (что с чем разговаривает)

### 3.1 Здоровые зависимости

```text
mcp/tools  ──► services  ──► repositories  ──► models
                  │
                  ├──► domain  (чистая логика)
                  ├──► audio   (через AudioService)
                  ├──► ym      (через MetadataService / DiscoveryService)
                  └──► core    (shared kernel)

audio/analyzers/* ──► audio/core/* ──► numpy/librosa
audio/pipeline    ──► analyzers + level_config
```

### 3.2 Граф «who calls whom» (топ-стрелки по фактам)

```text
                      ┌────────────────────────────┐
                      │  fastmcp middleware chain  │
                      └──────────────┬─────────────┘
                                     │
       ┌─────────────────────────────┴─────────────────────────────┐
       │                                                           │
       ▼                                                           ▼
┌─────────────┐    ┌──────────────────┐    ┌──────────────┐    ┌──────────┐
│ mcp/tools   │───▶│ mcp/dependencies │───▶│ services     │───▶│ repos    │
│ (50 tools)  │    │ (Depends DI)     │    │ (21 + 4 sub) │    │ (12 + 1) │
└──────┬──────┘    └──────────────────┘    └──┬───────┬───┘    └────┬─────┘
       │                                      │       │             │
       │ ❌ leak (4 файла)                    │       │             ▼
       ▼                                      │       │       ┌──────────┐
┌─────────────┐                               │       │       │ models   │
│ repositories│ ◀──────── ❌ shortcut         │       │       │ (44 tbl) │
└─────────────┘                               │       │       └──────────┘
                                              ▼       ▼
                                     ┌──────────┐  ┌──────────────────┐
                                     │ domain   │  │ audio.pipeline   │
                                     │ (pure)   │  │ ym.client        │
                                     └────┬─────┘  └──────────────────┘
                                          │
                                          │ ❌ leak (3 файла)
                                          ▼
                                     ┌──────────┐
                                     │ config   │
                                     └──────────┘
```

### 3.3 Взаимодействия, которых **нет** (правильно)

- `repositories/` ↛ `services/` — нет circular (проверено: 0 импортов).
- `models/` ↛ ничего из `app/*` (модели — листья).
- `domain/` ↛ `repositories/`, `services/`, `mcp/`, `audio/`, `ym/` (почти — кроме config).
- `audio/` ↛ `services/`, `repositories/`, `mcp/` (модуль изолирован).
- `panel/` ↛ `app/*` (Next.js полностью отдельный).

### 3.4 Взаимодействия, которых **быть не должно** (надо чинить)

| Источник | Цель | Файлы | Почему плохо |
|----------|------|-------|--------------|
| `mcp/tools/` | `repositories/` | `sets.py`, `search.py`, `tracks.py`, `curation.py` | Tool обходит use-case, дублирует логику резолвинга/валидации |
| `mcp/tools/` | `audio/` | `sets.py`, `audio.py`, `curation.py`, `delivery.py` | Адаптер знает про конкретный analyzer engine |
| `mcp/tools/` | `models/` | `audio.py` | Tool возвращает SQLAlchemy объект |
| `mcp/tools/` | `domain/` | `delivery.py` | Tool знает про доменные writer'ы |
| `services/` | `models/` | 13 сервисов | Сервисы используют ORM как DTO — нормально, но течёт ORM наружу |
| `domain/` | `app.config` | `audit/rules.py`, `transition/scorer.py`, `optimization/genetic.py` | **Критично**: ядро бизнес-логики зависит от инфра-конфига |

---

## 4. Найденные проблемы и code smells

### 4.1 Дубликаты файлов и шимов

Файлы с одинаковыми именами в разных пакетах:

| Имя | Местоположения | Статус |
|-----|----------------|--------|
| `storage.py` | `core/`(8) + `infrastructure/`(97) | 🟡 миграция: `core/storage.py` — re-export shim |
| `seed.py` | `core/`(8) + `infrastructure/`(120) | 🟡 миграция: `core/seed.py` — shim |
| `elicitation.py` | `core/`(8) + `mcp/`(160) | 🟡 миграция: `core/elicitation.py` — shim |
| `transition.py` | `services/`(9) + `models/` + `repositories/` + `domain/transition/scorer.py` | 🟡 `services/transition.py` — shim |
| `export.py` | `services/`(13) + `models/` + `repositories/` + `domain/export/` | 🟡 `services/export.py` — shim |
| `optimizer.py` | `services/`(9) — shim к `domain/optimization/` | 🟡 |
| `templates.py` | `services/`(12) + `mcp/resources/templates.py` | 🟡 services-shim |
| `set_service.py` | `services/`(8) — shim к `services/set/facade.py` | 🟡 |
| `curation_service.py` | `services/`(8) — shim к `services/curation/facade.py` | 🟡 |
| `base.py` | `repositories/` + `models/` + `audio/analyzers/` | ✅ разные роли — ОК |
| `crud.py` | `mcp/tools/` + `services/set/` | ✅ разные слои — ОК |
| `context.py` | `mcp/tools/_shared/` (ToolContext) + `audio/core/` (AnalysisContext) | ✅ разные домены — ОК |
| `errors.py` | `core/` + `mcp/tools/_shared/` | ⚠️ возможное дублирование иерархий |
| `spectral.py` | `audio/analyzers/` (фасад) + `audio/core/` (DSP) | ✅ Strategy + Pure helper |

**Action**: 9 шимов помечены к удалению в Phase 5 (по комментариям в файлах). Сейчас они работают как backward-compat, но засоряют namespace и сбивают grep.

### 4.2 Структурная асимметрия `services/`

Сейчас `services/` содержит:
- 13 «жирных» классов в плоских файлах (`reasoning_service.py`, `import_service.py`, `discovery_service.py`, `metadata_service.py`, `sync_service.py`, `delivery_service.py`, `audio_service.py`, …)
- 2 sub-package с фасадами (`set/`, `curation/`)
- 6 backward-compat шимов

**Проблема**: непредсказуемо, где искать класс. `SetService` лежит в `set/facade.py`, а `SyncService` — в `sync_service.py`. Когда писать суффикс `_service`?

**Решение**: либо **все** сервисы в sub-package с одноимённым фасадом, либо **все** в плоских файлах. Я рекомендую **sub-package для use-case кластеров** (set, curation, library, delivery, sync, discovery, analysis) и плоские файлы только для атомарных utility-классов (transition_cache, candidate, embedding).

### 4.3 `core/` стал помойкой shared-kernel

В `app/core/` сейчас 14 файлов разной природы:

| Файл | Истинная природа | Куда должен переехать |
|------|------------------|-----------------------|
| `camelot.py` | Domain VO | `domain/music/camelot.py` |
| `track_features.py` | Domain VO | `domain/music/track_features.py` |
| `transition_intent.py` | Domain Enum | `domain/transition/intent.py` |
| `constants.py` | Domain constants + tech enums | split: `domain/constants.py` + `core/enums.py` |
| `parsing.py` | Domain utility | `domain/parsing.py` |
| `ym_filters.py` | Domain predicates | `domain/curation/filters.py` |
| `errors.py` | Cross-cutting | `core/errors.py` ✅ |
| `pagination.py` | Infra primitive | `infrastructure/pagination.py` |
| `entity_resolver.py` | Application util | `application/resolvers.py` |
| `cache.py` | Infra primitive | `infrastructure/cache.py` |
| `schemas/*.py` | DTO layer | `application/dto/` |
| `seed.py`, `storage.py`, `elicitation.py` | shims | удалить |

После переезда `core/` останется только: `errors.py`, `enums.py` (опционально), `__init__.py`. Возможно, имеет смысл вообще распустить `core/`.

### 4.4 `domain/` ↛ `config` — нарушение Dependency Rule

```python
# app/domain/transition/scorer.py
from app.config import settings  # ❌

class TransitionScorer:
    def __init__(self):
        self.bpm_weight = settings.transition_bpm_weight  # ❌
```

**Почему плохо**: домен теряет тестируемость в изоляции, нельзя переиспользовать `TransitionScorer` в другом контексте, нельзя мокать. Нарушает Dependency Inversion.

**Решение**: инжектировать конфиг как explicit value object:

```python
@dataclass(frozen=True)
class ScoringWeights:
    bpm: float
    harmonic: float
    energy: float
    spectral: float
    groove: float
    timbral: float

class TransitionScorer:
    def __init__(self, weights: ScoringWeights, hard_limits: HardLimits) -> None:
        self._weights = weights
        self._limits = hard_limits
```

В `application/` слое создаётся `ScoringWeights.from_settings(settings)` и пробрасывается вниз. То же для `GeneticAlgorithm` (хранит population_size, mutation_rate в VO `GAConfig`) и `AuditRules` (`TechnoQualityCriteria` VO).

### 4.5 MCP tools обходят сервисы

```python
# app/mcp/tools/sets.py
from app.repositories.set import SetRepository  # ❌
from app.audio.pipeline import AnalysisPipeline  # ❌
```

Проблема: tool делает то, что должен делать сервис. Это значит:
1. Логика дублируется (если tool вызовут из теста или из REST API мимо tool-обёртки).
2. Сложно мокать на уровне сервисов.
3. Нарушает SRP — tool это **adapter**, его задача — переводить MCP-запрос в use-case вызов.

**Решение**: вынести всю логику из tool'ов в use case (`SetService.build_with_audio_analysis(...)`), tool превращается в 5 строк:

```python
@tool(annotations=ANNOTATIONS_WRITE, timeout=ToolTimeout.HEAVY)
async def build_set(
    ctx: Context,
    playlist_id: int,
    name: str,
    template: str | None = None,
    target_duration_min: int | None = None,
    algorithm: Literal["greedy", "ga"] = "ga",
    set_service: SetService = Depends(get_set_service),
) -> SetResponse:
    """Build optimized DJ set from playlist tracks."""
    return await set_service.build(
        BuildSetCommand(playlist_id, name, template, target_duration_min, algorithm),
        progress=ToolContext(ctx),
    )
```

### 4.6 `audio/` — почти образцовый изолированный модуль, но…

`audio/` импортирует только `numpy/librosa/essentia`, `app.config` (для sample_rate, n_mfcc), `app.core.constants`. Это хорошо. Но у него **есть знание про DB** через `audio/timeseries.py` (NPZ файлы) — на самом деле это файловый I/O, не DB, так что норм.

Проблема: `services/audio_service.py` и `services/tiered_pipeline.py` — оба оркестрируют audio. Дублирование? Надо посмотреть, делают ли они разное:
- `AudioService` — ручной anlyze_track / analyze_batch (по запросу пользователя)
- `TieredPipeline` — auto-trigger из других сервисов (classify_mood, build_set, deliver_set)

**Решение**: объединить в `application/audio/` с двумя use case: `AnalyzeTracksUseCase` (явный) и `EnsureAnalysisLevelUseCase` (для уровня L1/L2/L3/L4 при auto-trigger).

### 4.7 `mcp/elicitation.py` vs `core/elicitation.py`

`core/elicitation.py` — 8 строк, реэкспорт. Реальный код в `mcp/elicitation.py` (160). Это правильно, но `mcp/elicitation.py` — это уже не «interface adapter», а «application util» (универсальные safe_choice/safe_confirm). Если хотим строгое разделение: вынести в `application/` (сервис уровень), а `mcp/elicitation.py` оставить только тонкий wrapper над `ctx.elicit(...)`.

### 4.8 Нет явных портов (Port interfaces)

Сейчас domain напрямую вызывает `repositories` через `services`, и нет ни одного `Protocol` / `ABC` в `domain/ports/`. Это не критично пока проект небольшой, но как только добавится второй persistence backend (например, локальный JSON для оффлайн-режима) или второй streaming-сервис кроме YM, придётся всё переписывать.

**Action**: ввести `domain/ports/`:
- `TrackRepositoryPort` (Protocol)
- `PlaylistRepositoryPort`
- `MusicStreamingGatewayPort` (= YM, потенциально Spotify)
- `AudioAnalysisGatewayPort`
- `StorageBackendPort`

Это даст моки в тестах без in-memory SQLite.

### 4.9 `serve_http.py` в корне проекта

FastAPI-обёртка лежит как одинокий файл в корне. Если завтра появится gRPC или WebSocket — будет ещё `serve_grpc.py`, `serve_ws.py`. Уже сейчас имеет смысл:

```text
app/
└── interface/
    ├── mcp/         ← (бывший app/mcp/)
    └── http/
        └── api.py   ← (бывший serve_http.py)
```

### 4.10 `infrastructure/` почти пустой

В `app/infrastructure/` лежит 2 файла (`storage.py`, `seed.py`). Это явный признак незавершённого рефакторинга. По логике туда должны переехать:
- `repositories/` → `infrastructure/persistence/repositories/`
- `models/` → `infrastructure/persistence/models/`
- `migrations/` → `infrastructure/persistence/migrations/`
- `audio/` (как driver-адаптер) → `infrastructure/audio/`
- `ym/` → `infrastructure/integrations/yandex_music/`
- `core/cache.py` → `infrastructure/cache.py`

---

## 5. Целевая многослойная архитектура

Применяю Clean / Hexagonal Architecture с 5 слоями. Главное правило (Dependency Rule):

> **Зависимости направлены строго внутрь.** Внешний слой знает про внутренний; внутренний слой про внешний — никогда.

```text
              ┌──────────────────────────────────────────────┐
              │           INTERFACE (Adapters In)            │
              │   mcp/  http/  panel/  cli/  scheduled/      │
              └──────────────────────┬───────────────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────────┐
              │          APPLICATION (Use Cases)             │
              │   commands, queries, orchestrators           │
              │   knows: domain ports + DTO                  │
              └──────────────────────┬───────────────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────────┐
              │              DOMAIN (Pure)                   │
              │   entities, VO, domain services, ports       │
              │   knows: nothing outside domain              │
              └──────────────────────────────────────────────┘
                                     ▲
                                     │ (impl of ports)
              ┌──────────────────────┴───────────────────────┐
              │     INFRASTRUCTURE (Adapters Out)            │
              │  persistence/  cache/  storage/  observ/     │
              └──────────────────────────────────────────────┘
                                     ▲
                                     │ (impl of ports)
              ┌──────────────────────┴───────────────────────┐
              │   INTEGRATION (External Services Adapters)   │
              │  yandex_music/  audio_engine/  llm_sampling/ │
              └──────────────────────────────────────────────┘
```

### 5.1 Обоснование 5 слоёв (вместо классических 4)

Я разделяю «outbound adapters» на два:
- **Infrastructure** — то, что **лежит в нашем приложении** (БД, кеш, файловое хранилище, миграции, observability).
- **Integration** — то, что **внешние сервисы** (YM API, librosa/essentia engines, Anthropic LLM API).

Это даёт два независимых дерева зависимостей: можно подменить YM на Spotify не трогая БД, и наоборот.

### 5.2 Что куда попадает

| Слой | Что внутри | Кому разрешено импортировать |
|------|------------|------------------------------|
| **domain** | Entities, VOs, Aggregates, Domain Services, Ports (Protocols), Domain Errors, Constants | только себя + stdlib + numpy (для DSP-VO) |
| **application** | Commands, Queries, Use Cases, Application Services (фасады), DTOs, Mappers, Application Errors | domain + stdlib |
| **infrastructure** | SQLAlchemy models, Repositories, Migrations, Cache, Storage, Observability | domain + application (для DTO) + sqlalchemy/redis/etc |
| **integration** | YM client, Audio engines, LLM clients | domain + application |
| **interface** | MCP tools/resources/prompts, FastAPI routes, CLI, scheduled tasks | application + DTO |

### 5.3 Чего **нельзя** делать ни в одном слое

- **Domain** не импортирует `app.config`, `sqlalchemy`, `httpx`, `fastmcp`, `pydantic` (только `dataclass`/`Protocol`).
- **Application** не импортирует `sqlalchemy`, `httpx`, `fastmcp`, `librosa`. Только domain + DTO.
- **Infrastructure** не вызывает `interface` (нет «бэк-вызовов» в MCP или HTTP).
- **Integration** не знает про `infrastructure` (YM-клиент не лезет в БД).
- **Interface** не вызывает `infrastructure` напрямую — только через `application`.

---

## 6. Каноничная структура директорий

```text
dj-music-plugin/
├── pyproject.toml
├── alembic.ini
├── fastmcp.json
├── start.sh
│
├── app/
│   │
│   ├── __init__.py
│   ├── config.py                          ← Settings (singleton)
│   ├── bootstrap.py                       ← composition root: wires DI
│   │
│   ├── domain/                            ← ──────── INNERMOST ───────
│   │   ├── __init__.py
│   │   ├── shared/
│   │   │   ├── errors.py                  ← NotFound, Validation, Conflict
│   │   │   ├── value_objects.py           ← Bpm, Lufs, Energy, Confidence
│   │   │   └── time.py                    ← UtcInstant VO
│   │   │
│   │   ├── music/                         ← Music theory primitives
│   │   │   ├── camelot.py                 ← Camelot wheel + distance
│   │   │   ├── key.py                     ← Key, KeyCode VOs
│   │   │   ├── bpm.py                     ← Bpm VO with double/half-time
│   │   │   ├── track_features.py          ← TrackFeatures aggregate
│   │   │   └── subgenre.py                ← Subgenre enum + ordering
│   │   │
│   │   ├── library/                       ← Library aggregate
│   │   │   ├── track.py                   ← Track entity
│   │   │   ├── artist.py
│   │   │   ├── playlist.py
│   │   │   ├── label.py
│   │   │   └── release.py
│   │   │
│   │   ├── set/                           ← DJ set aggregate
│   │   │   ├── set.py                     ← DjSet entity
│   │   │   ├── set_version.py
│   │   │   ├── set_item.py
│   │   │   ├── template.py                ← SetTemplate, TemplateSlot
│   │   │   ├── template_registry.py       ← static catalog of 8 templates
│   │   │   ├── energy_arc.py              ← EnergyArc VO
│   │   │   └── constraints.py             ← SetConstraint VO
│   │   │
│   │   ├── transition/                    ← Transition scoring
│   │   │   ├── score.py                   ← TransitionScore VO
│   │   │   ├── scorer.py                  ← TransitionScorer (domain service)
│   │   │   ├── intent.py                  ← TransitionIntent enum
│   │   │   ├── weights.py                 ← ScoringWeights, HardLimits VO
│   │   │   ├── components/                ← Strategy per component
│   │   │   │   ├── bpm.py
│   │   │   │   ├── harmonic.py
│   │   │   │   ├── energy.py
│   │   │   │   ├── spectral.py
│   │   │   │   ├── groove.py
│   │   │   │   └── timbral.py
│   │   │   └── math.py                    ← sigmoid, gaussian, cosine
│   │   │
│   │   ├── optimization/                  ← Set order optimization
│   │   │   ├── optimizer_port.py          ← Optimizer Protocol
│   │   │   ├── greedy.py                  ← GreedyChainBuilder
│   │   │   ├── genetic.py                 ← GeneticAlgorithm
│   │   │   ├── fitness.py                 ← Fitness function (Strategy)
│   │   │   ├── result.py                  ← OptimizationResult VO
│   │   │   └── config.py                  ← GAConfig, GreedyConfig VO
│   │   │
│   │   ├── audit/                         ← Quality criteria
│   │   │   ├── techno_criteria.py         ← TechnoQualityCriteria VO
│   │   │   ├── rules.py                   ← AuditRule (Strategy)
│   │   │   └── result.py                  ← AuditResult VO
│   │   │
│   │   ├── classification/                ← Mood / subgenre classification
│   │   │   ├── classifier.py              ← MoodClassifier (rule-based)
│   │   │   ├── profiles.py                ← Subgenre weight profiles
│   │   │   └── result.py                  ← ClassificationResult VO
│   │   │
│   │   ├── audio/                         ← Audio domain (PURE)
│   │   │   ├── signal.py                  ← AudioSignal VO
│   │   │   ├── analysis_level.py          ← L1-L4 enum
│   │   │   ├── feature_set.py             ← ComputedFeatures aggregate
│   │   │   └── pipeline_spec.py           ← Which analyzers per level
│   │   │
│   │   ├── export/                        ← Set export logic (PURE)
│   │   │   ├── formats.py                 ← Format enum
│   │   │   ├── m3u8.py                    ← M3U8 serializer (str output)
│   │   │   ├── json_guide.py              ← JSON guide builder
│   │   │   ├── rekordbox.py               ← Rekordbox XML builder
│   │   │   └── cheatsheet.py              ← Cheat sheet builder
│   │   │
│   │   └── ports/                         ← All abstract gateways
│   │       ├── repositories.py            ← TrackRepoPort, SetRepoPort, ...
│   │       ├── streaming.py               ← MusicStreamingPort
│   │       ├── audio_engine.py            ← AudioAnalysisPort
│   │       ├── storage.py                 ← StorageBackendPort
│   │       ├── cache.py                   ← CachePort
│   │       └── llm.py                     ← LlmSamplingPort
│   │
│   ├── application/                       ← ──────── USE CASES ───────
│   │   ├── __init__.py
│   │   ├── dto/                           ← всё, что пересекает границу
│   │   │   ├── track.py
│   │   │   ├── playlist.py
│   │   │   ├── set.py
│   │   │   ├── transition.py
│   │   │   └── common.py                  ← Cursor, PaginatedPage
│   │   │
│   │   ├── library/                       ← Library use cases
│   │   │   ├── list_tracks.py
│   │   │   ├── get_track.py
│   │   │   ├── manage_track.py
│   │   │   ├── search_tracks.py
│   │   │   └── filter_tracks.py
│   │   │
│   │   ├── playlists/
│   │   │   ├── list_playlists.py
│   │   │   ├── get_playlist.py
│   │   │   └── manage_playlist.py
│   │   │
│   │   ├── sets/                          ← Set use cases
│   │   │   ├── build_set.py               ← BuildSetUseCase
│   │   │   ├── rebuild_set.py
│   │   │   ├── score_transitions.py
│   │   │   ├── get_cheat_sheet.py
│   │   │   ├── reasoning.py               ← suggest_next, explain, replace
│   │   │   └── compare_versions.py
│   │   │
│   │   ├── delivery/                      ← Set delivery pipeline
│   │   │   ├── deliver_set.py             ← DeliverSetUseCase (orchestrator)
│   │   │   ├── score_stage.py
│   │   │   ├── export_stage.py
│   │   │   └── sync_stage.py
│   │   │
│   │   ├── curation/                      ← Curation use cases
│   │   │   ├── classify_mood.py
│   │   │   ├── audit_playlist.py
│   │   │   ├── distribute_to_subgenres.py
│   │   │   └── library_stats.py
│   │   │
│   │   ├── discovery/
│   │   │   ├── find_similar.py
│   │   │   ├── expand_playlist.py
│   │   │   └── filter_by_feedback.py
│   │   │
│   │   ├── ingestion/
│   │   │   ├── import_tracks.py
│   │   │   └── download_tracks.py
│   │   │
│   │   ├── analysis/                      ← Audio analysis use cases
│   │   │   ├── analyze_track.py
│   │   │   ├── analyze_batch.py
│   │   │   ├── ensure_level.py            ← Tiered auto-trigger
│   │   │   └── separate_stems.py
│   │   │
│   │   ├── sync/
│   │   │   ├── sync_playlist.py
│   │   │   └── push_set_to_ym.py
│   │   │
│   │   ├── shared/
│   │   │   ├── unit_of_work.py            ← UoW Protocol
│   │   │   ├── transaction.py             ← @transactional decorator
│   │   │   ├── progress.py                ← ProgressReporter Protocol
│   │   │   ├── elicitation.py             ← Elicitation Protocol
│   │   │   └── resolvers.py               ← entity resolvers
│   │   │
│   │   └── errors.py                      ← UseCase errors
│   │
│   ├── infrastructure/                    ← ──────── PERSISTENCE ETC ───────
│   │   ├── __init__.py
│   │   │
│   │   ├── persistence/
│   │   │   ├── database.py                ← AsyncSession factory
│   │   │   ├── unit_of_work.py            ← SqlAlchemyUnitOfWork
│   │   │   ├── models/                    ← SQLAlchemy ORM (бывший app/models/)
│   │   │   │   ├── base.py
│   │   │   │   ├── track.py
│   │   │   │   ├── playlist.py
│   │   │   │   ├── set.py
│   │   │   │   ├── transition.py
│   │   │   │   ├── audio.py
│   │   │   │   ├── platform.py
│   │   │   │   ├── library.py
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── export.py
│   │   │   │   └── key.py
│   │   │   ├── repositories/              ← Implements domain ports
│   │   │   │   ├── track_repository.py
│   │   │   │   ├── playlist_repository.py
│   │   │   │   ├── set_repository.py
│   │   │   │   ├── transition_repository.py
│   │   │   │   ├── feature_repository.py
│   │   │   │   ├── candidate_repository.py
│   │   │   │   ├── embedding_repository.py
│   │   │   │   ├── audio_repository.py
│   │   │   │   ├── ingestion_repository.py
│   │   │   │   ├── metadata_repository.py
│   │   │   │   ├── export_repository.py
│   │   │   │   └── playlist_repository.py
│   │   │   ├── mappers/                   ← ORM ↔ Domain entity
│   │   │   │   ├── track_mapper.py
│   │   │   │   └── ...
│   │   │   ├── pagination.py              ← Cursor primitive
│   │   │   └── migrations/                ← Alembic
│   │   │       ├── env.py
│   │   │       └── versions/
│   │   │
│   │   ├── cache/
│   │   │   ├── lru_cache.py               ← Generic LRU
│   │   │   └── transition_cache.py        ← Domain-specific wrapper
│   │   │
│   │   ├── storage/
│   │   │   ├── filesystem_storage.py      ← FilesystemStorageBackend
│   │   │   └── timeseries_npz.py          ← Frame-data persistence
│   │   │
│   │   ├── observability/
│   │   │   ├── logging.py
│   │   │   ├── sentry.py
│   │   │   └── tracing.py                 ← OpenTelemetry
│   │   │
│   │   └── seeding/
│   │       └── reference_data.py          ← keys, providers
│   │
│   ├── integration/                       ← ──────── EXTERNAL SERVICES ──
│   │   ├── __init__.py
│   │   │
│   │   ├── yandex_music/
│   │   │   ├── client.py                  ← async httpx wrapper
│   │   │   ├── rate_limiter.py
│   │   │   ├── auth.py
│   │   │   ├── dto.py                     ← YM response models
│   │   │   ├── mappers.py                 ← YM DTO ↔ domain
│   │   │   ├── gateway.py                 ← MusicStreamingPort impl
│   │   │   └── endpoints/                 ← по сущностям
│   │   │       ├── search.py
│   │   │       ├── tracks.py
│   │   │       ├── albums.py
│   │   │       ├── artists.py
│   │   │       ├── playlists.py
│   │   │       └── likes.py
│   │   │
│   │   ├── audio_engine/                  ← librosa/essentia adapters
│   │   │   ├── analyzers/                 ← По одному файлу на анализатор
│   │   │   │   ├── base.py                ← BaseAnalyzer (Template Method)
│   │   │   │   ├── loudness.py
│   │   │   │   ├── energy.py
│   │   │   │   ├── spectral.py
│   │   │   │   ├── bpm.py
│   │   │   │   ├── beat.py
│   │   │   │   ├── key.py
│   │   │   │   ├── mfcc.py
│   │   │   │   ├── tonnetz.py
│   │   │   │   ├── tempogram.py
│   │   │   │   ├── pitch_salience.py
│   │   │   │   ├── spectral_complexity.py
│   │   │   │   ├── danceability.py
│   │   │   │   ├── dissonance.py
│   │   │   │   ├── dynamic_complexity.py
│   │   │   │   ├── bpm_histogram.py
│   │   │   │   ├── beats_loudness.py
│   │   │   │   ├── phrase.py
│   │   │   │   └── structure.py
│   │   │   ├── core/                      ← DSP primitives
│   │   │   │   ├── loader.py
│   │   │   │   ├── context.py             ← AnalysisContext (STFT cache)
│   │   │   │   ├── framing.py             ← Stitched multi-window
│   │   │   │   └── spectral.py            ← Pure numpy DSP
│   │   │   ├── pipeline.py                ← AnalysisPipeline (Composite)
│   │   │   ├── registry.py                ← AnalyzerRegistry
│   │   │   ├── temp_download.py           ← Temp file lifecycle
│   │   │   └── gateway.py                 ← AudioAnalysisPort impl
│   │   │
│   │   └── llm/
│   │       ├── anthropic_client.py
│   │       └── sampling_gateway.py        ← LlmSamplingPort impl
│   │
│   └── interface/                         ← ──────── INBOUND ADAPTERS ──
│       ├── __init__.py
│       │
│       ├── mcp/                           ← (бывший app/mcp/)
│       │   ├── server.py                  ← FastMCP entrypoint
│       │   ├── lifespan.py
│       │   ├── dependencies.py            ← Depends() factories
│       │   ├── middleware.py
│       │   ├── elicitation.py             ← MCP-specific elicit wrapper
│       │   ├── _shared/
│       │   │   ├── context.py             ← ToolContext
│       │   │   ├── dispatch.py            ← ActionDispatcher
│       │   │   ├── resolvers.py
│       │   │   ├── taxonomy.py            ← ToolCategory enum
│       │   │   ├── annotations.py         ← ANNOTATIONS_*
│       │   │   ├── timeouts.py            ← ToolTimeout enum
│       │   │   └── errors.py
│       │   ├── tools/                     ← Тонкие адаптеры — 5-10 строк
│       │   │   ├── library/
│       │   │   │   ├── tracks.py
│       │   │   │   ├── playlists.py
│       │   │   │   └── search.py
│       │   │   ├── sets/
│       │   │   │   ├── crud.py
│       │   │   │   ├── building.py
│       │   │   │   └── reasoning.py
│       │   │   ├── delivery/
│       │   │   │   ├── deliver.py
│       │   │   │   └── export.py
│       │   │   ├── curation/
│       │   │   │   ├── classify.py
│       │   │   │   ├── audit.py
│       │   │   │   └── distribute.py
│       │   │   ├── discovery/
│       │   │   │   ├── similar.py
│       │   │   │   ├── expand.py
│       │   │   │   └── feedback.py
│       │   │   ├── ingestion/
│       │   │   │   ├── import_tracks.py
│       │   │   │   └── download.py
│       │   │   ├── analysis/
│       │   │   │   ├── analyze.py
│       │   │   │   ├── analyze_batch.py
│       │   │   │   └── stems.py
│       │   │   ├── sync/
│       │   │   │   ├── playlist.py
│       │   │   │   └── push_set.py
│       │   │   ├── yandex/                ← Прямые YM tools
│       │   │   │   ├── search.py
│       │   │   │   ├── tracks.py
│       │   │   │   ├── albums.py
│       │   │   │   ├── playlists.py
│       │   │   │   └── likes.py
│       │   │   └── admin/
│       │   │       ├── unlock.py
│       │   │       └── platforms.py
│       │   ├── resources/
│       │   │   ├── status.py
│       │   │   ├── reference.py
│       │   │   └── templates.py
│       │   ├── prompts/
│       │   │   └── workflows.py
│       │   └── schemas/                   ← MCP-специфичные Pydantic
│       │       ├── llm_sampling.py
│       │       └── tool_results.py
│       │
│       ├── http/                          ← (бывший serve_http.py)
│       │   ├── api.py                     ← FastAPI app
│       │   ├── routers/
│       │   │   ├── tools.py
│       │   │   ├── health.py
│       │   │   └── mcp.py
│       │   └── schemas/
│       │       └── tool_call.py
│       │
│       └── cli/                           ← (опционально, для скриптов)
│           └── benchmark.py
│
├── panel/                                 ← Next.js (без изменений)
│
├── tests/
│   ├── unit/                              ← Только domain (без БД)
│   │   ├── domain/
│   │   ├── application/                   ← С моками портов
│   │   └── audio_engine/
│   ├── integration/                       ← С in-memory SQLite
│   │   ├── infrastructure/
│   │   ├── interface/mcp/
│   │   └── interface/http/
│   ├── e2e/
│   │   └── workflows/
│   └── fixtures/
│       ├── audio/                         ← synthetic WAV
│       └── data/
│
└── docs/                                  ← документация
    ├── architecture/
    │   ├── overview.md
    │   ├── layers.md
    │   ├── ports-and-adapters.md
    │   └── adr/                           ← Architecture Decision Records
    ├── domain/
    │   └── glossary.md
    ├── api/
    │   └── tool-catalog.md
    └── reports/
```

---

## 7. Распределение ответственности (что МОЖНО / НЕЛЬЗЯ)

### 7.1 Domain layer

| Может | Не может |
|-------|----------|
| Содержать чистые бизнес-правила | Импортировать sqlalchemy, httpx, fastmcp, pydantic.BaseModel (только dataclass) |
| Определять Protocol/ABC для портов | Импортировать `app.config` (конфиг проходит через VO в конструкторе) |
| Работать с numpy в DSP-VO | Делать I/O (файл, сеть, БД) |
| Бросать `DomainError` | Логировать (logging нет в domain — только raise) |
| Использовать stdlib | Знать про DTO/Pydantic |

**Контракт**: можно скопировать `app/domain/` в любой другой проект и оно скомпилируется, имея только numpy и stdlib.

### 7.2 Application layer

| Может | Не может |
|-------|----------|
| Импортировать domain | Импортировать sqlalchemy, fastmcp, httpx |
| Определять Use Case как `class XxxUseCase` или `async def execute(...)` | Знать конкретные репозитории — только порты |
| Создавать DTO для пересечения границы | Открывать DB сессию (только UoW Protocol) |
| Логировать через logging | Делать print, sys.exit |
| Конвертировать domain ↔ DTO через mapper | Содержать бизнес-правила (правила = в domain) |

**Контракт**: use case принимает Command/Query DTO, возвращает Response DTO, всё через инжектированные порты. Тестируется с моками портов без БД.

### 7.3 Infrastructure layer

| Может | Не может |
|-------|----------|
| Использовать sqlalchemy, alembic, aiosqlite, asyncpg | Содержать бизнес-правила |
| Реализовывать порты из `domain/ports/` | Импортировать `interface/` |
| Маппить ORM ↔ domain entity | Решать use case (это работа application) |
| Делать flush, не commit | Знать про MCP/HTTP |

**Контракт**: репозиторий импортируется ТОЛЬКО как реализация порта, через DI. Тесты запускают репозиторий против реальной in-memory SQLite.

### 7.4 Integration layer

| Может | Не может |
|-------|----------|
| Делать HTTP, WebSocket, gRPC к внешним сервисам | Импортировать infrastructure (нельзя писать в БД из YM gateway) |
| Использовать httpx, librosa, essentia, anthropic | Знать про use cases |
| Реализовывать порты из `domain/ports/` | Принимать решения уровня бизнеса |
| Маппить external DTO ↔ domain | Кешировать в БД (это infra) — может только in-memory |

**Контракт**: integration adapter получает `domain` параметры на вход, возвращает `domain` объекты на выход; всё API-specifics инкапсулированы.

### 7.5 Interface layer

| Может | Не может |
|-------|----------|
| Импортировать application + DTO | Вызывать infrastructure напрямую |
| Парсить входной запрос (MCP, HTTP, CLI) | Содержать бизнес-логику (только перевод параметров) |
| Сериализовать DTO в формат протокола | Делать I/O в БД |
| Делать elicitation, progress reporting | Знать про SQLAlchemy |
| Логировать, маскировать ошибки | Возвращать ORM объекты наружу |

**Контракт**: tool в 5-15 строк. Если больше — логика просочилась из application.

---

## 8. GoF-паттерны: где применять

| Паттерн | Где сейчас | Где надо явно ввести |
|---------|------------|----------------------|
| **Repository** | ✅ `repositories/` | Перенести в `infrastructure/persistence/repositories/` + порты в `domain/ports/` |
| **Unit of Work** | 🟡 неявно через `get_db_session()` | Формализовать `application/shared/unit_of_work.py` + `SqlAlchemyUnitOfWork` |
| **Strategy** | 🟡 BaseAnalyzer есть, оптимизаторы есть | Применить к компонентам Transition Score (один Strategy на каждый из 6 компонентов) |
| **Template Method** | ✅ `BaseAnalyzer.analyze()` | OK |
| **Composite** | ✅ `AnalysisPipeline` + `analyzers` | OK |
| **Decorator** | ✅ FastMCP middleware | Применить к `TransitionScorer` для cache (DecoratorScorer wraps Real) |
| **Facade** | ✅ `SetService`, `CurationService` | Расширить: единый `LibraryFacade`, `DeliveryFacade` для interface |
| **Command** | ✅ `ActionDispatcher` для `ym_playlists`, `ym_likes`, `manage_*` | Расширить на все `manage_*` tools |
| **Registry** | ✅ `AnalyzerRegistry`, template registry | Ввести `RepositoryRegistry` для DI |
| **Adapter** | 🟡 неявно (YM client = adapter) | Явно через `domain/ports/` |
| **Value Object** | ✅ `TrackFeatures` | Расширить: `Bpm`, `Lufs`, `Camelot`, `Energy` — все frozen dataclass |
| **Specification** | ❌ нет | Применить к `filter_tracks` (composable predicates: `BpmRange & KeyCompatible & EnergyAbove`) |
| **Mediator** | ❌ нет | Не вводить — overkill для текущего размера |
| **Observer** | 🟡 ProgressReporter неявно | Формализовать `ProgressReporter` Protocol для use case |
| **Factory Method** | ✅ `TrackFeatures.from_db()` | Расширить на все mapper'ы |
| **Abstract Factory** | ❌ нет | Можно ввести для `StorageBackend` (filesystem vs s3 vs gcs) |
| **Chain of Responsibility** | ✅ FastMCP middleware | OK |
| **Builder** | ❌ нет | Можно для `SetExportData.builder()` (m3u8 + json + cheatsheet за один проход) |

### 8.1 Конкретный пример: Strategy для компонентов TransitionScorer

Сейчас `domain/transition/scorer.py` — 454 строки в одном классе. С 6 компонентами это нарушение SRP.

```python
# domain/transition/components/base.py
class TransitionComponent(Protocol):
    name: str
    weight: float

    def score(self, a: TrackFeatures, b: TrackFeatures, intent: TransitionIntent) -> float:
        ...

# domain/transition/components/bpm.py
@dataclass(frozen=True)
class BpmComponent(TransitionComponent):
    name: str = "bpm"
    weight: float
    sigma: float

    def score(self, a, b, intent):
        delta = abs(a.bpm - b.bpm)
        delta = min(delta, abs(a.bpm - b.bpm * 2), abs(a.bpm - b.bpm / 2))
        return math.exp(-delta**2 / (2 * self.sigma**2))

# domain/transition/scorer.py
class TransitionScorer:
    def __init__(self, components: Sequence[TransitionComponent], hard_limits: HardLimits):
        self._components = components
        self._limits = hard_limits

    def score(self, a, b, intent=TransitionIntent.MAINTAIN) -> TransitionScore:
        if self._limits.violated(a, b):
            return TransitionScore.zero(reason="hard_reject")
        results = {c.name: c.score(a, b, intent) for c in self._components}
        overall = sum(results[c.name] * c.weight for c in self._components)
        return TransitionScore(overall=overall, components=results)
```

Преимущества: тесты на каждый компонент изолированно, добавление 7-го компонента — новый файл без правки `TransitionScorer`, можно делать A/B тесты с разными наборами Strategies.

### 8.2 Specification для `filter_tracks`

```python
# domain/library/specifications.py
class TrackSpecification(Protocol):
    def is_satisfied_by(self, track: Track) -> bool: ...
    def to_sql(self) -> ColumnElement: ...   # для оптимизации в репо

@dataclass(frozen=True)
class BpmRangeSpec:
    min: float
    max: float

@dataclass(frozen=True)
class KeyCompatibleSpec:
    target: KeyCode

class AndSpec:
    def __init__(self, *specs): self.specs = specs
    def is_satisfied_by(self, t): return all(s.is_satisfied_by(t) for s in self.specs)

# Используется так:
spec = AndSpec(BpmRangeSpec(120, 130), KeyCompatibleSpec(target=Key.AM))
tracks = await track_repo.find_by_spec(spec, limit=20)
```

---

## 9. Naming conventions

### 9.1 Файлы

- `snake_case.py` всегда.
- **Сущности**: `track.py`, `playlist.py`, `set.py` — единственное число.
- **Use case**: `build_set.py`, `classify_mood.py` — глагол + объект, единственное число.
- **Use case класс**: `BuildSetUseCase` (если class) или `async def execute(cmd: BuildSetCommand)` (если function).
- **Repository implementation**: `track_repository.py`, класс `SqlAlchemyTrackRepository(TrackRepositoryPort)`.
- **Port**: `domain/ports/repositories.py` → `class TrackRepositoryPort(Protocol)`.
- **DTO**: `application/dto/track.py` → `class TrackResponse(BaseModel)`, `class TrackCommand(BaseModel)`.
- **Mapper**: `infrastructure/persistence/mappers/track_mapper.py` → `class TrackMapper`.
- **Gateway**: `integration/yandex_music/gateway.py` → `class YandexMusicGateway(MusicStreamingPort)`.

### 9.2 Классы

- Domain entities: `Track`, `DjSet`, `Playlist` — без суффикса.
- Domain services: `TransitionScorer`, `MoodClassifier`, `GeneticAlgorithm` — описательное имя.
- VO: `Bpm`, `Camelot`, `Lufs`, `TrackFeatures` — без суффикса VO.
- Use cases: `BuildSetUseCase`, `ClassifyMoodUseCase`.
- DTO: `BuildSetCommand`, `BuildSetResponse`, `TrackDto`.
- Repos: `SqlAlchemyTrackRepository`, `InMemoryTrackRepository` (тесты).
- Ports: `TrackRepositoryPort`, `MusicStreamingPort` (Protocol суффикс не нужен — `Port` достаточно).
- Errors: `TrackNotFoundError`, `InvalidBpmError` (`Error` суффикс).

### 9.3 Variables

- `track_id: int` — primary key.
- `track_ref: TrackRef` — резолвимая ссылка (id|query|"local:N").
- `track: Track` (domain entity) — НЕ `track_model`, НЕ `track_orm`.
- `track_dto: TrackDto` — на границе.
- `track_orm: TrackOrm` — внутри `infrastructure/persistence/`, нигде ещё.

### 9.4 Никаких magic numbers

CLAUDE.md уже это требует. Расширить: domain константы → `domain/<bc>/constants.py`. Tunable → `app/config.py`. Tech enum → `domain/shared/enums.py`.

---

## 10. Slice или Layer? Гибрид

Есть 2 школы организации:
1. **Layer-first** (как у нас): `services/`, `repositories/`, `models/` — слои сверху, внутри слоёв сущности
2. **Feature-first** / Vertical Slice: `library/`, `sets/`, `delivery/` — фичи сверху, внутри фичи свои слои

**Я рекомендую гибрид**: layer-first на верхнем уровне (`domain/`, `application/`, `infrastructure/`, `interface/`), внутри каждого слоя — feature-first (`application/sets/`, `application/curation/`, `infrastructure/persistence/repositories/`).

Это даёт:
- Чёткое правило зависимостей (Dependency Rule).
- Локальность изменений (новая feature ≈ один файл в каждом слое).
- Возможность сделать лимит на длинные слои в линтере.

---

## 11. Миграционный план (фазы)

> Все фазы независимые. Каждая фаза — отдельная PR серия. Тесты должны быть зелёные на каждом коммите.

### Phase 1 — `core/` cleanup (1-2 дня)

- [ ] Удалить shim-файлы: `core/storage.py`, `core/seed.py`, `core/elicitation.py`.
- [ ] Заменить все `from app.core.storage import ...` на `from app.infrastructure.storage import ...`.
- [ ] Заменить все `from app.core.elicitation import ...` на `from app.mcp.elicitation import ...`.
- [ ] Удалить `services/export.py`, `services/transition.py`, `services/optimizer.py`, `services/templates.py`, `services/set_service.py`, `services/curation_service.py` (все 6 шимов).
- [ ] Прогнать тесты: `make check`.

### Phase 2 — Зачистка domain ↛ config (1 день)

- [ ] Создать `domain/transition/weights.py`: `ScoringWeights`, `HardLimits` — frozen dataclass.
- [ ] Создать `domain/optimization/config.py`: `GAConfig`, `GreedyConfig`.
- [ ] Создать `domain/audit/techno_criteria.py`: `TechnoQualityCriteria`.
- [ ] Удалить `from app.config import settings` из `audit/rules.py`, `transition/scorer.py`, `optimization/genetic.py`.
- [ ] Сделать `application/<feature>/<usecase>.py`, который собирает VO из `settings` и пробрасывает в domain.

### Phase 3 — MCP tools delamination (2 дня)

- [ ] Найти все `from app.repositories import ...`, `from app.audio import ...`, `from app.models import ...`, `from app.domain import ...` в `mcp/tools/*` (4 + 4 + 1 + 1 = 10 нарушений).
- [ ] Для каждого: вынести логику в существующий или новый use case.
- [ ] Tool становится 5-15 строк: парсит args → вызывает use case → возвращает Response DTO.

### Phase 4 — Services → Application (3-4 дня)

- [ ] Создать `app/application/` с feature-папками.
- [ ] Каждый сервис → 1+ use case в `application/<feature>/`.
- [ ] Унифицировать структуру: все сервисы либо `XxxUseCase` класс с `execute()`, либо `async def xxx_use_case()`. Я рекомендую класс ради DI.
- [ ] Убрать дисбаланс «13 плоских + 2 sub-package» — все в sub-package.

### Phase 5 — Persistence → Infrastructure (2-3 дня)

- [ ] Перенести `app/models/` → `app/infrastructure/persistence/models/`.
- [ ] Перенести `app/repositories/` → `app/infrastructure/persistence/repositories/`.
- [ ] Перенести `app/migrations/` → `app/infrastructure/persistence/migrations/`, обновить `alembic.ini`.
- [ ] Создать `domain/ports/repositories.py` с Protocol для каждого репо.
- [ ] Каждый репозиторий начинает наследовать от соответствующего Port.

### Phase 6 — YM и Audio → Integration (1-2 дня)

- [ ] Перенести `app/ym/` → `app/integration/yandex_music/`.
- [ ] Перенести `app/audio/` → `app/integration/audio_engine/` (но `audio/signal.py`, `audio/analysis_level.py`, `audio/feature_set.py` уезжают в `domain/audio/`).
- [ ] Создать `MusicStreamingPort`, `AudioAnalysisPort` в `domain/ports/`.
- [ ] `YandexMusicGateway`, `AudioAnalysisGateway` — реализации.

### Phase 7 — MCP → Interface (1 день)

- [ ] Перенести `app/mcp/` → `app/interface/mcp/`.
- [ ] Перенести `serve_http.py` → `app/interface/http/api.py`.
- [ ] Создать `app/bootstrap.py` — единая точка composition root: собирает все Settings → Adapters → Repositories → Use Cases → Tools.

### Phase 8 — Lint enforcement (0.5 дня)

- [ ] Добавить `ruff` правило `TID252` (relative imports запрет).
- [ ] Добавить кастомный плагин `import-linter` или `tach`:

```toml
# .tach.toml
[[modules]]
path = "app.domain"
depends_on = []

[[modules]]
path = "app.application"
depends_on = ["app.domain"]

[[modules]]
path = "app.infrastructure"
depends_on = ["app.domain", "app.application"]

[[modules]]
path = "app.integration"
depends_on = ["app.domain", "app.application"]

[[modules]]
path = "app.interface"
depends_on = ["app.application"]
```

`tach check` в pre-commit — невозможно нарушить Dependency Rule случайно.

---

## 12. Контракты и acceptance criteria

После полной миграции должны выполняться:

### 12.1 Структурные

- ✅ Зависимости вниз по диаграмме (проверка `tach check`).
- ✅ `app/domain/` не содержит `import sqlalchemy`, `import httpx`, `import fastmcp`, `from app.config`.
- ✅ `app/application/` не содержит `import sqlalchemy`, `import httpx`, `import fastmcp`.
- ✅ `app/interface/` не импортирует `infrastructure` напрямую.
- ✅ Каждый MCP tool ≤ 30 строк (включая декораторы и docstring).
- ✅ Каждый сервис ≤ 200 строк (если больше — split на 2+ use case).

### 12.2 Качественные

- ✅ Линтер: `ruff check && ruff format --check`.
- ✅ Type-checker: `mypy app/ --strict`.
- ✅ Tests: `pytest -v` зелёный.
- ✅ Coverage ≥ 80% на `domain/` и `application/`.
- ✅ Нет дублированных файлов (`find app -name "*.py" -printf "%f\n" | sort | uniq -d` → пусто, кроме `__init__.py`, `base.py`).

### 12.3 Функциональные

- ✅ Все 50 MCP tools работают (тесты не сломались).
- ✅ Panel читает Supabase напрямую — всё ещё работает (изменения только в `app/`).
- ✅ Alembic migrations накатываются (`uv run alembic upgrade head`).
- ✅ Время `make check` не выросло.

---

## 13. Преимущества целевой архитектуры

| Аспект | До | После |
|--------|----|----|
| Тестируемость domain | Нужен SQLite + .env | `pytest tests/unit/` без I/O |
| Замена YM на Spotify | Переписать 5 сервисов | Реализовать `MusicStreamingPort` |
| Замена librosa на essentia-only | Переписать `audio/pipeline.py` | Реализовать `AudioAnalysisPort` |
| Добавление gRPC | Создать `serve_grpc.py` рядом | Один новый файл `interface/grpc/api.py` |
| Понимание для нового разработчика | Где `SetService`? Что делает `core/`? | Структура говорит сама за себя |
| Линтер ловит layer leaks | Нет | `tach check` в pre-commit |
| Domain reusable | Нет | `pip install dj-music-domain` отдельным пакетом |

---

## 14. Что НЕ менять

Не всё нужно перекраивать. Сохранить как есть:

- ✅ FastMCP + `@tool` декораторы (адаптер ОК).
- ✅ FileSystemProvider — auto-discovery работает.
- ✅ Pydantic v2 + pydantic-settings — стандарт.
- ✅ SQLAlchemy 2.0 + alembic — стандарт.
- ✅ `tests/test_*` mirroring `app/` — стандарт.
- ✅ `panel/` Next.js — отдельный мир, не трогаем.
- ✅ `docs/` структура.
- ✅ `start.sh`, `Makefile`, `pyproject.toml`.
- ✅ Tiered audio analysis (L1-L4) — это **доменное** разделение, оно остаётся.
- ✅ Visibility tiers (core/extended/hidden tools) — оно работает, не трогаем.
- ✅ ActionDispatcher для `ym_playlists`, `ym_likes` — Command pattern, оставляем.

---

## 15. Открытые вопросы

1. **Domain Events**: вводить ли `TrackImported`, `SetBuilt`, `MoodClassified` события? Сейчас `services/background_tasks.py` симулирует это вручную. Преимущество — async observer для panel realtime updates. Минус — лишний слой сложности.
2. **CQRS**: split `*_query.py` / `*_command.py`? Текущий `2026-04-07-mcp-tools-refactor-design.md` упоминал лёгкий split в `library/`. Я считаю, что для DJ-плагина CQRS — overkill, кроме случая когда появятся read replicas.
3. **Hexagonal vs Onion vs Clean**: я выбрал Clean (5 слоёв). Onion (3 слоя: domain + application + infra) проще, но не разделяет inbound и outbound адаптеры. Если хочется минимализма — можно слить `interface/` и `integration/` в один `adapters/`.
4. **Мульти-tenant**: если в будущем плагин станет SaaS — потребуется `tenant_id` в каждой сущности, RLS в Supabase. Сейчас закладывать не нужно, но архитектура легко расширится через middleware → use case context.
5. **Asyncio vs threading в audio**: `audio/pipeline.py` уже использует ProcessPoolExecutor + SharedMemory. Это адекватно. Перенос в `integration/audio_engine/` ничего не меняет в производительности.

---

## 16. Резюме одной картинкой

```text
ДО (текущее)                          ПОСЛЕ (целевое)

app/                                  app/
├── audio/        ─┐                  ├── domain/         ←── PURE
│                  │                  │   ├── shared/
├── config.py     ─┤                  │   ├── music/
├── core/         ─┼─ смешано         │   ├── library/
│   (kernel +     │                   │   ├── set/
│    shims +      │                   │   ├── transition/
│    DTO)         │                   │   ├── optimization/
│                 │                   │   ├── audit/
├── domain/       ─┘                  │   ├── classification/
├── infrastructure/                   │   ├── audio/
│   (почти пустой)                    │   ├── export/
├── mcp/                              │   └── ports/
├── migrations/                       │
├── models/                           ├── application/    ←── USE CASES
├── repositories/                     │   ├── dto/
├── services/                         │   ├── library/
│   (плоско +                         │   ├── sets/
│    sub +                            │   ├── delivery/
│    шимы)                            │   ├── curation/
├── ym/                               │   ├── discovery/
├── utils/                            │   ├── ingestion/
└── server.py                         │   ├── analysis/
                                      │   ├── sync/
serve_http.py  ←── одиноко            │   └── shared/
                                      │
                                      ├── infrastructure/ ←── PERSISTENCE
                                      │   ├── persistence/
                                      │   │   ├── models/
                                      │   │   ├── repositories/
                                      │   │   ├── mappers/
                                      │   │   └── migrations/
                                      │   ├── cache/
                                      │   ├── storage/
                                      │   ├── observability/
                                      │   └── seeding/
                                      │
                                      ├── integration/    ←── EXTERNAL
                                      │   ├── yandex_music/
                                      │   ├── audio_engine/
                                      │   └── llm/
                                      │
                                      ├── interface/      ←── INBOUND
                                      │   ├── mcp/
                                      │   ├── http/
                                      │   └── cli/
                                      │
                                      ├── config.py
                                      └── bootstrap.py    ←── DI wiring
```

---

## 17. Приоритизация (что делать первым)

Если время ограничено, то делаем в таком порядке:

1. **🔴 P0 — Phase 1 (1-2 дня)**: убрать 9 шимов. Чистая победа без рисков.
2. **🔴 P0 — Phase 2 (1 день)**: domain ↛ config. Маленький рефакторинг с большой пользой для тестируемости.
3. **🟠 P1 — Phase 3 (2 дня)**: MCP tools delamination. Сразу сокращает поверхность багов в адаптерах.
4. **🟠 P1 — Phase 8 (0.5 дня)**: `tach` в pre-commit. Замораживает текущее состояние от деградации.
5. **🟡 P2 — Phase 4-7 (8-10 дней)**: полная переезд на 5 слоёв. Большой рефакторинг — делать, когда нет других горящих задач.

Минимальный полезный результат — Phase 1+2+3+8 = ~5 дней. После этого код становится **значительно** чище без полного переезда папок.

---

*Конец отчёта.*

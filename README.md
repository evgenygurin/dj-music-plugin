# DJ Music Plugin

MCP-сервер для управления личной DJ techno библиотекой, построения оптимизированных DJ сетов и интеграции с Яндекс Музыкой.

## Возможности

- **13 MCP tool dispatchers** (v1 polymorphism): `entity_{list,get,create,update,delete,aggregate}` × 11 registered entities, `provider_{read,write,search}` × Yandex, `transition_score_pool`, `sequence_optimize`, `playlist_sync`, `unlock_namespace`
- **27 MCP resources** — per-entity views, session state, schema introspection, static reference blobs
- **6 workflow prompts** — `dj_expert_session`, `build_set_workflow`, `deliver_set_workflow`, `expand_playlist_workflow`, `full_pipeline`, `quick_mix_check`
- **Audio analysis pipeline** — 18 анализаторов (L1→L4 tiered), SharedMemory transport + per-worker AnalysisContext cache
- **DJ set generation** — генетический алгоритм + greedy builder с transition scoring и section-aware весами
- **Transition scoring** — 6-компонентная оценка (BPM, гармония, энергия, спектр, грув, тембр) + hard constraints + recipe engine (12 mix-типов) + intent/style/template awareness
- **Yandex Music интеграция** — `provider_search` / `provider_read` / `provider_write` (playlist add/remove/create/rename/delete/set_description, likes add/remove)
- **Экспорт** — M3U8, Rekordbox XML, JSON guide, cheat sheet (через `local://sets/{id}/cheatsheet` + `deliver_set_workflow` prompt)
- **Mood classification** — 15 techno subgenres, запускается внутри `track_features_analyze` handler
- **REST API** (`app/rest/`) — thin FastAPI wrapper поверх MCP для Panel

## Быстрый старт

```bash
# Установка
uv sync

# Для audio analysis (BPM, key, beat detection)
uv sync --extra audio

# Настройка
cp .env.example .env
# Заполни DJ_YM_TOKEN и DJ_YM_USER_ID в .env

# Запуск
uv run fastmcp run server.py
```

### Установка как Claude Code плагин

Внутри Claude Code (slash-команды):

```bash
/plugin marketplace add evgenygurin/dj-music-plugin
/plugin install dj-music
```

Из терминала через `claude` CLI (non-interactive, годится для скриптов и CI):

```bash
# stable (default branch)
claude plugin marketplace add evgenygurin/dj-music-plugin
claude plugin install dj-music@dj-music-plugin

# dev branch
claude plugin marketplace add evgenygurin/dj-music-plugin@dev
claude plugin install dj-music@dj-music-plugin
```

Альтернативный синтаксис через git URL (любая ветка/тег/SHA):

```bash
claude plugin marketplace add https://github.com/evgenygurin/dj-music-plugin.git#dev
```

Плагин поднимает два MCP сервера:

| Сервер | Назначение |
|--------|------------|
| `mcp` | 13 DJ tool dispatchers + 27 resources + 6 prompts — построение сетов, аудиоанализ, YM, экспорт (FastMCP v3) |
| `db` | Read-only инспекция БД: схема, SQL, миграции, логи |

Сервер `db` принудительно изолирован (security hardening по [официальным рекомендациям Supabase MCP](https://github.com/supabase-community/supabase-mcp#security-risks)):

- `--read-only` — мутации БД блокируются (выполняются через `mcp`)
- `--project-ref=bowosphlnghhgaulcyfm` — scoped к одному проекту
- `--features=database,docs,debug` — surface ограничен: SQL, схема, миграции, логи. Account/branches/storage/edge-functions tools отключены

Конфигурация токена — в [.env](.env.example):

```bash
DJ_DB_ACCESS_TOKEN="..."   # personal access token
```

> Реализация — `@supabase/mcp-server-supabase@0.7.0` (запускается через `npx`). Токен генерится в [Supabase Dashboard](https://supabase.com/dashboard/account/tokens).

#### Платформенные ограничения

Сервер `db` использует `bash`-wrapper для авто-загрузки `.env` (Claude Code не делает этого нативно). На **Windows без WSL/Git-Bash не запустится** — альтернатива: экспортировать `DJ_DB_ACCESS_TOKEN` в shell вручную и заменить wrapper на нативный `env`-блок в `plugin.json`.

Сервер `mcp` использует нативный `command`/`cwd` — pydantic-settings (`app/config/`) читает `.env` сам, кроссплатформенно.

## Разработка

```bash
uv run pytest -v                           # Тесты (1200+)
uv run ruff check && uv run ruff format --check  # Линтер
uv run mypy app/                           # Типы
uv run alembic upgrade head                # Миграции
make check                                 # Всё вместе

# Верификация audio pipeline на реальном MP3
uv run python scripts/verify_audio_pipeline.py [path/to/track.mp3]
```

## Архитектура

FastMCP v3 + FileSystemProvider (standalone `@tool` / `@resource` / `@prompt`, auto-discovery):

```text
tools/       # 13 @tool dispatchers (entity/provider/compute/sync/admin)
resources/   # 27 @resource URIs
prompts/     # 6 @prompt workflow recipes
handlers/    # 6 entity-scoped side-effect handlers
registry/    # EntityRegistry + ProviderRegistry + defaults
repositories/# BaseRepository[M] + UnitOfWork aggregator
models/      # SQLAlchemy 2.0 — 12 aggregate roots
schemas/     # Pydantic DTOs per entity
domain/      # Pure compute: transition / optimization / camelot / template / audit
audio/       # 18 analyzers + tiered pipeline + 15-subgenre classifier
providers/   # External platforms (yandex/ …)
server/      # FastMCP composition: app.py, lifespan, 16 middleware, transforms, visibility
rest/        # Thin FastAPI wrapper over MCP (for Panel)
shared/      # errors, constants, filters, ids, pagination, time (leaf)
config/      # 9 per-domain Settings modules
db/          # session, seed, Alembic migrations
```

**Ключевые решения:**
- **MCP — primary interface.** Композиция — через prompts / CodeMode / Tool Search, а не императивный service-слой.
- **Polymorphism over proliferation.** 13 tool dispatchers вместо 88 (v0.8).
- **Anchor на DB entities.** Один aggregate root = один model + один repo + семья Pydantic schemas.
- **Unit of Work.** Одна `UnitOfWork` на tool call, commit/rollback через `DbSessionMiddleware`.
- **Pure domain.** `app/domain/` не знает о DB / HTTP / FastMCP (enforced by import-linter).
- **Panel direct reads** из Supabase; мутации — через MCP (REST-обёртка).

### Audio module (`app/audio/`)

Layered tiered pipeline L1→L4 (see [docs/audio-pipeline.md](docs/audio-pipeline.md)):

```text
core/             ← DSP primitives (0 app deps)
  types.py           FrameParams, AudioSignal, AnalyzerResult
  framing.py         frame energies, energy slope
  spectral.py        STFT, band energies, centroid, rolloff
  loader.py          AudioLoader (soundfile → librosa → wave)
  context.py         AnalysisContext (eager STFT, thread-safe)

analyzers/        ← 18 feature extractors
  base.py            BaseAnalyzer (Template Method), @register_analyzer
  beat, bpm, energy, key, loudness, mfcc, spectral, structure,
  beats_loudness, bpm_histogram, danceability, dissonance,
  dynamic_complexity, phrase, pitch_salience, spectral_complexity,
  tempogram, tonnetz

classification/   ← 15 techno subgenres (rule-based)
  profiles.py        SubgenreProfile dataclasses
  classifier.py      MoodClassifier (Strategy pattern)

pipeline.py, level_config.py, temp_download.py, timeseries.py
```

- **Two-phase pipeline**: independent analyzers run in parallel, dependent analyzers receive merged results
- **Tiered L1→L4**: L1+L2 triage (6 analyzers) → L3 scoring (+beat) → L4 transition (+structure + permanent MP3)
- **Registry auto-discovery**: `@register_analyzer` + `pkgutil.iter_modules()`
- **Eager context**: STFT/magnitude/freqs computed once, shared read-only — thread-safe
- **SharedMemory transport** + per-worker `AnalysisContext` LRU — эффективный ProcessPool path

**Server middleware (16 слоёв):** error handling, Sentry, OTEL, timing, audit log, retry, response limit/caching, deprecation, cost tracking, sampling budget, progress throttle, tool timeout, provider rate limit, DB session, structured logging.

Архитектурный блюпринт v1: [docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md](docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md)

## Конфигурация

Все настройки через переменные окружения с префиксом `DJ_`. См. [.env.example](.env.example).

### LLM-assisted discovery

Используй prompt `expand_playlist_workflow` — он оркестрирует `provider_search` / `provider_read(entity="track_similar")` → `entity_create(entity="track")` → `entity_create(entity="track_features")`.

Для headless-сценариев опционально включи server-side sampling:

```bash
# В .env
DJ_ANTHROPIC_API_KEY=sk-ant-...
```

`ctx.sample()` fallback подтягивает Anthropic API (см. `app/server/sampling.py`).

## E2E Pipeline

Полный цикл обработки трека (v1 dispatchers + handlers):

```text
entity_create("track",...)  → entity_create("audio_file",...)  → entity_create("track_features",...)  → entity_create("set_version",...)
      │                              │                                 │                                        │
 track_import                 audio_file_download             track_features_analyze                 set_version_build
      │                              │                                 │                                        │
  Track row                   DjLibraryItem +                 18 analyzers → ~60 features           GA / greedy + mix points
  (+ YM metadata)             MP3 on disk                     + mood classification                 + transition_persist
```

Дополнительно: `transition_score_pool` → `sequence_optimize` → `entity_create("set_version")` — trust-chain для сета из существующего пула.

## Требования

- Python 3.12+
- uv (менеджер пакетов)
- Supabase PostgreSQL 16+ (prod), SQLite in-memory (tests only)
- Опционально: librosa (audio analysis), demucs (stem separation), fastmcp[tasks] (background tasks)

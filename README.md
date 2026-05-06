# DJ Music Plugin

**v1.3.6** · MIT · MCP-сервер для управления личной DJ techno библиотекой, построения оптимизированных DJ сетов и интеграции с Яндекс Музыкой.

Три surface'а на одном backend'е: **MCP** (Claude Desktop / Cursor / любой MCP-client), **REST API** (FastAPI обёртка для скриптов), **Web Panel** (Next.js dashboard).

## Возможности

- **20 MCP tools** — 14 generic dispatchers (v1 polymorphism: `entity_{list,get,create,update,delete,aggregate}` × 11 entities, `provider_{read,write,search}` × Yandex, `transition_score_pool`, `sequence_optimize`, `playlist_sync`, `unlock_namespace`, `tool_invoke`) + 6 UI Prefab dashboards (camelot wheel, library audit/dashboard, set view, transition score, score-pool matrix)
- **27 MCP resources** — per-entity views (`local://`), session state (`session://`), schema introspection (`schema://`), static reference blobs (`reference://`)
- **6 workflow prompts** — `dj_expert_session`, `build_set_workflow`, `deliver_set_workflow`, `expand_playlist_workflow`, `full_pipeline`, `quick_mix_check`
- **Audio analysis pipeline** — 18 анализаторов (L1→L4 tiered), SharedMemory transport + per-worker AnalysisContext cache
- **DJ set generation** — генетический алгоритм + greedy builder с transition scoring и section-aware весами
- **Transition scoring** — 6-компонентная оценка (BPM, гармония, энергия, спектр, грув, тембр) + hard constraints + recipe engine (12 mix-типов) + intent/style/template awareness
- **Yandex Music интеграция** — `provider_search` / `provider_read` / `provider_write` (playlist add/remove/create/rename/delete/set_description, likes add/remove)
- **Экспорт** — M3U8, Rekordbox XML, JSON guide, cheat sheet (через `local://sets/{id}/cheatsheet` + `deliver_set_workflow` prompt)
- **Mood classification** — 15 techno subgenres, запускается внутри `track_features_analyze` handler
- **REST API** (`app/rest/`) — thin FastAPI wrapper поверх MCP для Panel и скриптов
- **Web Panel** (`panel/`) — Next.js 16 + shadcn/ui дашборд: library, playlists, sets, discover, аналитика. Подробности в [docs/panel-guide.md](docs/panel-guide.md)

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
| `mcp` | 20 DJ tools + 27 resources + 6 prompts — построение сетов, аудиоанализ, YM, экспорт (FastMCP v3) |
| `db` | Read-only инспекция БД: схема, SQL, миграции, логи |

Сервер `db` принудительно изолирован (security hardening по [официальным рекомендациям Supabase MCP](https://github.com/supabase-community/supabase-mcp#security-risks)):

- `--read-only` — мутации БД блокируются (выполняются через `mcp`)
- `--project-ref=${DJ_DB_PROJECT_REF}` — scoped к одному проекту (env-driven для marketplace-portability)
- `--features=database,docs,debug` — surface ограничен: SQL, схема, миграции, логи. Account/branches/storage/edge-functions tools отключены

Конфигурация в [.env](.env.example):

```bash
DJ_DB_ACCESS_TOKEN="sbp_..."         # personal access token
DJ_DB_PROJECT_REF="your_project_ref" # из URL Supabase Dashboard
```

> Реализация — `@supabase/mcp-server-supabase@0.7.0` (запускается через `npx`). Токен генерится в [Supabase Dashboard](https://supabase.com/dashboard/account/tokens).

#### Платформенные ограничения

Сервер `db` использует `bash`-wrapper для авто-загрузки `.env` (Claude Code не делает этого нативно). На **Windows без WSL/Git-Bash не запустится** — альтернатива: экспортировать `DJ_DB_ACCESS_TOKEN` в shell вручную и заменить wrapper на нативный `env`-блок в `plugin.json`.

Сервер `mcp` использует нативный `command`/`cwd` — pydantic-settings (`app/config/`) читает `.env` сам, кроссплатформенно.

## Разработка

```bash
uv run pytest -q                           # Тесты (1262 passed)
uv run ruff check && uv run ruff format --check  # Линтер
uv run mypy app/                           # Типы (есть pre-existing tech debt)
uv run lint-imports                        # Архитектурные контракты (5/5)
uv run alembic upgrade head                # Миграции
make check                                 # Всё вместе (lint + typecheck + arch + test)

# Верификация audio pipeline на реальном MP3
uv run python scripts/verify_audio_pipeline.py [path/to/track.mp3]
```

### Panel (Next.js)

```bash
cd panel
cp .env.example .env.local                 # Заполни SUPABASE_URL / ANON_KEY / MCP_HTTP_URL
bun install
bun dev                                    # http://localhost:3000

# Проверка перед PR
bunx tsc --noEmit                          # Типизация
bun run build                              # Production build
```

Backend на `:8000` запускается параллельно через [start.sh](start.sh) или вручную: `uv run --extra http uvicorn app.rest.app:api --port 8000`.

## Архитектура

FastMCP v3 + FileSystemProvider (standalone `@tool` / `@resource` / `@prompt`, auto-discovery):

```text
tools/       # 14 @tool dispatchers (entity/provider/compute/sync/admin) + 6 UI Prefab
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
- **Polymorphism over proliferation.** 20 tools вместо 88 (v0.8) — 14 generic dispatchers + 6 UI Prefab.
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

**Server middleware (15 слоёв):** domain error → ToolError, Sentry context, FastMCP timing, audit log, retry, response limit/caching, deprecation, cost tracking, sampling budget, progress throttle, tool timeout, provider rate limit, DB session (UoW), structured logging.

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
- Bun (для Panel, опционально)
- Опционально: librosa (audio analysis), demucs (stem separation), fastmcp[tasks] (background tasks)

## Документация

| Тема | Документ |
|---|---|
| Архитектурный блюпринт v1 | [docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md](docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md) |
| Bounded contexts + data flow | [docs/architecture.md](docs/architecture.md) |
| MCP tool catalog (20 tools, 27 resources, 6 prompts) | [docs/tool-catalog.md](docs/tool-catalog.md) |
| Audio analysis pipeline L1→L4 | [docs/audio-pipeline.md](docs/audio-pipeline.md) |
| Transition scoring (6-component formula) | [docs/transition-scoring.md](docs/transition-scoring.md) |
| Yandex Music API quirks | [docs/ym-api-guide.md](docs/ym-api-guide.md) |
| DJ-терминология (BPM, Camelot, LUFS, subgenres) | [docs/domain-glossary.md](docs/domain-glossary.md) |
| Panel — пути данных, components, env | [docs/panel-guide.md](docs/panel-guide.md) |

## Лицензия

[MIT](LICENSE) © Evgeny Gurin

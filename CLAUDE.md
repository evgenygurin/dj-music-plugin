# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Quick Start

```bash
uv sync --all-extras                       # Install all deps
make check                                 # lint + typecheck + arch + test
uv run fastmcp run server.py --reload      # MCP dev server (root entrypoint)
cd panel && bun dev                        # Panel on :3000
./start.sh                                 # Both at once
```

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой. Включает веб-панель для мониторинга и аналитики.

- Спецификация: @REQUIREMENTS.md
- Архитектурный блюпринт v1: @docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — bounded-contexts, data flow, ключевые решения v1
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — 13 generic tool dispatchers + 27 resources + 6 prompts
- @docs/audio-pipeline.md — анализаторы, tiered pipeline L1-L4, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 6-компонентная формула, Camelot wheel, section-aware scoring
- @docs/panel-guide.md — Panel архитектура, data flow, компоненты
- @docs/vm-deployment.md — continuous import+analyze loop на VM (systemd-run)
- @docs/reports/tiered-analysis-design-2026-03-27.md — tiered pipeline L1-L4

## Принципы v1

- **MCP — primary interface.** Tools / resources / prompts декларативны, композиция через LLM (prompts, CodeMode, Tool Search), а не императивный service/workflow слой.
- **Polymorphism over proliferation.** 6 generic CRUD tools (`entity_list/get/create/update/delete/aggregate`) + 3 provider tools (`provider_read/write/search`) + 2 compute (`transition_score_pool`, `sequence_optimize`) + `playlist_sync` + `unlock_namespace` = **13 tool dispatchers**. Side-effects живут в handlers, привязанных к entity (create track = import, create audio_file = download, create track_features = analyze, create set_version = build+score).
- **Anchor на DB entities.** Каждый aggregate root → один `models/<entity>.py` + один `repositories/<entity>.py` + одна Pydantic-схема-семейство.
- **Panel (Next.js)** — monitoring/analytics UI, читает напрямую из Supabase, мутации через MCP (REST-обёртка).
- **REST API** (`app/rest/app.py`) — тонкая FastAPI-обёртка поверх MCP для Panel.
- **FastMCP v3.x** — FileSystemProvider auto-discovers tools/resources/prompts, standalone `@tool` / `@resource` / `@prompt` декораторы.
- **Unit of Work.** Одна `UnitOfWork` на tool call, инжектится через `Depends(get_uow)`. DbSession middleware управляет commit/rollback.
- **BaseRepository[M].** Generic CRUD + Django-style lookups (`bpm__gte`, `mood__in`). Entity-specific методы в subclass.
- Python 3.12+, все операции async.
- Strict typing: mypy strict + pydantic v2.
- Тесты обязательны для каждого компонента.
- **Никаких magic numbers** — `app/config/*.py` + `app/shared/constants.py`.

## Архитектура — Bounded Contexts

```text
app/
├── tools/          # @tool — 13 generic dispatchers (entity/provider/compute/sync/admin)
├── resources/      # @resource — 27 URIs (16 local://, 4 schema://, 3 session://, 4 reference://)
├── prompts/        # @prompt — 6 workflow recipes
├── handlers/       # 6 entity-specific side-effects (track_import, track_features_analyze, track_features_reanalyze, audio_file_download, set_version_build, transition_persist)
├── registry/       # EntityRegistry + ProviderRegistry (polymorphism anchors)
├── repositories/   # BaseRepository[M] + UnitOfWork aggregator
├── models/         # SQLAlchemy 2.0 ORM — one file per aggregate root
├── schemas/        # Pydantic DTOs (one family per entity)
├── domain/         # Pure compute, no IO
│   ├── transition/ # 6-component scoring, hard constraints, recipe engine
│   ├── optimization/ # GA, greedy, fitness, protocol
│   ├── camelot/    # Camelot wheel math
│   ├── template/   # Set templates registry
│   └── audit/      # Techno audit rules
├── audio/          # Tiered pipeline (analyzers, classification, level_config)
├── providers/      # External platforms (yandex/ …)
├── server/         # FastMCP composition: app.py, lifespan.py, middleware/, transforms.py, visibility.py, observability.py
├── rest/           # FastAPI wrapper: app.py, lifespan.py, routes/
├── shared/         # errors, constants, filters, ids, pagination, time
└── config/         # Settings split by concern (audio, yandex, database, mcp, …)
```

```text
Panel (Next.js) → REST API (FastAPI) ─┐
                                       ├──→ FastMCP (tools/resources/prompts)
Claude Code (stdio / streamable-http) ─┘       ↓ Depends(get_uow)
                                            UnitOfWork → BaseRepository[M] → models
                                            → Providers (yandex)
                                            → Audio pipeline
                                            → Domain (transition, optimization, …)
```

**Dependency rule (enforced by import-linter):**
- `tools → handlers → repositories → models`
- `tools → domain` (pure compute OK)
- `domain` imports: only `models` (для типизации) + `shared`
- `audio` / `providers` — side-effect layers, imported only by handlers
- `rest` оборачивает MCP через `mcp.call_tool()` — не дублирует бизнес-логику
- `shared` is leaf — нет обратных импортов

## Tiered Audio Analysis (L1→L4)

| Уровень | Когда | Анализаторы |
|---------|-------|-------------|
| L1+L2 (TRIAGE) | classify handler (mood) | loudness, energy, spectral, bpm, key, mfcc |
| L3 (SCORING) | `transition_score_pool`, `sequence_optimize` | + beat |
| L4 (TRANSITION) | `entity_create(entity="audio_file", persistent=true)` | + structure, permanent MP3 |

Детали: @docs/reports/tiered-analysis-design-2026-03-27.md

## Команды

```bash
# Backend (MCP server)
uv sync                                         # Install deps
uv run pytest -v                                # Tests
uv run ruff check && uv run ruff format --check # Lint
uv run mypy app/                                # Type-check
uv run lint-imports                             # Architecture contracts
uv run alembic upgrade head                     # Migrations
uv run fastmcp run server.py --reload           # MCP dev server (root entrypoint)
make check                                      # lint + typecheck + arch + test

# REST API
uv run --extra http uvicorn app.rest.app:api --host 0.0.0.0 --port 8000 --reload

# Panel
cd panel && bun install && bun dev              # http://localhost:3000

# All-in-one
./start.sh                                      # Backend + Panel dev servers
```

## Плагины Claude Code

| Плагин | Когда использовать |
|--------|-------------------|
| **fastmcp-builder** | Перед реализацией tools/resources/prompts |
| **mcp-server-dev** | При проектировании tool patterns, elicitation, auth |
| **superpowers** | Brainstorming, planning, TDD, debugging |
| **feature-dev** | Guided feature development |
| **python** | pytest fixtures, ruff config, mypy |
| **fastapi** | Alembic migrations |
| **tech-lead** | Architecture review, dependency analysis |
| **context7** | Документация библиотек (FastMCP, SQLAlchemy, librosa) |

## Правила архитектуры

- **Bounded contexts** — защищены `import-linter` (`make arch`). Список слоёв см. выше.
- **Один файл = одна ответственность.** Никаких дублирующих файлов.
- **Время:** все datetime-операции через `app/shared/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`).
- **Линтер:** ruff + mypy + import-linter. Pyright игнорируй.
- **FastMCP 3.x:** перед любой работой с tools/lifespan/visibility — читать `.claude/rules/tools.md`, `.claude/rules/resources.md` и `https://gofastmcp.com/llms.txt`.

## ⚠️ Plugin cache ≠ working dir (частый косяк)

Claude Code загружает плагин в `~/.claude/plugins/cache/dj-music-plugin/dj-music/<ver>/` — это **отдельная копия** кода и `.env`. По дефолту MCP сервер стартует оттуда (`${CLAUDE_PLUGIN_ROOT}`), **не** из working dir `/Users/laptop/dev/dj-music-plugin/`.

**Симптомы, когда забыли про это:**
- Правки в `app/` ничего не меняют после auto-reload — плагин крутит старый код из cache.
- Сервер падает `sqlite3.OperationalError: no such table: dj_*` — в cache нет `.env` → pydantic-settings берёт default SQLite вместо Supabase.
- MCP возвращает generic "internal error" на всё — в cache старый `di.py` с sync state API.

**Dev override через env var (официальный механизм):**

`plugin.json` собран так, что обе `mcpServers` команды стартуют из `${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}`. Выстави переменную перед запуском Claude Code — и MCP сервер + Supabase клиент поднимутся из working dir:

```bash
export DJ_PLUGIN_DEV_PATH=/Users/laptop/dev/dj-music-plugin
# затем запусти Claude Code из этого окружения
```

Или один раз в `~/.claude/settings.json` (персистентно для всех сессий):

```json
{ "env": { "DJ_PLUGIN_DEV_PATH": "/Users/laptop/dev/dj-music-plugin" } }
```

Без этой переменной плагин работает как у обычного пользователя — из cache.

**Правило:** никогда не копируй файлы в cache руками и не симлинкай dir целиком — разваливается через пару правок или при version bump. Используй только `DJ_PLUGIN_DEV_PATH`.

## Версия

**v1.0.1** — патч поверх v1.0.0 рефактора по `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md`. Добавлены `provider_write(... operation="set_description")` и hook авто-рестарта MCP на правки плагина. Entrypoint — корневой `server.py` (не `app/server/app.py`).

**v1 surface:** 13 tool dispatchers (6 entity CRUD + 3 provider + 2 compute + 1 sync + 1 admin) + **27 resources** (16 `local://`, 4 `schema://`, 3 `session://`, 4 `reference://`) + 6 prompts + 6 handlers. FastMCP v3 canonical layout (`tools/`, `resources/`, `prompts/`). Polymorphism через EntityRegistry (11 registered entities) + ProviderRegistry + handlers. Unit of Work + BaseRepository[M]. Pure domain (transition / optimization / camelot / template / audit). 18 audio analyzers, tiered L1-L4, section-aware scoring. 16 middleware.

**DB drift:** v1 удалил legacy Python-код (`app/engines/`, `app/ym/`, `app/services/`, `app/controllers/`, `app/bootstrap/` и пр.), но Alembic-миграция `p2_drop_dead_tables` **не применена** к Supabase — 17 dead-таблиц (spotify_\*, beatport_metadata, soundcloud_metadata, embeddings, transition_candidates, dj_saved_loops/cue_points/beatgrid_change_points, dj_set_constraints/feedback, labels, track_labels, app_exports) пока живут в схеме с 0 rows (`app_exports` с 2 устаревшими). Всего 47 live tables.

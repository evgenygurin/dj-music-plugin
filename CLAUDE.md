# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой. Включает веб-панель для мониторинга и аналитики.

- Спецификация: @REQUIREMENTS.md
- Дизайн-документ: @docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — слои, data flow, ключевые решения
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — 50 MCP tools (46 visible + 4 atomic hidden)
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 6-компонентная формула, Camelot wheel, caching
- @docs/panel-guide.md — Panel архитектура, data flow, компоненты
- @docs/vm-deployment.md — continuous import+analyze loop на VM (systemd-run, monitoring, troubleshooting)
- @docs/reports/tiered-analysis-design-2026-03-27.md — спека tiered pipeline (L1-L4)

## Принципы

- MCP — primary interface (tools, resources, prompts)
- Panel (Next.js) — monitoring/analytics UI, reads from Supabase, mutations via MCP
- REST API (`app/api/server.py`) — тонкая FastAPI сборка поверх `app/api/routes/*`, `state.py`, `lifespan.py`, `openapi.py`
- FastMCP v3.x — FileSystemProvider auto-discovers tools/resources/prompts из `app/controllers/` (standalone `@tool`, не `@mcp.tool`)
- Lifespan composition через `|` оператор: `db | ym | analyzer | cache | audio`
- Python 3.12+, все операции async
- Strict typing: mypy strict + pydantic v2
- Тесты обязательны для каждого компонента
- **Никаких magic numbers** — `app/config.py` (`settings.*`), `app/core/constants.py`
- **Запрещённое имя пакета:** `domain/` — bounded-context-pure пакеты лежат top-level (`transition/`, `optimization/`, `templates/`, `audit/`, `export/`, `camelot/`)

## Архитектура — 5 bands + Core

```text
Band 0  Core            cross-cutting (config · constants · errors · utils · middleware)
Band 1  Controllers     MCP tools/prompts/resources + REST routes + Pydantic schemas
Band 2A Services        request-scoped use cases (UoW, services/curation, services/set)
Band 2B Engines         long-lived runtime singletons (DeckEngine × 4, MixerEngine, ...)
Band 3  Pure logic      entities · transition · optimization · templates · mood · camelot · audit
Band 4  Persistence     mappers ⇆ db.repositories ⇆ db.models ⇆ Alembic migrations
Band 5  Infrastructure  yandex client · audio analyzers · sounddevice playback · storage
```

```text
Panel (Next.js) → REST API (FastAPI) ─┐
                                       ├──→ Controllers (FastMCP) → Services → Repositories → DB (Supabase PG)
Claude Code (stdio proxy)             ─┘                          → Engines (singleton runtime)
                                                                  → Infrastructure (YM/audio/playback)
```

```text
app/
├── core/              # Band 0 — config, constants, errors, utils, middleware
│   └── utils/         # time, parsing, pagination, cache, files
├── controllers/       # Band 1 — MCP entry (tools, prompts, resources)
│   ├── tools/         # 64 @tool functions auto-discovered by FSProvider
│   │   ├── _shared/   # taxonomy, resolvers, ToolContext, dispatch, factory
│   │   └── yandex/    # YM API tools (search, tracks, albums, playlists, likes)
│   ├── prompts/workflows/  # split per workflow (build_set, deliver, …)
│   ├── resources/reference/ # split per topic (camelot, templates, subgenres)
│   ├── dependencies/       # Depends() factories split by concern (db, repos, services, audio, external, uow)
│   └── middleware.py
├── bootstrap/         # MCP composition root split: observability, lifespans, transforms, middleware, visibility
├── api/               # Band 1 — FastAPI REST wrapper (server.py + routes/services/state)
├── schemas/           # Band 1 — Pydantic DTOs (catalog, set, deck, mixer, …)
├── services/          # Band 2A — request-scoped use cases
│   ├── set/           # builder, scoring, crud, cheatsheet, facade
│   ├── curation/      # mood, audit, distribution, facade
│   ├── workflows/     # explicit orchestration for import/analyze/build/deliver/sync flows
│   └── *.py           # discovery, delivery, sync, import, search, …
├── engines/           # Band 2B — long-lived runtime (lifespan singletons)
│   ├── deck/          # DeckEngine (state machine), state, playback, eq, fx, cue, loop
│   ├── mixer/         # MixerEngine (crossfader, channels)
│   └── lifespan.py    # @lifespan audio_lifespan
├── entities/          # Band 3 — pure dataclass domain (Entity, ValueObject)
│   ├── audio/         # TrackFeatures + composite VOs
│   └── value_objects/
├── transition/        # Band 3 — 6-component scoring + intent
├── optimization/      # Band 3 — GA, greedy, fitness, protocol
├── templates/         # Band 3 — set templates registry
├── audit/             # Band 3 — techno audit specs
├── export/            # Band 3 — M3U8, Rekordbox, JSON, cheatsheet writers
├── camelot/           # Band 3 — Camelot wheel math
├── audio/             # Band 5 — analysis pipeline (analyzers, classification, level_config)
├── ym/                # Band 5 — Yandex Music client (httpx async, rate limiter, filters)
├── infrastructure/    # Band 5 — storage backend factory
├── db/                # Band 4 — persistence
│   ├── models/        # SQLAlchemy 2.0 ORM (44 моделей)
│   ├── repositories/  # Generic BaseRepository[T] + UnitOfWork aggregator
│   ├── migrations/    # Alembic
│   ├── seed.py        # static reference data (24 keys, 4 providers)
│   └── session.py     # async_session_factory
├── server.py          # Thin FastMCP entry — delegates assembly to bootstrap/server_builder.py
├── config.py          # Settings (env DJ_*)
└── telemetry.py       # Sentry / OTEL
panel/                 # Next.js dashboard (shadcn, Supabase, Recharts)
```

**Dependency rule (закреплено import-linter):**
- `controllers → services/workflows → services → repositories → entities/db.models`
- `services` framework-agnostic (нет fastmcp / app.controllers импортов)
- `transition` / `optimization` pure (нет DB / HTTP / MCP / SQLAlchemy / httpx)
- `core/utils` — leaf, не импортирует ни один app слой

## Команды

```bash
# Backend (MCP server)
uv sync                                    # Install deps
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run lint-imports                        # Architecture contracts (6 contracts)
uv run alembic upgrade head                # Migrations
uv run fastmcp run app/server.py --reload  # MCP dev server (3.x: dev → run)
make check                                 # lint + typecheck + arch + test

# Fallback если uv не в PATH (используй venv напрямую):
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy app/
.venv/bin/python -m ruff check app/ tests/

# REST API
uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload

# Panel
cd panel && bun install && bun dev         # http://localhost:3000

# All-in-one
./start.sh                                 # Backend + Panel dev servers
```

## Плагины Claude Code

| Плагин | Когда использовать |
|--------|-------------------|
| **fastmcp-builder** | Перед реализацией MCP tools/resources/prompts |
| **mcp-server-dev** | При проектировании tool patterns, elicitation, auth |
| **superpowers** | Brainstorming, planning, TDD, debugging |
| **feature-dev** | Guided feature development с пониманием codebase |
| **python** | pytest fixtures, ruff config, mypy |
| **fastapi** | Alembic migrations (fastapi plugin имеет migrate-* скиллы) |
| **tech-lead** | Architecture review, dependency analysis |
| **context7** | Документация библиотек (FastMCP, SQLAlchemy, librosa) |
| **commit-commands** | Git commit workflow |

## Правила архитектуры

- **5 bands + Core** — см. `docs/architecture.md` и dependency rule выше. Защищено `import-linter` (`make arch`)
- **Запрещённое имя `domain`** — bounded-context-pure пакеты top-level (`transition/`, `optimization/`, …)
- **Один файл = одна ответственность.** НИКОГДА не создавать дублирующие файлы (например `middleware.py` + `custom_middleware.py`)
- **Время:** все datetime-операции через `app/core/utils/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`). Не используй `datetime.now()` / `func.now()` напрямую
- **Линтер:** ruff + mypy + import-linter. Pyright игнорируй — он выдаёт ложные ошибки (reportMissingImports, reportCallIssue на @tool)
- **FastMCP 3.x:** перед любой работой с tools/lifespan/dependencies/visibility — читать `.claude/rules/fastmcp.md` и docs из `https://gofastmcp.com/llms.txt`. См. `docs/refactor-v2.md` для locked decisions

## Tiered Audio Analysis (L1→L4)

| Уровень | Когда | Анализаторы |
|---------|-------|-------------|
| L1+L2 (TRIAGE) | `classify_mood`, `audit_playlist` | loudness, energy, spectral, bpm, key, mfcc |
| L3 (SCORING) | `build_set`, `score_transitions` | + beat |
| L4 (TRANSITION) | `deliver_set` | + structure, permanent MP3 |

Детали: @docs/reports/tiered-analysis-design-2026-03-27.md

## Версия

Plugin v0.6.0, 50 tools (46 visible + 4 atomic hidden), 20 audio analyzers (8 core + 6 P1 + 4 P2 essentia/librosa + phrase + bpm_histogram), two-phase pipeline, context-aware 6-component scoring, tiered analysis (L1-L4), FileSystemProvider, modular bootstrap/api/di/workflows architecture.

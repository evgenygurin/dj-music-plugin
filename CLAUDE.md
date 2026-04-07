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
- @docs/reports/tiered-analysis-design-2026-03-27.md — спека tiered pipeline (L1-L4)

## Принципы

- MCP — primary interface (tools, resources, prompts)
- Plugin поднимает **два MCP сервера**: `mcp` (FastMCP, 50 DJ tools) + `db` (`@supabase/mcp-server-supabase`, read-only, scoped к проекту)
- Panel (Next.js) — monitoring/analytics UI, reads from Supabase, mutations via MCP
- REST API (serve_http.py) — тонкая FastAPI обёртка для panel→MCP коммуникации
- FastMCP v3.1 — FileSystemProvider auto-discovers tools (standalone `@tool`, не `@mcp.tool`)
- Python 3.12+, все операции async
- Strict typing: mypy strict + pydantic v2
- Тесты обязательны для каждого компонента
- **Никаких magic numbers** — все настройки в `app/config.py` (`settings.*`), все константы в `app/core/constants.py`

## Архитектура

```text
Panel (Next.js) → REST API (FastAPI) → MCP Server (FastMCP) → DB (Supabase PostgreSQL)
     ↓ reads                                                        ↑
     └──────────────── Supabase direct queries ─────────────────────┘
```

```text
app/models/             → SQLAlchemy модели (данные)
app/repositories/       → Data access (flush, never commit)
app/services/           → Business logic (domain errors, no MCP imports)
app/mcp/tools/          → MCP tools (standalone @tool, FSProvider auto-discovers)
app/mcp/tools/_shared/  → Tool infra: taxonomy, resolvers, ToolContext, dispatch
app/mcp/tools/yandex/   → YM API tools split by entity (search/tracks/albums/...)
app/mcp/schemas/        → Tool-only Pydantic models (LLM sampling)
app/mcp/resources/      → MCP resources (read-only data views)
app/mcp/prompts/        → Workflow prompt templates
app/audio/              → Audio analysis, tiered pipeline, level config
app/ym/                 → Yandex Music client (async httpx)
app/core/               → Shared: errors, constants, schemas, ym_filters
panel/                  → Next.js dashboard (shadcn, Supabase, Recharts)
serve_http.py           → FastAPI REST API wrapper
```

Правило: каждый слой импортирует только слой ниже. Tools → Services → Repositories → Models.

## Команды

```bash
# Backend (MCP server)
uv sync                                    # Install deps
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run alembic upgrade head                # Migrations
uv run fastmcp dev app/server.py --reload  # MCP dev server
make check                                 # lint + typecheck + test

# REST API
uv run --extra http uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload

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

- **Один файл = одна ответственность.** НИКОГДА не создавать дублирующие/расширяющие файлы (например `middleware.py` + `custom_middleware.py`). Если нужно расширить — расширяй в том же файле
- **Время:** все datetime-операции через `app/utils/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`). Не используй `datetime.now()` / `func.now()` напрямую
- **Линтер:** ruff + mypy. Pyright **игнорируй** — он выдаёт ложные ошибки (reportMissingImports, reportCallIssue на @tool). VSCode Pyright предупреждения — НЕ баги

## Tiered Audio Analysis (L1→L4)

| Уровень | Когда | Анализаторы |
|---------|-------|-------------|
| L1+L2 (TRIAGE) | `classify_mood`, `audit_playlist` | loudness, energy, spectral, bpm, key, mfcc |
| L3 (SCORING) | `build_set`, `score_transitions` | + beat |
| L4 (TRANSITION) | `deliver_set` | + structure, permanent MP3 |

Детали: @docs/reports/tiered-analysis-design-2026-03-27.md

## Версия

Plugin v0.5.0, 50 tools (46 visible + 4 atomic hidden), 18 audio analyzers (8 core + 6 P1 + 4 P2 essentia/librosa), two-phase pipeline, context-aware 6-component scoring, tiered analysis (L1-L4), FileSystemProvider.

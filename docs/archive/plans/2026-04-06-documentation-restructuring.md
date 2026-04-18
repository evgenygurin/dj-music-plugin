# Documentation Restructuring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure CLAUDE.md (218→~100 lines), create 5 new rules/ files, update 4 existing rules/, update 2 docs, create 1 new doc — zero gotchas lost.

**Architecture:** Three-layer documentation: CLAUDE.md (compact entry point with links) → .claude/rules/ (modular per-domain rules with frontmatter) → docs/ (deep reference docs). Gotchas from CLAUDE.md are distributed to thematic rules/ files.

**Tech Stack:** Markdown files only. No code changes.

---

### Task 1: Create new rules/ files (5 files)

**Files:**
- Create: `.claude/rules/panel.md`
- Create: `.claude/rules/rest-api.md`
- Create: `.claude/rules/supabase.md`
- Create: `.claude/rules/llm-sampling.md`
- Create: `.claude/rules/gotchas.md`

- [ ] **Step 1: Create `.claude/rules/panel.md`**

```markdown
---
description: Next.js panel conventions and patterns
globs: panel/**/*
---

# Panel (Next.js)

- **Framework**: Next.js 16 with app router, server components by default
- **Package manager**: bun (not npm/yarn). Run `bun install`, `bun dev`, `bun build`
- **UI library**: shadcn/ui (Base UI + Tailwind v4). Config in `panel/components.json`
- **Icons**: @tabler/icons-react (not lucide for custom icons)
- **Charts**: Recharts with cyberpunk neon theme (magenta/cyan gradients)
- **Theme**: Dark mode default via next-themes (class-based). Cyberpunk aesthetic with `--primary` magenta and `--chart-*` neon colors
- **Fonts**: Local Geist (sans + mono) from `app/fonts/`, not Google Fonts

## Directory Structure

- `app/` — Pages (dashboard, library, playlists, sets, discover). App router with `page.tsx` + `layout.tsx`
- `actions/` — Server actions for MCP mutations (analysis, discovery, set-building, sync). Each calls MCP via `mcpCall()` from `lib/mcp-client.ts`
- `components/` — Shared UI: `charts/` (5 Recharts visualizations), `ui/` (25+ shadcn components), domain components (data-table, mood-badge, track-features, transition-table)
- `lib/queries/` — Supabase read queries (dashboard stats, tracks, playlists, sets). Direct SQL via Supabase client, not ORM
- `lib/supabase/` — SSR-compatible Supabase client (`createClient()` with Next.js cookies)
- `lib/mcp-client.ts` — HTTP wrapper for MCP tool calls via REST API (`MCP_HTTP_URL`)
- `lib/constants.ts` — Subgenre colors and labels

## Data Flow

- **Reads**: Page server components → `lib/queries/*.ts` → Supabase PostgreSQL (direct)
- **Writes/Mutations**: Server actions → `lib/mcp-client.ts` → REST API (serve_http.py) → MCP Server → DB

## Env Vars

- `NEXT_PUBLIC_SUPABASE_URL` — Supabase endpoint
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon JWT
- `MCP_HTTP_URL` — MCP REST API (default: http://localhost:8000)
```

- [ ] **Step 2: Create `.claude/rules/rest-api.md`**

```markdown
---
description: REST API wrapper patterns (serve_http.py)
globs: serve_http.py
---

# REST API (FastAPI Wrapper)

- `serve_http.py` is a thin wrapper exposing MCP tools over HTTP — **never duplicate business logic here**
- All business logic lives in MCP tools/services. REST API only proxies `mcp.call_tool()`
- Run: `uv run --extra http uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload`

## Endpoints

- `GET /api/health` — server status + tool count + MCP readiness
- `GET /api/tools` — list all tools with inputSchema (filter: `?tag=core`)
- `GET /api/tools/{name}` — single tool metadata
- `GET /api/tools/{name}/schema` — JSON Schema for form generation
- `POST /api/tools/{name}/call` — execute tool with `{"arguments": {...}}`
- `POST /mcp` — native MCP StreamableHTTP transport

## Patterns

- Tool discovery is static (at import time via FileSystemProvider) — no DB needed for Swagger
- MCP lifespan failure is graceful: discovery works, execution returns 503
- CORS allows `localhost:3000` (panel dev) and `*.vercel.app` (production)
- Pydantic models: `ToolCallRequest`, `ToolCallResponse`, `ToolInfo`, `ToolListResponse`
```

- [ ] **Step 3: Create `.claude/rules/supabase.md`**

```markdown
---
description: Supabase query patterns for panel
globs: panel/lib/supabase/**/*.ts, panel/lib/queries/**/*.ts
---

# Supabase Queries

- Direct SQL queries via `@supabase/supabase-js` — no ORM, no Prisma
- SSR client: `createClient()` from `lib/supabase/server.ts` (uses Next.js cookies for auth)
- **RLS disabled** on all tables — queries run with anon key, no row-level filtering
- Connection via env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Query Patterns

- Queries live in `lib/queries/` organized by domain: `dashboard.ts`, `tracks.ts`, `playlists.ts`, `sets.ts`
- Each query function creates its own Supabase client: `const supabase = await createClient()`
- Use Supabase query builder: `.from('table').select('columns').eq('col', val)`
- For joins use select with relations: `.select('*, artists:track_artists(artist:artists(name))')`
- Return typed results — define interfaces in the same query file
- Handle errors: check `error` field, throw or return empty defaults
```

- [ ] **Step 4: Create `.claude/rules/llm-sampling.md`**

```markdown
---
description: LLM sampling modes for AI-assisted tools
globs: app/mcp/tools/discovery.py
---

# LLM Sampling

Two modes for LLM-assisted tools (`find_similar_tracks` strategy="llm"):

## 1. Client-driven (default — Claude Code MAX)

Claude Code IS the LLM — it generates search queries and passes them as tool params:

```python
find_similar_tracks(
    track_id=42,
    strategy="llm",
    search_queries=["Amelie Lens acid techno", "FJAAK industrial"]
)
```

Use prompt `llm_discovery_workflow` for step-by-step instructions.

**Why**: Claude Code doesn't support MCP sampling (`createMessage`) — `ctx.sample()` can't call back to the client.

## 2. Server-side (requires `DJ_ANTHROPIC_API_KEY`)

`ctx.sample()` calls Anthropic API via fallback handler. For headless/automated scenarios.

## Gotchas

- `ctx.sample()` does NOT work in Claude Code — always use client-driven mode
- Client-driven mode requires the caller to be an LLM (Claude Code, not a script)
```python

- [ ] **Step 5: Create `.claude/rules/gotchas.md`**

```markdown
---
description: General Python gotchas not tied to a specific domain
globs: "**/*.py"
---

# General Python Gotchas

## `from __future__ import annotations`

Makes all annotations strings at runtime. If a function needs the actual type at runtime (e.g., `TrackFeatures()` as a default), import the type normally — don't rely on the string annotation.

## Circular imports

repos→services circular imports: use `TYPE_CHECKING` guard + lazy import inside the method body:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.track import TrackService

class TrackRepo:
    def method(self) -> None:
        from app.services.track import TrackService  # lazy
        ...
```

## Ruff removes unused imports

Ruff auto-removes imports that aren't used yet. When adding an import + its usage, do both in a single edit — don't add the import first and the usage later.
```text

- [ ] **Step 6: Commit new rules/ files**

```bash
git add .claude/rules/panel.md .claude/rules/rest-api.md .claude/rules/supabase.md .claude/rules/llm-sampling.md .claude/rules/gotchas.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```bash
docs(rules): add panel, rest-api, supabase, llm-sampling, gotchas rules

Five new .claude/rules/ files for recently added components:
panel (Next.js), REST API wrapper, Supabase queries, LLM sampling
modes, and general Python gotchas.
```

---

### Task 2: Update existing rules/ files (transfer gotchas)

**Files:**
- Modify: `.claude/rules/tools.md`
- Modify: `.claude/rules/ym.md`
- Modify: `.claude/rules/audio.md`
- Modify: `.claude/rules/repositories.md`
- Modify: `.claude/rules/models.md`
- Modify: `.claude/rules/config.md`

- [ ] **Step 1: Update `.claude/rules/tools.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- `Depends()`: use `param=Depends(factory)`, NOT `Annotated[Type, Depends(factory)]` — FastMCP doesn't resolve Annotated
- `list_page_size` in config must be >= tool count (100) — Claude Code doesn't follow nextCursor
- Hidden tools: after `unlock_tools`, Claude Code doesn't reload tool list — hidden tools (audio, atomic) only accessible via script `Client(mcp)`
- `download_tracks` refs: accepts YM track IDs (`"135055088"`) or local IDs (auto-resolves via `resolve_local_ids_to_ym`). Numbers < 100000 = local, >= 100000 = YM
- `download_tracks` automatically creates `DjLibraryItem` via `_link_file_to_track()` — no manual linking needed
- `score_delivery_transitions` returns `tuple[int, int]` (scored, conflicts), NOT dict
- `build_set` without features: fallback to `playlist_order` (not greedy/ga) — correct behavior
- `get_set` tracks view: includes `artist_names` via batch query (`get_by_ids` batch, not N+1)
- `TransitionIntent`: context-aware enum (maintain/ramp_up/cool_down/contrast) affects GA optimizer weights by track position
- `score_timbral`: 6th component of TransitionScorer (weight 0.10), total weights = 1.0 (bpm 0.22 + harmonic 0.20 + energy 0.23 + spectral 0.15 + groove 0.10 + timbral 0.10)
```

- [ ] **Step 2: Update `.claude/rules/ym.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- Search API: `type=tracks` (plural), not `type=track`
- Playlist add_tracks: albumId resolves automatically via `ym.resolve_track_ids_with_albums()` — pass bare track IDs, `"trackId:albumId"` formatting happens under the hood
- `ym_playlists` supports `action=get_tracks` (returns tracks with id/title/artists) and working `action=remove_tracks` (removes by track_id, not by index)
```

- [ ] **Step 3: Update `.claude/rules/audio.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- `classify_mood` and `distribute_to_subgenres` persist `mood` and `mood_confidence` to `track_audio_features_computed`
- Pipeline features → DB: always use `TrackAudioFeaturesComputed.filter_features(result.features)` — pipeline may return keys without columns
- Tiered auto-trigger: `classify_mood`/`build_set`/`deliver_set` auto-analyze tracks — no need to call `analyze_track` manually
- P1 analyzers: essentia DFA danceability is unbounded (not 0-1), dissonance 0-1, dynamic_complexity 0-~10
- P2 analyzers: SpectralComplexityAnalyzer, PitchSalienceAnalyzer depend on essentia; BpmHistogramAnalyzer depends on `beat` (depends_on); PhraseAnalyzer depends on `beat` + `bpm`
- `depends_on`: `ClassVar[frozenset[str]]` — Phase 2 pipeline passes `prior_results` to dependent analyzers
- `_ANALYZER_REGISTRY`: global dict, `importlib` doesn't re-register decorator on re-import — in tests delete only `_test_*` keys, never `clear()`
- Beat analyzer: processes first `settings.audio_beat_analysis_duration` seconds (default 60), not the entire track
- MP3 analysis: requires `uv sync --extra audio` (librosa + soundfile)
```

- [ ] **Step 4: Update `.claude/rules/repositories.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- `AsyncSession.delete()` IS async in SQLAlchemy 2.0 — `await` is correct
```

- [ ] **Step 5: Update `.claude/rules/models.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- Energy band column names: `energy_sub`, `energy_lowmid`, `energy_highmid` (not `energy_band_*`, not `energy_low_mid`)
```

- [ ] **Step 6: Update `.claude/rules/config.md`**

Append after the last existing bullet:

```markdown

## Gotchas

- Background tasks: `task=True` requires `pip install 'fastmcp[tasks]'`
- Error masking: `mask_error_details=not settings.debug` in production
```

- [ ] **Step 7: Commit updated rules/**

```bash
git add .claude/rules/tools.md .claude/rules/ym.md .claude/rules/audio.md .claude/rules/repositories.md .claude/rules/models.md .claude/rules/config.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```bash
docs(rules): transfer gotchas from CLAUDE.md to thematic rules

Distribute 30 gotchas from monolithic CLAUDE.md list into their
domain-specific .claude/rules/ files for better discoverability.
```

---

### Task 3: Rewrite CLAUDE.md (compact entry point)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace CLAUDE.md with compact version**

Full replacement content:

```markdown
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
app/models/       → SQLAlchemy модели (данные)
app/repositories/ → Data access (flush, never commit)
app/services/     → Business logic (domain errors, no MCP imports)
app/mcp/tools/    → MCP tools (standalone @tool, FileSystemProvider auto-discovers)
app/mcp/resources/ → MCP resources (read-only data views)
app/mcp/prompts/  → Workflow prompt templates
app/audio/        → Audio analysis, tiered pipeline, level config, temp download
app/ym/           → Yandex Music client (async httpx)
app/core/         → Shared: errors, constants, pagination, entity resolver
panel/            → Next.js dashboard (shadcn, Supabase, Recharts)
serve_http.py     → FastAPI REST API wrapper
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
```text

- [ ] **Step 2: Verify line count**

Run: `wc -l CLAUDE.md`
Expected: ~95-100 lines (down from 218)

- [ ] **Step 3: Commit rewritten CLAUDE.md**

```bash
git add CLAUDE.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```bash
docs: compact CLAUDE.md from 218 to ~95 lines

Remove duplicated patterns (now in .claude/rules/), gotchas (distributed
to thematic rules/), and implementation details (in docs/). Add panel,
REST API, and Supabase references.
```

---

### Task 4: Update docs/architecture.md

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Replace docs/architecture.md with updated version**

Full replacement content:

```markdown
# Architecture

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    MCP Clients (Claude, etc.)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio / streamable-http
┌──────────────────────────▼──────────────────────────────────┐
│                   FastMCP v3.1 Server                        │
│  ┌─────────────┐ ┌────────────┐ ┌─────────────────────────┐│
│  │ Middleware   │ │ Transforms │ │ Visibility System       ││
│  │ (logging,    │ │ (namespace,│ │ (core/extended/hidden)  ││
│  │  rate limit, │ │  R→T, P→T) │ │                         ││
│  │  timing)     │ │            │ │                         ││
│  └──────┬───────┘ └────────────┘ └─────────────────────────┘│
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────────┐│
│  │              FileSystemProvider (auto-discover)          ││
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐││
│  │  │ 50 Tools │  │ 9 Resources│  │ 5 Workflow Prompts   │││
│  │  └────┬─────┘  └──────┬─────┘  └──────────────────────┘││
│  └───────┼───────────────┼─────────────────────────────────┘│
└──────────┼───────────────┼──────────────────────────────────┘
           │               │
    ┌──────▼───────┐ ┌─────▼──────┐
    │ DI (Depends) │ │ DI (Depends)│
    └──────┬───────┘ └─────┬──────┘
           │               │
    ┌──────▼───────────────▼──────┐
    │        Service Layer         │
    │  TrackService, SetService,   │
    │  TransitionScorer, Optimizer,│
    │  MoodClassifier, Exporter    │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │      Repository Layer         │
    │  TrackRepo, SetRepo,          │
    │  PlaylistRepo, FeatureRepo    │
    │  (flush only, never commit)   │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │    SQLAlchemy 2.0 Async       │
    │  Supabase PostgreSQL (prod)   │
    │  SQLite (test, in-memory)     │
    │  44 tables, Alembic migrations│
    └──────────────────────────────┘

External:
    ┌──────────────────────────────┐
    │  Yandex Music API (httpx)    │
    │  Rate limited, OAuth token   │
    └──────────────────────────────┘
    ┌──────────────────────────────┐
    │  Audio Files (filesystem)    │
    │  librosa, essentia (optional)│
    └──────────────────────────────┘
```

## Panel & REST API Layer

```text
┌──────────────────────────────────────────┐
│  Panel (Next.js 16, Bun)                 │
│  http://localhost:3000                   │
│  ┌──────────┐  ┌───────────────────────┐│
│  │ Pages    │  │ Server Actions        ││
│  │ (SSR)    │  │ (analysis, discovery, ││
│  │          │  │  sets, sync)          ││
│  └────┬─────┘  └──────────┬────────────┘│
│       │ reads              │ mutations   │
└───────┼────────────────────┼─────────────┘
        │                    │
        ▼                    ▼
┌───────────────┐  ┌─────────────────────────┐
│ Supabase      │  │ REST API (FastAPI)       │
│ PostgreSQL    │  │ serve_http.py            │
│ (direct SQL)  │  │ http://localhost:8000    │
└───────────────┘  │ ┌─────────────────────┐ │
                   │ │ /api/tools — list    │ │
                   │ │ /api/tools/N/call    │ │
                   │ │ /mcp — native MCP    │ │
                   │ └────────┬────────────┘ │
                   └──────────┼──────────────┘
                              │ mcp.call_tool()
                   ┌──────────▼──────────────┐
                   │  FastMCP Server          │
                   │  (same as above)         │
                   └──────────────────────────┘
```

## Data Flow: Tool Call Lifecycle

```text
1. Client sends tool call → FastMCP
2. Middleware pipeline: log → timing → rate limit → response limit → retry → error masking
3. FastMCP resolves tool via FileSystemProvider
4. DI chain activates:
   get_db_session() → get_*_repo() → get_*_service()
   (all cached per-request, same session across all repos)
5. Tool function executes with injected services
6. On success: session.commit() (in get_db_session finally)
7. On error: session.rollback() (in get_db_session except)
8. ToolResult → structuredContent + content + meta
9. Response through middleware (timing recorded, logged)
10. Back to client
```

## Startup Flow

```text
./start.sh
├── Backend: uv run uvicorn serve_http:api --port 8000
│   └── MCP lifespan: DB connection, YM client, analyzer registry
└── Panel: cd panel && bun dev --port 3000
    └── Connects to Supabase + MCP_HTTP_URL
```

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| FileSystemProvider over manual registration | Zero boilerplate, hot reload in dev, tools are just Python files |
| Depends() for DI over global state | Per-request session scoping, testable, no thread-safety issues |
| Services ≠ Tools | Services are framework-agnostic, reusable outside MCP |
| Repos flush, never commit | Transaction boundary at tool level via DI, not scattered in business logic |
| Pydantic models for tool returns | Automatic structuredContent, type-safe, self-documenting |
| Settings class over raw env vars | Type-checked, documented defaults, testable overrides |
| Visibility tiers over all-tools-visible | ~5K tokens in context vs ~9K, better Claude accuracy |
| TrackFeatures.from_db() classmethod | Single source of truth for DB→dataclass mapping, eliminates field copy-paste |
| FeatureRepository batch methods | N SQL queries → 1 for scoring/optimization loops |
| Panel reads Supabase directly | Avoids MCP overhead for read-only dashboard data |
| REST API wrapper over direct MCP | Panel needs HTTP transport; Swagger docs for debugging |
| Supabase PostgreSQL over SQLite | Production-grade, panel reads directly, RLS available |
```text

- [ ] **Step 2: Commit updated architecture.md**

```bash
git add docs/architecture.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```sql
docs: update architecture with panel, REST API, and Supabase

Add Panel + REST API layer diagram, startup flow, Supabase PostgreSQL
as production DB, and three new architectural decisions.
```

---

### Task 5: Update docs/transition-scoring.md

**Files:**
- Modify: `docs/transition-scoring.md`

- [ ] **Step 1: Update formula and weights section**

Replace the formula block (lines 3-20) with:

```markdown
6-component weighted formula for evaluating track-to-track transitions.

## Formula

```text
score = w_bpm * S_bpm + w_harmonic * S_harmonic + w_energy * S_energy
      + w_spectral * S_spectral + w_groove * S_groove + w_timbral * S_timbral
```

Default weights (from `app/core/constants.py`):

| Component | Weight | Purpose |
|-----------|--------|---------|
| BPM | 0.22 | Tempo compatibility |
| Harmonic | 0.20 | Key compatibility (Camelot) |
| Energy | 0.23 | Energy flow (LUFS) |
| Spectral | 0.15 | Timbral similarity (MFCC + centroid + bands) |
| Groove | 0.10 | Rhythmic compatibility |
| Timbral | 0.10 | Timbral texture matching |

Total weights = 1.0
```bash

- [ ] **Step 2: Add S_timbral section**

Insert after the S_groove section (after line 83):

```markdown

### S_timbral — Timbral Texture

6th scoring component added for finer timbral discrimination:

```text
S_timbral = timbral_texture_similarity(features_a, features_b)
```

Uses spectral complexity, pitch salience, and energy band correlation for deeper timbral matching beyond MFCC cosine similarity.

### TransitionIntent — Context-Aware Scoring

Enum that modifies scoring weights based on track position in the set:

| Intent | When | Effect |
|--------|------|--------|
| `maintain` | Mid-set, same energy | Favor similar tracks |
| `ramp_up` | Building energy | Favor higher energy target |
| `cool_down` | After peak | Favor lower energy target |
| `contrast` | Deliberate shift | Relax similarity constraints |

The GA optimizer assigns intent per position based on the template's energy arc.
```bash

- [ ] **Step 3: Update Transition Cache section**

Replace `5 components + overall` with `6 components + overall` in the cache description (line 131).

- [ ] **Step 4: Commit**

```bash
git add docs/transition-scoring.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```sql
docs: update transition scoring to 6 components + TransitionIntent

Add timbral component (weight 0.10), update weights to current values
(total 1.0), and document TransitionIntent context-aware scoring.
```

---

### Task 6: Create docs/panel-guide.md

**Files:**
- Create: `docs/panel-guide.md`

- [ ] **Step 1: Create docs/panel-guide.md**

```markdown
# Panel Guide

Next.js dashboard for monitoring and analytics of the DJ music library.

## Stack

| Tech | Version | Purpose |
|------|---------|---------|
| Next.js | 16 | App router, SSR, server actions |
| Bun | — | Package manager and runtime |
| shadcn/ui | — | Component library (Base UI + Tailwind v4) |
| Supabase | — | PostgreSQL queries (direct, no ORM) |
| Recharts | — | Chart visualizations |
| TanStack Table | — | Client-side table sorting/filtering |
| @tabler/icons-react | — | Icon library |

## Pages

| Route | Page | Data Source |
|-------|------|-------------|
| `/` | Dashboard | `queries/dashboard.ts` — stats, BPM/LUFS/mood/key distributions, analysis coverage |
| `/library` | Track list | `queries/tracks.ts` — paginated, filterable, sortable table |
| `/library/[id]` | Track detail | `queries/tracks.ts` — full track with artists, features, sections, cue points, YM metadata |
| `/playlists` | Playlist list | `queries/playlists.ts` — with track counts |
| `/playlists/[id]` | Playlist detail | Playlist tracks with features |
| `/sets` | Set list | `queries/sets.ts` — with version info |
| `/sets/[id]` | Set detail | Set tracks, transitions, energy arc |
| `/discover` | YM Search | Server action `ymSearch` → MCP `ym_search` |

## Data Flow

```text
READ path (dashboard, listings):
  Page (server component) → lib/queries/*.ts → Supabase PostgreSQL

WRITE path (mutations):
  User action → Server action (actions/*.ts) → lib/mcp-client.ts
    → HTTP POST /api/tools/{name}/call → serve_http.py → MCP Server → DB
```

## Server Actions

| File | Actions | MCP Tools Called |
|------|---------|-----------------|
| `analysis-actions.ts` | classifyMood, analyzeTrack | classify_mood, analyze_track |
| `discovery-actions.ts` | ymSearch, importTracks | ym_search, import_tracks |
| `set-actions.ts` | buildSet, rebuildSet, deliverSet, scoreTransitions | build_set, rebuild_set, deliver_set, score_transitions |
| `sync-actions.ts` | syncPlaylist | sync_playlist |

All actions use `mcpCall(toolName, args)` from `lib/mcp-client.ts` which POSTs to `MCP_HTTP_URL`.

## Components

### Charts (`components/charts/`)

| Component | Visualization | Data |
|-----------|--------------|------|
| BpmDistribution | Histogram (bar) | BPM buckets from tracks |
| LufsRange | Histogram (bar) | LUFS level distribution |
| MoodDistribution | Pie/donut | Subgenre classification counts |
| CamelotWheel | Radial | Key distribution across 24 keys |
| EnergyArc | Line | Energy curve across set tracks |

All use Recharts with cyberpunk neon gradient styling.

### Domain Components

| Component | Purpose |
|-----------|---------|
| `data-table.tsx` | TanStack React Table wrapper with sorting, filtering, pagination |
| `mood-badge.tsx` | Colored badge per subgenre (colors from `lib/constants.ts`) |
| `track-features.tsx` | Tabbed display of audio features (tempo, loudness, energy, spectral, rhythm) |
| `section-cards.tsx` | Track structure sections (intro, drop, breakdown, etc.) |
| `sections-timeline.tsx` | Visual timeline of track sections |
| `transition-table.tsx` | Set transitions with scores, pins, conflict indicators |
| `app-sidebar.tsx` | Navigation sidebar with vinyl logo, tooltips, version footer |

### UI Components (`components/ui/`)

25+ shadcn components. Do not modify these directly — use `bunx shadcn@latest add <component>` to add new ones.

## Theme

- Dark mode default (class-based via `next-themes`)
- Cyberpunk aesthetic: magenta primary, cyan/green/amber accents
- Custom CSS variables in `globals.css` for chart colors
- Geist fonts (sans + mono) loaded locally from `app/fonts/`

## Dev Setup

```bash
cd panel
cp .env.example .env.local    # Set Supabase URL + key + MCP URL
bun install
bun dev                        # http://localhost:3000
```

Requires running backend: `uv run uvicorn serve_http:api --port 8000`
```text

- [ ] **Step 2: Commit**

```bash
git add docs/panel-guide.md
git commit -F /tmp/commit-msg.txt
```

Commit message:
```bash
docs: add panel guide with architecture, pages, and components

Comprehensive documentation for the Next.js dashboard: stack, pages,
data flow, server actions, components, theme, and dev setup.
```

---

### Task 7: Verification — no gotchas lost

**Files:** None (read-only verification)

- [ ] **Step 1: Count gotchas in CLAUDE.md**

Run: `grep -c "^- " CLAUDE.md` in the Gotchas-equivalent sections
Expected: 0 (no gotchas remain in CLAUDE.md)

- [ ] **Step 2: Count gotchas across rules/**

Run: `grep -c "^- " .claude/rules/tools.md .claude/rules/ym.md .claude/rules/audio.md .claude/rules/repositories.md .claude/rules/models.md .claude/rules/config.md .claude/rules/gotchas.md .claude/rules/llm-sampling.md`

Expected: total ≥ 30 gotcha bullets distributed across files

- [ ] **Step 3: Verify CLAUDE.md line count**

Run: `wc -l CLAUDE.md`
Expected: ≤ 100 lines

- [ ] **Step 4: Verify all rules/ have frontmatter**

Run: `head -3 .claude/rules/*.md`
Expected: every file starts with `---` frontmatter block

- [ ] **Step 5: Spot-check architecture.md has Panel section**

Run: `grep -c "Panel" docs/architecture.md`
Expected: ≥ 3 occurrences

- [ ] **Step 6: Spot-check transition-scoring.md has 6 components**

Run: `grep -c "timbral\|Timbral" docs/transition-scoring.md`
Expected: ≥ 2 occurrences

- [ ] **Step 7: Final commit (if any fixups needed)**

Only if verification found issues — fix and commit.

# Architecture

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    MCP Clients (Claude, etc.)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio / streamable-http
┌──────────────────────────▼──────────────────────────────────┐
│                   FastMCP v3.2 Server                        │
│  ┌─────────────┐ ┌────────────┐ ┌─────────────────────────┐│
│  │ Middleware   │ │ Transforms │ │ Visibility System       ││
│  │ (logging,    │ │ (ToolTrans-│ │ (core/extended/hidden)  ││
│  │  rate_limit, │ │  form,     │ │ per-session via         ││
│  │  timing,     │ │  R→T, P→T) │ │ ctx.enable_components() ││
│  │  resp_limit, │ │            │ │                         ││
│  │  caching)    │ │            │ │                         ││
│  └──────┬───────┘ └────────────┘ └─────────────────────────┘│
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────────┐│
│  │              FileSystemProvider (auto-discover)          ││
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐││
│  │  │  Tools   │  │ Resources  │  │  Workflow Prompts    │││
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
    │  Supabase PostgreSQL          │
    │  SQLite (tests only, in-mem)  │
    │  Alembic migrations            │
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
│ Supabase      │  │ REST API (FastAPI)      │
│ PostgreSQL    │  │ app/api/server.py       │
│ (direct SQL)  │  │ http://localhost:8000   │
└───────────────┘  │ ┌─────────────────────┐ │
                   │ │ routes/*.py         │ │
                   │ │ state.py            │ │
                   │ │ openapi.py          │ │
                   │ │ lifespan.py         │ │
                   │ └────────┬────────────┘ │
                   └──────────┼──────────────┘
                              │ mcp.call_tool()
                   ┌──────────▼──────────────┐
                   │ FastMCP Server          │
                   │ app/server.py           │
                   │ -> bootstrap/builder    │
                   └─────────────────────────┘
```

## Middleware Pipeline (ordered)

```text
DereferenceRefsMiddleware       # FastMCP built-in
ErrorHandlingMiddleware         # structured error wrapping + Sentry
RetryMiddleware                 # up to 2 retries on transient errors
ResponseLimitingMiddleware      # truncate oversized responses (50 KB)
ResponseCachingMiddleware       # cache list_tools/list_prompts/list_resources
YMRateLimitMiddleware           # Yandex Music API rate limiting
ToolCallTimeoutMiddleware       # per-tool timeouts (heavy ops)
DetailedTimingMiddleware        # per-tool timing breakdown
DjMcpRpcLoggingMiddleware       # JSON-ish logs via mcp_extra (innermost)
```

## Data Flow: Tool Call Lifecycle

```text
1. Client sends tool call → FastMCP
2. Middleware pipeline: error/retry → response_limit → caching → rate_limit → timeout → timing → request log
3. FastMCP resolves tool via FileSystemProvider
4. DI chain activates:
   controllers/dependencies/db.py
   → repos.py / services.py / audio.py / external.py / uow.py
   (all cached per-request, same session across all repos)
5. Tool function executes with injected services (ctx: Context = CurrentContext())
6. On success: session.commit() (in get_db_session finally)
7. On error: session.rollback() (in get_db_session except)
8. ToolResult → structuredContent (from Pydantic model) + content + meta
9. Response through middleware (timing recorded, logged, size-checked)
10. Back to client
```

## Startup Flow

```text
./start.sh
├── Backend: uv run uvicorn app.api.server:api --port 8000
│   ├── FastAPI lifespan: dedicated YM client + MCP mount readiness
│   └── MCP lifespan: bootstrap/lifespans.py composes DB + YM + analyzer + cache + audio
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
| Supabase PostgreSQL (only DB) | Production-grade, panel reads directly, RLS available; SQLite only for tests |
| CurrentContext() for DI | Unified context injection; session-scoped, no null checks needed |
| ToolTransform dict in transforms.py | Centralizes LLM-facing descriptions and hidden params without touching tool files |
| Pydantic response models | Auto-generates output_schema in FastMCP, helps LLMs parse tool results |

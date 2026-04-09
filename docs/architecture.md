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
    │  Supabase PostgreSQL          │
    │  SQLite (tests only, in-mem)  │
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
│ PostgreSQL    │  │ app/api/server.py            │
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
├── Backend: uv run uvicorn app.api.server:api --port 8000
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
| Supabase PostgreSQL (only DB) | Production-grade, panel reads directly, RLS available; SQLite only for tests |

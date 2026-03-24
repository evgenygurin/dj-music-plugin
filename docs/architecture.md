# Architecture

## Layer Diagram

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
│  │  │ 44 Tools │  │ 9 Resources│  │ 5 Workflow Prompts   │││
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
    │  SQLite (dev) / PostgreSQL    │
    │  44 tables, Alembic migrations│
    └──────────────────────────────┘

External:
    ┌──────────────────────────────┐
    │  Yandex Music API (httpx)    │
    │  Rate limited, OAuth token   │
    └──────────────────────────────┘
    ┌──────────────────────────────┐
    │  Audio Files (filesystem)    │
    │  librosa, demucs (optional)  │
    └──────────────────────────────┘
```

## Data Flow: Tool Call Lifecycle

```text
1. Client sends tool call → FastMCP
2. Middleware pipeline: log → timing → rate limit → response limit
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

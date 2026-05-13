# Architecture

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    MCP Clients (Claude, etc.)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio / streamable-http
┌──────────────────────────▼──────────────────────────────────┐
│                   FastMCP v3.x Server                        │
│  (root server.py — entrypoint;                              │
│   app/server/app.py — build_mcp_server composition)          │
│                                                              │
│  ┌─────────────┐ ┌────────────┐ ┌─────────────────────────┐ │
│  │ Middleware  │ │ Transforms │ │ Visibility (Namespaces) │ │
│  │ (log, time, │ │ (prompts→t,│ │ (crud:destructive,      │ │
│  │ rate limit, │ │ resources→t)│ │ provider:write, sync,   │ │
│  │ session,    │ │            │ │ admin — unlock per sess)│ │
│  │ error mask) │ │            │ │                         │ │
│  └──────┬──────┘ └────────────┘ └─────────────────────────┘ │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────────┐│
│  │           FileSystemProvider (auto-discover)             ││
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ ││
│  │  │ 20 Tools │  │27 Resources│  │ 6 Workflow Prompts   │ ││
│  │  └────┬─────┘  └──────┬─────┘  └──────────────────────┘ ││
│  └───────┼───────────────┼─────────────────────────────────┘│
└──────────┼───────────────┼──────────────────────────────────┘
           │               │
    ┌──────▼───────┐ ┌─────▼──────┐
    │ Depends()    │ │ Depends()  │
    │ get_uow,     │ │ get_uow,   │
    │ EntityReg,   │ │ caches     │
    │ ProviderReg  │ │            │
    └──────┬───────┘ └─────┬──────┘
           │               │
    ┌──────▼───────────────▼──────┐
    │     Handlers Layer           │
    │  track_import, track_features│
    │  _analyze / _reanalyze,      │
    │  audio_file_download,        │
    │  set_version_build,          │
    │  transition_persist          │
    │  (keyed by entity in         │
    │   EntityRegistry)            │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │   Repositories + UnitOfWork  │
    │  BaseRepository[M] generic:  │
    │  list/get/create/update/del  │
    │  + Django-style lookups      │
    │  (bpm__gte, mood__in)        │
    │  UoW flushes + commits once  │
    │  per tool call               │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │    SQLAlchemy 2.0 Async       │
    │  Supabase PostgreSQL          │
    │  SQLite (tests, in-mem)       │
    │  47 tables (17 drop-pending), │
    │  Alembic                      │
    └──────────────────────────────┘

Parallel layers (called from handlers, never from tools directly):
    ┌──────────────────────────────┐
    │  Providers (app/providers/)  │
    │  yandex/, future: spotify…   │
    │  Rate limited, OAuth token   │
    └──────────────────────────────┘
    ┌──────────────────────────────┐
    │  Audio pipeline (app/audio/) │
    │  Tiered L1-L4, 18 analyzers  │
    └──────────────────────────────┘
    ┌──────────────────────────────┐
    │  Domain (app/domain/)        │
    │  Pure compute — transition,  │
    │  optimization, camelot,      │
    │  template, audit             │
    └──────────────────────────────┘
```

## Bounded Contexts

| Context | Path | Responsibility |
|---|---|---|
| **Tools** | `app/tools/` | 14 `@tool` dispatchers (6 entity + 3 provider + 2 compute + 1 sync + `unlock_namespace` + `tool_invoke`) — no business logic, only dispatch |
| **UI Tools** | `app/tools/ui/` | 6 Prefab Apps renderers (`meta={"ui": True}`) — return `prefab_ui.components.Column` trees; JSON fallback via `ctx.client_supports_extension("io.modelcontextprotocol/ui")` |
| **Resources** | `app/resources/` | 27 `@resource` URIs — read-only views (16 local://, 4 schema://, 3 session://, 4 reference://) |
| **Prompts** | `app/prompts/` | 6 workflow recipes (LLM-visible) |
| **Handlers** | `app/handlers/` | Entity-specific side-effect logic (registered in EntityRegistry) |
| **Registry** | `app/registry/` | `EntityRegistry` (entity→repo+handler) + `ProviderRegistry` (name→client) |
| **Repositories** | `app/repositories/` | `BaseRepository[M]` + `UnitOfWork`. Flush-only, never commit |
| **Models** | `app/models/` | SQLAlchemy 2.0 ORM, one file per aggregate root |
| **Schemas** | `app/schemas/` | Pydantic DTOs — request/response/view |
| **Domain** | `app/domain/` | Pure compute (transition, optimization, camelot, template, audit) |
| **Audio** | `app/audio/` | Tiered pipeline + analyzers + mood classification |
| **Providers** | `app/providers/` | External platform clients (yandex/…) |
| **Server** | `app/server/` | FastMCP composition: lifespan, middleware, transforms, visibility, observability, DI |
| **Shared** | `app/shared/` | Errors, constants, filters, ids, pagination, time (leaf module) |
| **Config** | `app/config/` | Settings split by concern (audio, yandex, database, mcp, …) |

## Data Flow: Tool Call Lifecycle

```text
1. Client sends tool call → FastMCP
2. Middleware pipeline (app/server/middleware/):
   log → timing → rate limit → response limit → session → DomainErrorMiddleware
   (wraps tool + resource + prompt envelopes since v1.3.7 — translates
   NotFoundError / ValidationError / etc. into typed MCP error envelopes
   instead of leaking as "internal error: ...")
3. FastMCP resolves tool via FileSystemProvider (flat scan of app/tools/)
4. DI chain (app/server/di.py):
   Depends(get_uow) → UnitOfWork(AsyncSession) with repos attached
   Depends(get_entity_registry) / Depends(get_provider_registry)
5. Generic tool dispatches:
   - entity_create / entity_update → schema-validate payload → FK gate
     (app/tools/entity/_fk_gate.py:validate_fk_constraints, auto-derived
     from cls.__table__.foreign_keys) → handler if registered → repo persist
   - entity_list / entity_get / entity_aggregate → EntityRegistry lookup →
     BaseRepository[M] call (+ optional handler for side-effects)
   - provider_* → ProviderRegistry lookup → provider client
   - compute_* → app/domain/ pure function
   - playlist_sync → handler chain
6. On success: UoW.commit() in DI wrapper
7. On error: UoW.rollback(); raw pydantic ValidationError is wrapped into
   typed app.shared.errors.ValidationError("invalid payload for entity 'X': ...")
   for entity_create/update so mask_details=True production envelopes stay
   informative.
8. Return typed Pydantic model → structuredContent + content + meta
9. Response through middleware (timing recorded, logged)
10. Back to client
```

## Startup Flow

```text
uv run fastmcp run server.py
└── MCP lifespan (app/server/lifespan.py):
    composes DB + providers + audio pipeline + caches
```

**DB session setup (v1.3.7).** `app/db/session.py` registers a SQLAlchemy
`connect` event listener that issues `PRAGMA foreign_keys=ON` on every
aiosqlite connection. Erases the prod-on-Supabase-Postgres (FK enforced
by default) / dev-tests-on-SQLite (FK off by default) behaviour drift
that previously masked orphan-row bugs. Production (Postgres) is
unaffected.

**Handler ctx wrappers (v1.3.7).** Handlers (`app/handlers/*.py`) use
`safe_info(ctx, ...)` / `safe_report_progress(ctx, ...)` from
`app/handlers/_context_log.py` instead of calling `ctx.info()` /
`ctx.report_progress()` directly. The wrappers fall back to stdlib
logger when no active MCP session exists (headless scripts, unit
tests) — successful builds are no longer misreported as failures.

## EntityRegistry

```text
EntityRegistry
├── track           → TrackRepository + handlers(create=track_import)
├── track_features  → TrackFeaturesRepository
│                     + handlers(create=track_features_analyze,
│                                update=track_features_reanalyze)
├── audio_file      → AudioFileRepository
│                     + handlers(create=audio_file_download)
├── playlist        → PlaylistRepository
├── set             → SetRepository
├── set_version     → SetVersionRepository
│                     + handlers(create=set_version_build)
├── transition      → TransitionRepository
│                     + handlers(create=transition_persist)
├── transition_history, track_affinity, track_feedback,
│  scoring_profile → BaseRepository[M]
```

Note: `key` and `provider_metadata` have ORM models + repositories
under `app/repositories/` but are **not** registered in
`EntityRegistry` — they're internal references (Camelot wheel lookup,
provider response cache). Surface via `reference://camelot` /
`reference://providers` instead of `entity_*`.

`entity_list(entity="track", filter={...})` → `EntityRegistry.get("track").repo.list(filter)`.
`entity_create(entity="track", data={ym_id: 42})` → dispatches to `track_import` handler
(download metadata from YM, persist).

## ProviderRegistry

```text
ProviderRegistry
└── yandex → YandexMusicClient (see app/providers/yandex/)
```

`provider_read(provider="yandex", entity="track", id=42)` → `YandexMusicClient.get_track(42)`.

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| FastMCP v3 canonical layout (`tools/`, `resources/`, `prompts/`) | Matches upstream; FileSystemProvider auto-discovery; zero registration boilerplate |
| 20 tool dispatchers (14 core + 6 UI) | 88-tool catalog collapsed via polymorphism (EntityRegistry, ProviderRegistry, handlers) |
| Handlers over services | Side-effects live at the tool layer, colocated with the entity they mutate |
| BaseRepository[M] + Django lookups | Generic CRUD + filter DSL (`bpm__gte`, `mood__in`) without bespoke methods per entity |
| Unit of Work | Explicit transaction boundary; middleware commits/rollbacks; repos only flush |
| Pydantic v2 for tool returns | Structured content, self-documenting, type-safe |
| Domain pure | No IO in `app/domain/` — testable, composable, fast |
| Tool Search (BM25) + Namespace Activation | ~10 tools always visible; others discoverable per session — context stays lean |
| Supabase PostgreSQL (prod) + SQLite (tests) | Production-grade + RLS-capable; tests stay fast without external DB |

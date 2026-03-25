# Architecture

## Overview

DJ Music Plugin follows a strict layered architecture where each layer imports only the layer below. The MCP server is built on FastMCP v3.1 with FileSystemProvider for zero-boilerplate tool auto-discovery.

```mermaid
graph TB
    subgraph "MCP Clients"
        C1[Claude Code]
        C2[Other MCP Clients]
    end

    subgraph "FastMCP v3.1 Server"
        MW[Middleware Pipeline]
        TR[Transforms]
        VIS[Visibility System]
        FSP[FileSystemProvider]

        subgraph "MCP Layer"
            T[50 Tools]
            R[9 Resources]
            P[6 Workflow Prompts]
        end
    end

    subgraph "Service Layer"
        TS[TrackService]
        PS[PlaylistService]
        SS[SetService]
        SC[TransitionScorer]
        OP[GA/Greedy Optimizer]
        MC[MoodClassifier]
        EX[Exporter]
    end

    subgraph "Repository Layer"
        TR2[TrackRepo]
        PR[PlaylistRepo]
        SR[SetRepo]
        FR[FeatureRepo]
    end

    subgraph "Data Layer"
        DB[(SQLAlchemy 2.0<br/>44 tables)]
        YM[Yandex Music API<br/>httpx async]
        AF[Audio Files<br/>librosa / numpy]
    end

    C1 & C2 -->|stdio / streamable-http| MW
    MW --> TR --> VIS --> FSP
    FSP --> T & R & P
    T & R -->|Depends DI| TS & PS & SS & SC & OP & MC & EX
    TS & PS & SS & SC & OP & MC & EX --> TR2 & PR & SR & FR
    TR2 & PR & SR & FR -->|flush only| DB
    TS --> YM
    MC & SC --> AF
```

## Layer Rules

| Layer | Directory | Imports | Responsibility |
|-------|-----------|---------|---------------|
| **Models** | `app/models/` | SQLAlchemy only | Data structure definitions (44 tables) |
| **Repositories** | `app/repositories/` | Models | Data access. **Flush only, never commit** |
| **Services** | `app/services/` | Repositories, Models | Business logic. Domain errors, no MCP imports |
| **MCP Tools** | `app/mcp/tools/` | Services (via DI) | Thin MCP wrappers with `@tool` decorator |
| **MCP Resources** | `app/mcp/resources/` | Services (via DI) | Read-only data views with `@resource` decorator |
| **MCP Prompts** | `app/mcp/prompts/` | None (pure templates) | Workflow prompt templates |
| **Audio** | `app/audio/` | Models | Audio analysis (optional deps) |
| **YM Client** | `app/ym/` | None | Async Yandex Music HTTP client |
| **Core** | `app/core/` | None | Shared: errors, constants, pagination, entity resolver |

> **Rule:** Each layer imports only the layer below. Tools -> Services -> Repositories -> Models.

## Data Flow: Tool Call Lifecycle

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant MW as Middleware
    participant FSP as FileSystemProvider
    participant DI as DI Chain
    participant Tool as Tool Function
    participant Svc as Service
    participant Repo as Repository
    participant DB as Database

    Client->>MW: Tool call request
    MW->>MW: Log -> Timing -> Rate Limit
    MW->>FSP: Resolve tool
    FSP->>DI: Activate DI chain
    DI->>DI: get_db_session() -> get_*_repo() -> get_*_service()
    Note over DI: All repos share same session
    DI->>Tool: Inject services
    Tool->>Svc: Business logic
    Svc->>Repo: Data access
    Repo->>DB: SQL (flush only)
    DB-->>Repo: Results
    Repo-->>Svc: Domain objects
    Svc-->>Tool: Pydantic models
    Tool-->>MW: ToolResult (structuredContent)

    alt Success
        DI->>DB: session.commit()
    else Error
        DI->>DB: session.rollback()
    end

    MW-->>Client: Response (timing recorded)
```

## Dependency Injection

All services and repositories are injected via FastMCP's `Depends()` system. A single DB session is shared across all services within one tool call.

```python
from fastmcp.tools import tool
from fastmcp.dependencies import Depends

@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def my_tool(
    id: int,
    view: Literal["summary", "full"] = "summary",
    svc=Depends(get_my_service),       # param=Depends() pattern
) -> MyModel:
    """Short description."""
    return await svc.get(id, view=view)
```

### DI Chain

```mermaid
graph LR
    A[get_db_session] --> B[get_track_repo]
    A --> C[get_feature_repo]
    A --> D[get_playlist_repo]
    B --> E[get_track_service]
    C --> E
    D --> F[get_playlist_service]

    style A fill:#f9f,stroke:#333
    style E fill:#bbf,stroke:#333
    style F fill:#bbf,stroke:#333
```

> **Important:** Use `param=Depends(factory)`, NOT `Annotated[Type, Depends(factory)]` -- FastMCP does not resolve the Annotated pattern.

### Transaction Boundary

- **Repositories:** `await self.session.flush()` (never commit)
- **DI wrapper** `get_db_session()`: commit on success, rollback on failure
- This ensures one transaction per tool call across all repos

## Middleware Pipeline

```mermaid
graph LR
    A[Request] --> B[StructuredLogging]
    B --> C[DetailedTiming]
    C --> D[YMRateLimit]
    D --> E[RetryMiddleware]
    E --> F[Tool Execution]
    F --> E --> D --> C --> B --> G[Response]
```

| Middleware | Purpose |
|-----------|---------|
| `StructuredLoggingMiddleware` | Logs tool calls with optional payload logging |
| `DetailedTimingMiddleware` | Records execution time per tool |
| `YMRateLimitMiddleware` | Enforces rate limiting for YM API calls |
| `RetryMiddleware` | Retries failed tool calls (max 2 retries) |

## Transforms

```python
mcp.add_transform(ResourcesAsTools(mcp))  # Resources exposed as tools
mcp.add_transform(PromptsAsTools(mcp))    # Prompts exposed as tools
```

This enables tool-only clients (like Claude Code) to access resources and prompts as regular tool calls.

## Visibility System

Tools are organized into three visibility tiers to reduce token overhead (~5K vs ~9K context):

```mermaid
graph TD
    subgraph "Always Visible (23 tools)"
        A[CRUD: tracks, playlists, sets]
        B[Search & Filter]
        C[Set Building & Reasoning]
        D[Admin]
    end

    subgraph "Extended (20 tools, unlock per category)"
        E[Delivery & Export]
        F[Discovery & Download]
        G[Curation]
        H[Sync]
        I[YM API]
    end

    subgraph "Hidden (7 tools, explicit unlock)"
        J[Audio Analysis]
        K[Atomic Tools]
    end

    D -->|unlock_tools| E & F & G & H & I
    D -->|unlock_tools| J & K
```

Usage:
```python
unlock_tools(action="unlock", category="discovery")  # Unlock discovery tools
unlock_tools(action="status")                         # Check what's unlocked
unlock_tools(action="lock", category="audio")         # Re-hide audio tools
```

## Server Lifespans

Four lifespans manage resource lifecycles:

| Lifespan | Provides | Cleanup |
|----------|----------|---------|
| `db_lifespan` | DB engine + session factory | `engine.dispose()` |
| `ym_lifespan` | YM client + rate limiter | `client.close()` |
| `analyzer_lifespan` | Audio analyzer registry | -- |
| `cache_lifespan` | Transition score cache | `cache.clear()` |

```python
mcp = FastMCP(
    lifespan=db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan,
    ...
)
```

## FileSystemProvider

Auto-discovers `@tool`, `@resource`, and `@prompt` decorated functions from all Python files in `app/mcp/`:

```
app/mcp/
├── tools/          # 17 files, 50 tools
│   ├── tracks.py   # list_tracks, get_track, manage_tracks, get_track_features
│   ├── playlists.py
│   ├── crud.py     # sets CRUD
│   ├── search.py
│   ├── sets.py     # build_set, rebuild_set, score_transitions
│   ├── reasoning.py
│   ├── admin.py
│   ├── delivery.py
│   ├── discovery.py
│   ├── import_download.py
│   ├── curation.py
│   ├── sync.py
│   ├── ym.py
│   ├── audio.py
│   └── audio_atomic.py
├── resources/      # 3 files, 9 resources
│   ├── status.py
│   ├── templates.py
│   └── reference.py
└── prompts/        # 1 file, 6 prompts
    └── workflows.py
```

No manual imports needed -- new tools are discovered automatically.

## Error Hierarchy

```mermaid
graph TD
    A[DJMusicError] --> B[NotFoundError]
    A --> C[ValidationError]
    A --> D[ConflictError]
    A --> E[PipelineError]
    A --> F[YandexMusicError]
    A --> G[ExportError]

    E --> H[AnalyzerUnavailableError]
    E --> I[AnalysisTimeoutError]

    F --> J[RateLimitedError]
    F --> K[AuthFailedError]
    F --> L[APIError]
```

- **Services** raise domain errors (`NotFoundError`, `ValidationError`)
- **Tools** raise `ToolError` for input validation
- Production mode masks error details: `mask_error_details=not settings.debug`

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| FileSystemProvider over manual registration | Zero boilerplate, hot reload in dev |
| `Depends()` for DI over global state | Per-request session scoping, testable |
| Services != Tools | Services are framework-agnostic, reusable outside MCP |
| Repos flush, never commit | Transaction boundary at tool level via DI |
| Pydantic models for tool returns | Automatic `structuredContent`, type-safe |
| Settings class over raw env vars | Type-checked, documented defaults, testable |
| Visibility tiers | ~5K tokens in context vs ~9K, better Claude accuracy |
| `TrackFeatures.from_db()` classmethod | Single source of truth for DB->dataclass mapping |
| `FeatureRepository` batch methods | N SQL queries -> 1 for scoring loops |

## Related Pages

- **[MCP Tools Reference](MCP-Tools-Reference)** -- All 50 tools
- **[Configuration Reference](Configuration-Reference)** -- All settings
- **[Contributing](Contributing)** -- Code patterns and conventions

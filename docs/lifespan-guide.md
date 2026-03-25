# Lifespan Management Guide

FastMCP v3.1 server with composable lifespans for managing server-level resources.

## Overview

The DJ Music Plugin uses **4 composable lifespans** that handle server startup/shutdown:

1. **`db_lifespan`** — SQLAlchemy async engine + session factory
2. **`ym_lifespan`** — Yandex Music HTTP client with rate limiting
3. **`analyzer_lifespan`** — Audio analyzer plugin registry
4. **`cache_lifespan`** — In-memory LRU cache for transition scores

Lifespans are composed using the `|` operator and execute in LIFO order:
- **Enter**: left-to-right (db → ym → analyzer → cache)
- **Exit**: right-to-left (cache → analyzer → ym → db)

## Architecture

```python
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

# Each lifespan yields a dict that becomes part of lifespan_context
@lifespan
async def db_lifespan(server):
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)
    try:
        yield {"db_engine": engine, "db_session_factory": session_factory}
    finally:
        await engine.dispose()

# Compose with | operator
mcp = FastMCP(
    "DJ Music",
    lifespan=db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan,
)
```

## Accessing Lifespan Context

### In Tools

Use dependency injection via `Depends()`:

```python
from fastmcp import tool
from fastmcp.server.dependencies import Depends
from app.mcp.dependencies import get_ym_client, get_transition_cache

@tool
async def my_tool(
    ym_client=Depends(get_ym_client),
    cache=Depends(get_transition_cache),
):
    """Tool with injected lifespan dependencies."""
    tracks = await ym_client.search("techno")
    score = cache.get(1, 2)
    return {"tracks": len(tracks), "cached": score is not None}
```

### Manually via Context

```python
from fastmcp import Context
from fastmcp.server.dependencies import CurrentContext

@tool
def manual_access(ctx: Context = CurrentContext()):
    """Direct access to lifespan context."""
    db_engine = ctx.lifespan_context["db_engine"]
    ym_client = ctx.lifespan_context["ym_client"]
    registry = ctx.lifespan_context["analyzer_registry"]
    cache = ctx.lifespan_context["transition_cache"]
```

## Available Dependency Factories

Located in `app/mcp/dependencies.py`:

| Factory | Returns | Lifespan Context Key |
|---------|---------|---------------------|
| `get_db_session()` | `AsyncSession` | `db_session_factory` (via async context manager) |
| `get_ym_client()` | `YandexMusicClient` | `ym_client` |
| `get_analyzer_registry()` | `AnalyzerRegistry` | `analyzer_registry` |
| `get_transition_cache()` | `TransitionCache` | `transition_cache` |

## Lifespan Details

### 1. Database Lifespan

**Purpose**: Creates SQLAlchemy async engine + session factory

**Lifecycle**:
- **Startup**: Create engine with pool_pre_ping for connection health checks
- **Shutdown**: Dispose engine and close all connections

**Context**:
```python
{
    "db_engine": AsyncEngine,
    "db_session_factory": async_sessionmaker
}
```

**Usage**:
```python
# Via get_db_session() — auto-commit/rollback wrapper
async with get_db_session() as session:
    result = await session.execute(select(Track))
    await session.commit()  # auto-committed if no exception
```

### 2. Yandex Music Lifespan

**Purpose**: Creates YM HTTP client with rate limiting

**Lifecycle**:
- **Startup**: Initialize httpx.AsyncClient with OAuth token + RateLimiter
- **Shutdown**: Close HTTP client gracefully

**Context**:
```python
{
    "ym_client": YandexMusicClient
}
```

**Rate Limiting**:
- Token bucket: 1 request per `settings.ym_rate_limit_delay` (default 1.5s)
- Exponential backoff on HTTP 429
- Max `settings.ym_retry_attempts` retries (default 3)

**Usage**:
```python
ym_client = Depends(get_ym_client)
tracks = await ym_client.search("techno", type="tracks", limit=10)
```

### 3. Analyzer Registry Lifespan

**Purpose**: Discover and register audio analyzers

**Lifecycle**:
- **Startup**: Call `registry.discover()` to auto-register built-in analyzers
- **Shutdown**: No cleanup (stateless)

**Context**:
```python
{
    "analyzer_registry": AnalyzerRegistry
}
```

**Available Analyzers**:
- **Core** (always available): loudness, energy, spectral
- **Optional** (requires `[audio]` extra): bpm, key, mfcc, beat

**Usage**:
```python
registry = Depends(get_analyzer_registry)
available = registry.list_available()
analyzer = registry.get("loudness")
```

### 4. Cache Lifespan

**Purpose**: In-memory LRU cache for transition scores

**Lifecycle**:
- **Startup**: Create `TransitionCache` with configured size/TTL
- **Shutdown**: Clear all cached entries

**Context**:
```python
{
    "transition_cache": TransitionCache
}
```

**Configuration**:
- `settings.transition_cache_max_size` (default 10,000 pairs)
- `settings.transition_cache_ttl` (default 3600 seconds)

**Usage**:
```python
cache = Depends(get_transition_cache)

# Store
cache.put(1, 2, bpm_score=0.9, harmonic_score=0.8, ..., overall_score=0.8)

# Retrieve
score = cache.get(1, 2)  # Returns TransitionScore | None

# Invalidate when features change
cache.invalidate_track(1)  # Removes all transitions involving track 1
```

## Testing Lifespans

See `tests/test_cache.py` for unit tests of `TransitionCache`.

For integration testing with lifespans:

```python
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

@lifespan
async def test_lifespan(server):
    # Setup
    resource = await initialize_test_resource()
    try:
        yield {"test_resource": resource}
    finally:
        # Cleanup
        await resource.cleanup()

mcp = FastMCP("test", lifespan=test_lifespan)

async with mcp.lifespan_context(mcp):
    # Lifespan is active, context available
    assert mcp._lifespan_context["test_resource"] is not None
```

## Best Practices

1. **Always use try/finally** in lifespans for guaranteed cleanup
2. **Keep lifespans focused** — one resource type per lifespan
3. **Use dependency injection** — prefer `Depends()` over direct context access
4. **Composition order matters** — dependencies should be entered first
5. **Test cleanup** — ensure `finally` blocks execute even on cancellation

## Troubleshooting

### Import Hangs

If `from app.server import mcp` hangs:
- Check for circular imports in tool modules
- Ensure optional dependencies (librosa, etc.) don't block at import time
- Use lazy imports for heavy modules

### Context Not Available

If `ctx.lifespan_context` raises KeyError:
- Ensure lifespan is passed to `FastMCP(..., lifespan=...)`
- Verify tool is called within lifespan scope (not at module import)
- Check lifespan composition order

### Cache Not Working

If cache misses unexpectedly:
- Check TTL — entries may have expired
- Verify key normalization — `(1,2)` and `(2,1)` are the same
- Inspect stats: `cache.stats()` shows size, TTL, oldest age

## Configuration

All lifespan settings in `app/config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `database_url` | `sqlite+aiosqlite:///dj_music.db` | DB connection |
| `ym_token` | `""` | YM OAuth token |
| `ym_rate_limit_delay` | `1.5` | Seconds between YM calls |
| `transition_cache_max_size` | `10000` | Max cached pairs |
| `transition_cache_ttl` | `3600` | Cache TTL in seconds |

Override via environment variables with `DJ_` prefix:

```bash
export DJ_DATABASE_URL="postgresql+asyncpg://..."
export DJ_YM_TOKEN="your_token_here"
export DJ_TRANSITION_CACHE_MAX_SIZE=50000
```

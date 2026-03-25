# Dependency Injection Patterns

Aligned with [FastMCP Dependency Injection](https://gofastmcp.com/servers/dependency-injection.md) best practices.

## Overview

FastMCP uses dependency injection powered by [Docket](https://github.com/chrisguidry/docket) to provide runtime values to tools, resources, and prompts. Dependencies are declared as parameter defaults and resolved automatically.

**Key principle**: Dependency parameters are **automatically excluded** from the MCP schema. Clients never see them.

## Core Pattern

```python
from typing import Annotated
from fastmcp.dependencies import Depends
from app.mcp.dependencies import get_track_repo
from app.repositories.track import TrackRepository

@mcp.tool()
async def my_tool(
    query: str,  # ← visible to client
    repo: Annotated[TrackRepository, Depends(get_track_repo)] = None,  # type: ignore
    ctx: Context | None = None,  # ← auto-injected
) -> dict:
    # repo is already connected to a session
    # session is committed automatically on success
    results = await repo.search_by_text(query)
    return {"results": results}
```

## Database Session Lifecycle

### 1. Session Creation

```python
@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Single transaction per tool call."""
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        try:
            yield session
            await session.commit()  # ✅ Auto-commit on success
        except Exception:
            await session.rollback()  # ✅ Auto-rollback on error
            raise
```

### 2. Repository Factories

```python
def get_track_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackRepository:
    return TrackRepository(session)

def get_playlist_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlaylistRepository:
    return PlaylistRepository(session)
```

**Key insight**: Multiple repos depending on `get_db_session` receive the **SAME session** (per-request caching).

### 3. Tool Usage

```python
@mcp.tool()
async def complex_tool(
    track_repo: Annotated[TrackRepository, Depends(get_track_repo)],
    playlist_repo: Annotated[PlaylistRepository, Depends(get_playlist_repo)],
) -> dict:
    # Both repos share the SAME session
    assert track_repo.session is playlist_repo.session
    
    # All operations are in ONE transaction
    track = await track_repo.create(Track(...))
    await playlist_repo.add_track(playlist_id, track.id)
    
    # ✅ No commit here — happens automatically in get_db_session
    return {"track_id": track.id}
```

## Built-in Dependencies

| Dependency | Type | Usage |
|-----------|------|-------|
| `Context` (type annotation) | MCP context | `ctx: Context` |
| `CurrentContext()` | MCP context | `ctx: Context = CurrentContext()` |
| `CurrentFastMCP()` | Server instance | `server: FastMCP = CurrentFastMCP()` |
| `CurrentRequest()` | HTTP request (SSE/HTTP only) | `request: Request = CurrentRequest()` |
| `CurrentHeaders()` | HTTP headers (graceful fallback) | `headers: dict = CurrentHeaders()` |
| `CurrentAccessToken()` | OAuth token | `token: AccessToken = CurrentAccessToken()` |
| `TokenClaim("sub")` | Single token claim | `user_id: str = TokenClaim("sub")` |

## Custom Dependencies

### Synchronous Dependency

```python
def get_config() -> dict:
    return {"api_url": "https://api.example.com"}

@mcp.tool()
async def my_tool(
    config: dict = Depends(get_config),
) -> str:
    return config["api_url"]
```

### Async Dependency

```python
async def get_user_id() -> int:
    # Could fetch from DB, external service, etc.
    return 42

@mcp.tool()
async def my_tool(
    user_id: int = Depends(get_user_id),
) -> str:
    return f"User {user_id}"
```

### Resource Management (Async Context Manager)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_http_client():
    client = httpx.AsyncClient()
    try:
        yield client
    finally:
        await client.aclose()

@mcp.tool()
async def fetch_data(
    url: str,
    client = Depends(get_http_client),
) -> dict:
    response = await client.get(url)
    return response.json()
```

### Nested Dependencies

```python
def get_base_url() -> str:
    return "https://api.example.com"

def get_api_client(base_url: str = Depends(get_base_url)) -> dict:
    return {"base_url": base_url, "version": "v1"}

@mcp.tool()
async def call_api(
    endpoint: str,
    client: dict = Depends(get_api_client),
) -> str:
    return f"{client['base_url']}/{client['version']}/{endpoint}"
```

## Per-Request Caching

Dependencies are **cached per request**. If multiple parameters use the same dependency, it's resolved **once** and reused.

```python
def expensive_computation() -> dict:
    print("Computing...")  # Only printed ONCE per request
    return {"result": 42}

@mcp.tool()
async def my_tool(
    data1: dict = Depends(expensive_computation),
    data2: dict = Depends(expensive_computation),  # Same instance as data1
) -> bool:
    return data1 is data2  # True!
```

## Transaction Boundaries

| Layer | Responsibility | Pattern |
|-------|---------------|---------|
| **Tools** | Call services, handle MCP concerns | Use `Depends()` for repos |
| **Services** | Business logic, orchestration | Receive repos via `__init__` |
| **Repositories** | Data access | `flush()` only, **never** `commit()` |
| **DI (get_db_session)** | Transaction boundary | `commit()` on success, `rollback()` on error |

### ✅ Correct Pattern

```python
# Tool
@mcp.tool()
async def create_track(
    title: str,
    repo: Annotated[TrackRepository, Depends(get_track_repo)],
) -> dict:
    track = Track(title=title, status=0)
    track = await repo.create(track)
    # ✅ No commit — happens in get_db_session
    return {"id": track.id}

# Repository
class TrackRepository:
    async def create(self, track: Track) -> Track:
        self.session.add(track)
        await self.session.flush()  # ✅ Only flush
        return track
```

### ❌ Wrong Patterns

```python
# ❌ Wrong: Manual session management
@mcp.tool()
async def create_track_wrong(
    title: str,
    ctx: Context,
) -> dict:
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:  # ❌ Manual session
        repo = TrackRepository(session)
        track = await repo.create(Track(title=title))
        await session.commit()  # ❌ Commit in tool
        return {"id": track.id}

# ❌ Wrong: Commit in repository
class TrackRepository:
    async def create(self, track: Track) -> Track:
        self.session.add(track)
        await self.session.commit()  # ❌ NEVER commit in repo
        return track
```

## Testing DI

### Unit Test with Mocked Session

```python
@pytest.mark.asyncio
async def test_repo_operation(seeded_db):
    session = seeded_db["session"]
    repo = TrackRepository(session)
    
    track = Track(title="Test", status=0)
    result = await repo.create(track)
    
    assert result.id is not None
```

### Integration Test with MCP Client

```python
@pytest.mark.asyncio
async def test_tool_with_di(mcp_client):
    result = await mcp_client.call_tool(
        "create_track",
        arguments={"title": "Test Track"}
    )
    
    assert result["id"] is not None
    # Session was committed automatically
```

## Migration Checklist

Migrating tools from old pattern (`async with _get_session(ctx)`) to Depends():

- [ ] Add `from typing import Annotated`
- [ ] Add `from fastmcp.dependencies import Depends`
- [ ] Add `from app.mcp.dependencies import get_*_repo`
- [ ] Remove `_get_session(ctx)` helper
- [ ] Replace `async with await _get_session(ctx) as session:` with repo parameters
- [ ] Remove `await session.commit()` calls (handled by DI)
- [ ] Add `repo: Annotated[XRepository, Depends(get_x_repo)] = None` parameters
- [ ] Remove manual `Repository(session)` instantiation

## References

- [FastMCP DI Documentation](https://gofastmcp.com/servers/dependency-injection.md)
- [Docket Dependency System](https://chrisguidry.github.io/docket/dependencies/)
- Design Spec §3: DI Chain
- `.claude/rules/repositories.md`: Flush-only rule

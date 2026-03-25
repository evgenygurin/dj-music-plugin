---
description: MCP tool implementation patterns (FastMCP v3)
globs: app/mcp/tools/**/*.py
---

# MCP Tools

## Decorator & Metadata

- Use standalone `@tool` decorator from `fastmcp` (FileSystemProvider auto-discovers)
- **Every tool must have**: `tags={"category"}` and `annotations={"readOnlyHint": ...}`
- Tool descriptions ≤50 words — details go in parameter descriptions
- Timeouts: set `timeout=N` on heavy tools (build_set, analyze_*, deliver_set)

## Dependency Injection (FastMCP v3 Pattern)

**✅ CORRECT pattern:**

```python
from typing import Annotated
from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from app.mcp.dependencies import get_track_repo
from app.repositories.track import TrackRepository

@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def my_tool(
    query: str,  # ← visible to client
    repo: Annotated[TrackRepository, Depends(get_track_repo)] = None,  # type: ignore
    ctx: Context | None = None,  # ← auto-injected
) -> dict:
    # repo is already connected to a session
    results = await repo.search_by_text(query)
    # ✅ NO commit here — handled by get_db_session
    return {"results": results}
```

**Key rules:**
- Use `Annotated[Repo, Depends(get_repo)]` — dependencies hidden from MCP schema
- Multiple repos in same tool → same session (per-request caching)
- **NEVER** call `session.commit()` or `session.rollback()` in tools
- Transaction boundary is `get_db_session` context manager
- Context (`ctx: Context`) is optional, for logging/progress only

**❌ WRONG patterns:**

```python
# ❌ Manual session management
async with await _get_session(ctx) as session:
    repo = TrackRepository(session)
    await session.commit()  # ❌ NO!

# ❌ Direct repository instantiation
repo = TrackRepository(session)  # ❌ Use Depends() instead
```

## Other Patterns

- Use `CurrentContext()` for MCP context (logging, progress, elicitation)
- Return Pydantic models for `structuredContent` (not dicts)
- Use `view: Literal["summary", "full"]` pattern for progressive disclosure
- Entity resolution: use explicit `id: int | None, query: str | None` — not `ref: str`
- Elicitation: always use `safe_elicit()` wrapper with fallback
- Progress: `ctx.report_progress(current, total)` for long operations

## References

- [FastMCP DI docs](https://gofastmcp.com/servers/dependency-injection.md)
- `docs/di-patterns.md` — full DI guide
- `app/mcp/tools/crud_example.py` — reference implementation

---
description: MCP tool implementation patterns (FastMCP v3)
globs: app/mcp/tools/**/*.py
---

# MCP Tools

- Use standalone `@tool` decorator from `fastmcp` (FileSystemProvider auto-discovers)
- **Every tool must have**: `tags={"category"}` and `annotations={"readOnlyHint": ...}`
- Tool descriptions ≤50 words — details go in parameter descriptions
- Use `Depends()` for DI — hidden from tool schema automatically
- **Context access**: ALWAYS use `ctx: Context = CurrentContext()` (preferred pattern)
  - Import: `from fastmcp.dependencies import CurrentContext`
  - Never use legacy type-hint injection (`ctx: Context | None = None`)
  - Context methods are async: `await ctx.info()`, `await ctx.report_progress()`
- **Helper functions**: use `get_context()` to access context without parameters
  - Import: `from fastmcp.server.dependencies import get_context`
  - Example: `ctx = get_context()` inside `_get_session()`
- Return Pydantic models for `structuredContent` (not dicts)
- Use `view: Literal["summary", "full"]` pattern for progressive disclosure
- Entity resolution: use explicit `id: int | None, query: str | None` — not `ref: str`
- **Logging & Progress**:
  - `await ctx.info("message")` / `await ctx.warning()` / `await ctx.error()`
  - `await ctx.report_progress(current, total)` for long operations
- **Visibility**: `await ctx.enable_components(tags=...)` / `await ctx.disable_components()`
- Timeouts: set `timeout=N` on heavy tools (build_set, analyze_*, deliver_set)
- Never import repositories directly — use services via Depends
- Never call `session.commit()` — DI handles transaction lifecycle

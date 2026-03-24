---
description: MCP tool implementation patterns (FastMCP v3)
globs: app/mcp/tools/**/*.py
---

# MCP Tools

- Use standalone `@tool` decorator from `fastmcp` (FileSystemProvider auto-discovers)
- **Every tool must have**: `tags={"category"}` and `annotations={"readOnlyHint": ...}`
- Tool descriptions ≤50 words — details go in parameter descriptions
- Use `Depends()` for DI — hidden from tool schema automatically
- Use `CurrentContext()` for MCP context (logging, progress, elicitation)
- Return Pydantic models for `structuredContent` (not dicts)
- Use `view: Literal["summary", "full"]` pattern for progressive disclosure
- Entity resolution: use explicit `id: int | None, query: str | None` — not `ref: str`
- Elicitation: always use `safe_elicit()` wrapper with fallback
- Progress: `ctx.report_progress(current, total)` for long operations
- Timeouts: set `timeout=N` on heavy tools (build_set, analyze_*, deliver_set)
- Never import repositories directly — use services via Depends
- Never call `session.commit()` — DI handles transaction lifecycle

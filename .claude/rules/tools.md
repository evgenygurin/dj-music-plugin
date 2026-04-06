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

## Gotchas

- `Depends()`: use `param=Depends(factory)`, NOT `Annotated[Type, Depends(factory)]` — FastMCP doesn't resolve Annotated
- `list_page_size` in config must be >= tool count (100) — Claude Code doesn't follow nextCursor
- Hidden tools: after `unlock_tools`, Claude Code doesn't reload tool list — hidden tools (audio, atomic) only accessible via script `Client(mcp)`
- `download_tracks` refs: accepts YM track IDs (`"135055088"`) or local IDs (auto-resolves via `resolve_local_ids_to_ym`). Numbers < 100000 = local, >= 100000 = YM
- `download_tracks` automatically creates `DjLibraryItem` via `_link_file_to_track()` — no manual linking needed
- `score_delivery_transitions` returns `tuple[int, int]` (scored, conflicts), NOT dict
- `build_set` without features: fallback to `playlist_order` (not greedy/ga) — correct behavior
- `get_set` tracks view: includes `artist_names` via batch query (`get_by_ids` batch, not N+1)
- `TransitionIntent`: context-aware enum (maintain/ramp_up/cool_down/contrast) affects GA optimizer weights by track position
- `score_timbral`: 6th component of TransitionScorer (weight 0.10), total weights = 1.0 (bpm 0.22 + harmonic 0.20 + energy 0.23 + spectral 0.15 + groove 0.10 + timbral 0.10)

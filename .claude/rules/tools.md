---
description: MCP tool implementation patterns (FastMCP v3)
globs: app/controllers/tools/**/*.py
---

# MCP Tools

- Use standalone `@tool` decorator from `fastmcp` (FileSystemProvider auto-discovers, scans subpackages recursively)
- **Tag and annotation constants**: import from `app.controllers.tools._shared` — never hardcode literals
  - `tags={ToolCategory.CORE.value}` (StrEnum, no magic strings)
  - `annotations=ANNOTATIONS_READ_ONLY` / `ANNOTATIONS_WRITE` / `ANNOTATIONS_WRITE_IDEMPOTENT` / `ANNOTATIONS_WRITE_DESTRUCTIVE` / `ANNOTATIONS_WRITE_OPEN_WORLD` / `ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN` / `ANNOTATIONS_READ_ONLY_OPEN_WORLD`
  - `idempotentHint=True` — classify_mood, analyze_track, score_transitions (safe to retry)
  - `destructiveHint=True` — ban_track, distribute_to_subgenres(clean)
  - `openWorldHint=True` — import_tracks, download_tracks, platform_*, sync_playlist
  - `timeout=ToolTimeout.MEDIUM | HEAVY | BATCH`
- **Title**: `title="Human Readable Name"` — REQUIRED on every tool (Claude Code displays it in UI)
- **Icons**: `icons=ICON_TRACKS` / `ICON_SETS` / `ICON_YM` / etc — 16 SVG icon sets in `_shared.taxonomy`
- **Meta**: `meta=TOOL_META` on every tool — auto-generated from `app._version.__version__`
- **Visibility**: default visibility configured in `bootstrap/visibility.py`. Per-session changes via `ctx.enable_components(tags={...})` / `ctx.disable_components(tags={...})` — NOT `ctx.fastmcp.enable()`
- **Entity resolution**: use `resolve_track_id` / `resolve_entity` / `ensure_reference` from `_shared` — never re-implement `id|query` validation
- **Context injection**: `ctx: Context = CurrentContext()  # noqa: B008` — import `Context` from `fastmcp.server.context`, `CurrentContext` from `fastmcp.dependencies`. NEVER use `Annotated[Context | None, Field(...)] = None`
  - Shorthand also valid: `ctx: Context` (no default) — FastMCP injects via type hint automatically
  - In helper functions that don't receive ctx as param: `ctx = get_context()` from `fastmcp.server.dependencies`
- **Context properties**: `ctx.transport` (stdio/sse/streamable-http), `ctx.session_id`, `ctx.client_id`, `ctx.request_id` — useful for observability and per-transport behaviour
- **Context logging**: wrap `ctx` in `ToolContext(ctx)` and call `await log.info(...)`, `log.progress(...)`, `log.elicit(...)` — never write `if ctx: await ctx.info(...)` guards
- **Progress reporting**: `await ctx.report_progress(progress=i, total=n)` for long-running loops. Both `progress` and `total` can be any unit (items, percentage, bytes). `total` is optional (indeterminate). No-op if client sent no progress token — safe to call always.
- **Sampling** (`ctx.sample()`): server-initiated LLM call. Requires `DJ_ANTHROPIC_API_KEY` (fallback mode) or client support. Tools that reason over library data use `search_queries: list[str]` parameter instead — the LLM client generates queries and passes them as tool input.
- **Action-dispatched tools** (`platform_playlists`, `platform_liked_tracks`, `manage_*`): use `ActionDispatcher[ResultT]` from `_shared.dispatch` — `@_dispatcher.register("name")` instead of `if/elif` chains. Duplicate registration raises at import time.
- Tool descriptions ≤50 words — details go in parameter descriptions
- Use `Depends()` for DI — hidden from tool schema automatically
- Return Pydantic models for `structuredContent` (not dicts) where the service supports it
- Use `view: Literal["summary", "full"]` pattern for progressive disclosure
- Never import repositories directly — use services via `Depends`
- Never call `session.commit()` — DI handles transaction lifecycle
- **No lazy imports inside function bodies** — hoist to module top. Lazy import = code smell.
- Platform tools live in `app/controllers/tools/platform/` (one file per entity), not in a flat `platform.py`

## Gotchas

- `Depends()`: use `param=Depends(factory)`, NOT `Annotated[Type, Depends(factory)]` — FastMCP doesn't resolve Annotated
- `pagination_size` in config must be >= tool count — MCP clients may not follow nextCursor
- Hidden tools: all 7 extended/hidden categories (delivery, discovery, curation, sync, ym, audio, atomic) are disabled at startup. `unlock_tools(action="unlock", category="...")` calls `ctx.enable_components(tags={category})` — per-session, triggers `notifications/tools/list_changed` so the client re-fetches automatically
- `ctx.enable_components()` / `ctx.disable_components()` filter criteria: `names`, `keys` (e.g. `"tool:my_tool"`), `tags`, `version`, `components` (`{"tool"}`, `{"resource"}`, `{"prompt"}`). `ctx.reset_visibility()` returns session to global defaults
- `ArgTransformConfig(hide=True, default_factory=lambda: str(uuid.uuid4()))` — dynamic default (requires `hide=True`). Static default: `default="value"`
- `ToolTransform` is deferred (tools from mounts/proxies). `Tool.from_tool()` is immediate (direct tool object) — use `ToolTransform` in `bootstrap/transforms.py`
- `download_tracks` refs: accepts YM track IDs (`"135055088"`) or local IDs (auto-resolves via `resolve_local_ids_to_ym`). Numbers < 100000 = local, >= 100000 = YM
- `download_tracks` automatically creates `DjLibraryItem` via `_link_file_to_track()` — no manual linking needed
- `score_delivery_transitions` returns `tuple[int, int]` (scored, conflicts), NOT dict
- `build_set` without features: fallback to `playlist_order` (not greedy/ga) — correct behavior
- `get_set` tracks view: includes `artist_names` via batch query (`get_by_ids` batch, not N+1)
- `TransitionIntent`: context-aware enum (maintain/ramp_up/cool_down/contrast) affects GA optimizer weights by track position
- `score_timbral`: 6th component of TransitionScorer, total weights = 1.0 (bpm 0.20 + harmonic 0.12 + energy 0.18 + spectral 0.20 + groove 0.15 + timbral 0.15). Source of truth: `app/core/constants.py:DEFAULT_TRANSITION_WEIGHTS`
- `import_tracks`: возвращает `id_mapping: dict[str, int]` (ym_id → local_id) для **всех** refs, включая skipped. `playlist_id` реально добавляет треки в плейлист (idempotent — пропускает уже существующие). `auto_analyze=True` запускает `TieredPipeline.ensure_level(...L3)` на impoted+existing IDs.
- `platform_playlists action=get_tracks`: `limit` (default 100, max 500) + `offset` обязательны для больших плейлистов. Ответ содержит `total`, `count`, `offset`, `limit`, `has_more`. Без них на плейлисте 1377 треков ответ ≈106k символов и переполняет MCP клиент.
- `get_track` / `TrackService.search` распознают `ym:12345` / `YM:12345` префикс и резолвят через `track_external_ids` (`yandex_music`). Plain text query — fallback по title/artist. Implementation в `app/services/track_service.py:_extract_ym_id`.

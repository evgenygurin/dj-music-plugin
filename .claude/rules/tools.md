---
description: MCP tool implementation patterns (FastMCP v3)
globs: app/controllers/tools/**/*.py
---

# MCP Tools

- Use standalone `@tool` decorator from `fastmcp` (FileSystemProvider auto-discovers, scans subpackages recursively)
- **Tag and annotation constants**: import from `app.controllers.tools._shared` — never hardcode literals
  - `tags={ToolCategory.CORE.value}` (StrEnum, no magic strings)
  - `annotations=ANNOTATIONS_READ_ONLY` / `ANNOTATIONS_WRITE` / `ANNOTATIONS_READ_ONLY_OPEN_WORLD`
  - `timeout=ToolTimeout.MEDIUM | HEAVY | BATCH`
- **Entity resolution**: use `resolve_track_id` / `resolve_entity` / `ensure_reference` from `_shared` — never re-implement `id|query` validation
- **Context logging**: wrap `ctx` in `ToolContext(ctx)` and call `await log.info(...)`, `log.progress(...)`, `log.elicit(...)` — never write `if ctx: await ctx.info(...)` guards
- **Action-dispatched tools** (`ym_playlists`, `ym_likes`, `manage_*`): use `ActionDispatcher[ResultT]` from `_shared.dispatch` — `@_dispatcher.register("name")` instead of `if/elif` chains. Duplicate registration raises at import time.
- Tool descriptions ≤50 words — details go in parameter descriptions
- Use `Depends()` for DI — hidden from tool schema automatically
- Return Pydantic models for `structuredContent` (not dicts) where the service supports it
- Use `view: Literal["summary", "full"]` pattern for progressive disclosure
- Never import repositories directly — use services via `Depends`
- Never call `session.commit()` — DI handles transaction lifecycle
- **No lazy imports inside function bodies** — hoist to module top. Lazy import = code smell.
- YM tools live in `app/controllers/tools/yandex/` (one file per entity), not in a flat `ym.py`

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
- `score_timbral`: 6th component of TransitionScorer, total weights = 1.0 (bpm 0.20 + harmonic 0.12 + energy 0.18 + spectral 0.20 + groove 0.15 + timbral 0.15). Source of truth: `app/core/constants.py:DEFAULT_TRANSITION_WEIGHTS`
- `import_tracks`: возвращает `id_mapping: dict[str, int]` (ym_id → local_id) для **всех** refs, включая skipped. `playlist_id` реально добавляет треки в плейлист (idempotent — пропускает уже существующие). `auto_analyze=True` запускает `TieredPipeline.ensure_level(...L3)` на impoted+existing IDs.
- `ym_playlists action=get_tracks`: `limit` (default 100, max 500) + `offset` обязательны для больших плейлистов. Ответ содержит `total`, `count`, `offset`, `limit`, `has_more`. Без них на плейлисте 1377 треков ответ ≈106k символов и переполняет MCP клиент.
- `get_track` / `TrackService.search` распознают `ym:12345` / `YM:12345` префикс и резолвят через `track_external_ids` (`yandex_music`). Plain text query — fallback по title/artist. Implementation в `app/services/track_service.py:_extract_ym_id`.

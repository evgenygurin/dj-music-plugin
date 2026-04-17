# DJ Music Plugin — Surface Redesign v2

**Date:** 2026-04-18
**Status:** Design — awaiting user approval.
**Scope:** Tool surface redesign (domain managers), handler gap closure (`deliver_set`, `classify_mood`), FastMCP v3 feature adoption (task=True, timeouts, native OTEL, elicitation). Seven phased rollouts.
**Relationship to Architecture Blueprint v1** (`2026-04-17-architecture-blueprint-design.md`): **supplements, does not replace**. Blueprint v1 defines bounded contexts + `EntityRegistry` + `ProviderRegistry` + handler/UoW pattern. This spec refines the **client-facing tool surface**, fixes **broken handlers/prompts** missed at cutover, and adopts **v3 features** missed by blueprint v1.

**Successor to:** blueprint v1 §7 (Tool Catalog), §9 (Prompt Catalog), §11 (Middleware), §12 (FastMCP v3+ Features).

---

## 1. Purpose

The current v1.0.1 runtime ships 13 generic dispatchers (`entity_list`, `entity_get`, `entity_create`, `entity_update`, `entity_delete`, `entity_aggregate`, `provider_read`, `provider_write`, `provider_search`, `transition_score_pool`, `sequence_optimize`, `playlist_sync`, `unlock_namespace`). An audit on 2026-04-18 identified:

- **Ergonomics pain.** User feedback: generic `entity_list(entity="track", filters={...})` reads worse than domain-scoped `tracks_list(filters={...})`; LLM must learn the abstract model before it can search for tracks.
- **Broken workflow.** `deliver_set_workflow` prompt instructs the LLM to call `entity_create(entity="app_export", ...)` and `provider_write(operation="create_from_set", ...)` — **neither exists** in `EntityRegistry` / yandex adapter. Runtime `NotFoundError`.
- **Dead integration.** `MoodClassifier` is implemented in `app/audio/classification/` but not imported by any handler, pipeline, or tool. `entity_create(entity="track_features", level=5)` produces features with `mood=None`. Workflows that depend on subgenre classification (`distribute_to_subgenres`, mood-filtered `entity_list`) silently fail.
- **Missed v3 adoption.** Blueprint v1 §12.2 marks `task=True` as "deferred experimental" — docs confirm production-ready since v2.14. Blueprint v1 §11 lists a custom `OTELTracingMiddleware` — v3 has native OpenTelemetry with MCP semantic conventions (zero config). Blueprint v1 §11 mentions `tool_timeout` middleware — v3 gives `@tool(timeout=...)` decorator (per-tool, cleaner).
- **Panel breakage.** `panel/actions/*.ts` still calls 0.7.1 tool names (`build_set`, `classify_mood`, `deliver_set`); after v1 cutover it is non-functional. Separate track.

This spec resolves the above in seven phases, keeping the blueprint v1 domain model and dependency rules intact.

**Out of scope for this spec:** runtime fix (user-driven: restart Claude + remove `cache/0.7.1`), panel rewrite details (allocated phase 4 but belongs to a separate panel-dedicated spec), auth/RLS, VM campaign script rewrite.

---

## 2. Audit findings (2026-04-18)

| # | Finding | Severity | Evidence | Disposition |
|---|---|---|---|---|
| G10 | resources v3 compliance (`return str\|bytes\|ResourceResult`) | ✅ PASS | All 24 `@resource` functions return `str` via `.model_dump_json()` or `json_dump(...)`. Private helpers return dict but are not registered. | No action. |
| G11 | prompts v3 compliance (`fastmcp.prompts.Message` / `PromptResult`) | ✅ PASS | All 6 `@prompt` files import `from fastmcp.prompts import Message, PromptResult, prompt`. No `mcp.types.PromptMessage` anywhere. | No action. |
| G1 | `deliver_set_workflow` prompt references unregistered entities | **P0** | `app/prompts/deliver_set_workflow.py:35-37` uses `entity="app_export"`, `provider_write(operation="create_from_set")`. `EntityRegistry.names()` has 11 entries, no `app_export`. No export tool exists. | Fix in Phase 2: introduce `sets_deliver` composite tool + rewrite prompt. |
| G2 | `MoodClassifier` not wired | **P0** | `rg "MoodClassifier\|mood_classifier" app/handlers/ app/tools/ app/server/` = 0 matches. `app/audio/pipeline.py` does not import it. | Fix in Phase 2: wire classifier into `track_features_analyze_handler` at level>=2 + add `playlists_distribute` tool. |
| G3 | Panel calls 0.7.1 tool names | P1 | `panel/actions/*.ts` references `build_set`, `classify_mood`, `deliver_set`, `analyze_track`. | Fix in Phase 4: migrate to domain managers. |
| G4 | RLS disabled on 40 tables | P1 | Supabase security advisor, `rls_disabled_in_public` severity=critical. | **Out of scope** — separate auth spec. |
| G5 | L3/L4 coverage ≈ 0 | P2 | `track_audio_features_computed`: 23658 at L2, 110 at L3, 0 at L4. 97/23929 audio files downloaded. | Data gap, not design. Addressed separately via BG campaign revival. |
| G6 | VM scripts stubbed | P2 | `scripts/vm_import_and_analyze.py` and `scripts/ym_bfs_expand.py` reduced to placeholders after v1 cutover. | **Out of scope** unless user requests revival; Phase 5 offers `task=True` as replacement. |
| G9 | Runtime loads cache/0.7.1 not 1.0.1 | P0 (ops) | `ps -ef` shows `exec .venv/bin/fastmcp run app/server.py` from `.../0.7.1/`. All MCP calls return `internal error`. | **User-driven:** `exit && claude` + `rm -rf ~/.claude/plugins/cache/dj-music-plugin/dj-music/0.7.1`. Not a code change. |
| G12 | Custom `OTELTracingMiddleware` duplicates native OTEL | P1 | Blueprint v1 §11 row 3. `docs/servers/telemetry.mdx` confirms zero-config native OTEL with MCP semantic conventions. | Remove in Phase 3. |
| G13 | `transition_score_pool` / `sequence_optimize` have no timeout | P1 | N=500 GA optimization can run >10min. Client disconnects before completion. | Phase 3: add `@tool(timeout=60)` / `timeout=300`. |
| G14 | L5 analyze blocking (`task=True` not used) | P2 | `track_features_analyze_handler` runs synchronously, client waits minutes. | Phase 5: opt-in `task=True` for level=5, Redis backend in prod. |
| G15 | Tool returns untyped `dict` instead of Pydantic | P2 | Raw dispatchers return `dict[str, Any]` — schema generation uses anonymous object. Pydantic models would give clients richer `outputSchema`. | Phase 3: migrate to `app/schemas/tool_responses.py` (already exists per blueprint). |

---

## 3. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | **Hybrid surface**: v1 dispatchers remain (tag=`internal`, versioned `v1.0`), add 12 domain managers (tag=`namespace:domain:<X>`, versioned `v2.0`) via `ToolTransform` facade with `ArgTransform(hide=True, default="<entity>")`. Zero schema duplication. | brainstorm + v3 docs §tool-transformation |
| D2 | **snake_case tool names** (`tracks_list`, not `tracks.list`). Dots break some MCP clients; FastMCP convention produces `api_tool_name` via Namespace. | v3 docs §namespace |
| D3 | **Versioning deprecation window**: managers ship as `v2.0`, raw dispatchers stay `v1.0` (tagged `internal`, visible only via BM25 `search_tools` + `call_tool`). After 3 release cycles (+ telemetry confirms zero v1.0 call traffic via `DeprecationWarningMiddleware`), drop `v1.0` from registry. Panel + docs migrate in Phase 4. | v3 docs §versioning, §visibility |
| D4 | **BM25SearchTransform** is already active in runtime; keep. `always_visible=[tracks_list, tracks_get, transitions_score, sets_build, library_aggregate, unlock_namespace]` (6 tools). Managers NOT in always_visible are discoverable via natural-language search. | v3 docs §tool-search, existing runtime |
| D5 | **CodeMode** is feature-flag `DJ_MCP_CODE_MODE=1`, default off. When on, it replaces manager surface with 4 meta-tools (`search` + `get_schema` + `list_tools` + `execute`) — targets `full_pipeline` workflow where the LLM benefits from writing a script instead of 15 round-trips. Requires `fastmcp[code-mode]` extra. Phase 6. | v3 docs §code-mode |
| D6 | **`sets_deliver` is a standalone composite tool, not `entity_create(entity="set_delivery")`**. Deliver is workflow (score → export files → copy MP3 → optional YM sync), not CRUD over an aggregate root. Forces `sets_deliver` to be outside `EntityRegistry`. | brainstorm |
| D7 | **Classifier wiring**: `MoodClassifier` gets invoked inside `track_features_analyze_handler` whenever the run produces level>=2 features; `mood` + `mood_confidence` persist into `track_audio_features_computed`. Separate `playlists_distribute` tool wraps batch classify + playlist-sync-per-subgenre orchestration. | brainstorm |
| D8 | **Drop custom OTEL middleware**. Replace with env-var driven `opentelemetry-instrument`. Remove `app/server/middleware/otel_tracing.py` + blueprint v1 row 3. | v3 docs §telemetry |
| D9 | **Per-tool timeouts**: `transition_score_pool timeout=60`, `sequence_optimize timeout=300`, all other managers default (no timeout). Replaces blueprint v1 §11 row 13 `ToolCallTimeoutMiddleware`. | v3 docs §tools |
| D10 | **`task=True` for `tracks_analyze` when level=5**. Default backend `memory://` (single-process). Prod deployment sets `FASTMCP_DOCKET_URL=redis://...`. Embedded worker auto-starts; multi-worker scaling via `fastmcp tasks worker server.py`. | v3 docs §tasks |
| D11 | **`ctx.elicit`** for deliver-set hard-conflict gate. Current prompt embeds the question as natural-language instruction ("Use ctx.elicit to ask the user…") — now moved inside the `sets_deliver` tool as `response_type=Literal["continue", "abort"]`. Deterministic; doesn't depend on the LLM interpreting prompt text correctly. | v3 docs §elicitation |
| D12 | **Panel migration runs in parallel** with Phase 3 backend cleanup. Separate PR, separate panel-dedicated spec; this spec references only the tool-name migration contract. | D1 versioning allows this |
| D13 | **15 dead DB tables NOT dropped** (blueprint v1 D16 reversed per `CONTINUE.md:47`). They are pre-built schema for REQUIREMENTS.md features. Empty tables cost ~24 KB each. Keep. | user, CONTINUE.md |
| D14 | **Pydantic return types** for every domain manager and raw dispatcher. Schemas live in `app/schemas/tool_responses.py` (already exists). Phase 3 audits + migrates. | v3 docs §tools structured output |
| D15 | **No session-level redis store** for now. `session_state_store` stays in-memory (single-user deployment). Future scope when multi-user Panel demands. | YAGNI |
| D16 | **No OAuth/authorization**. Single-user server. Out of scope. | YAGNI |

---

## 4. Target Surface

### 4.1 Domain managers (12, tag=`namespace:domain:<X>`, version=2.0)

| Manager | Delegates to (v1 dispatcher) | Handler (entity-side-effect) | Namespace | Default visibility |
|---|---|---|---|---|
| `tracks_list` | `entity_list(entity="track")` | — | `domain:tracks` | ON (in always_visible) |
| `tracks_get` | `entity_get(entity="track")` | — | `domain:tracks` | ON (in always_visible) |
| `tracks_import` | `entity_create(entity="track")` | `track_import` | `domain:tracks` | ON |
| `tracks_analyze` | `entity_create(entity="track_features")` | `track_features_analyze` (**wired with classifier** per D7), `task=True` when level=5 (D10) | `domain:tracks` | ON |
| `tracks_audio_download` | `entity_create(entity="audio_file")` | `audio_file_download` | `domain:tracks` | ON |
| `playlists_list` | `entity_list(entity="playlist")` | — | `domain:playlists` | ON |
| `playlists_sync` | `playlist_sync` (raw) | — | `domain:playlists` | unlock required |
| `playlists_distribute` | NEW composite — not a single dispatcher | **NEW handler per D7**: classify + push-to-subgenre-playlist | `domain:playlists` | unlock required |
| `sets_build` | `entity_create(entity="set_version")` | `set_version_build` | `domain:sets` | ON (in always_visible) |
| `sets_get` | `entity_get(entity="set")` + `entity_get(entity="set_version")` composite | — | `domain:sets` | ON |
| `sets_deliver` | **NEW standalone tool per D6** — not under EntityRegistry | composite: `transition_score_pool` + export + copy + optional `playlist_sync` | `domain:sets` | unlock required |
| `transitions_score` | composite of `transition_score_pool` + `sequence_optimize` for common case (score N tracks, return top pairs ordered) | — | `domain:transitions` | ON (in always_visible) |

Plus:
- `library_aggregate` — thin facade over `entity_aggregate` (unchanged signature). Namespace `domain:library`. ON (always_visible).
- `unlock_namespace` — unchanged. Namespace `admin`. ON (always_visible).

**Always_visible list** (6): `tracks_list`, `tracks_get`, `transitions_score`, `sets_build`, `library_aggregate`, `unlock_namespace`. Plus BM25 synthetic: `search_tools`, `call_tool`. **Total always-on: 8 tools.** Others discoverable via `search_tools("import tracks from yandex")` etc.

### 4.2 Raw dispatchers (13, tag=`internal`, version=1.0)

Unchanged from blueprint v1 §7. Remain in registry for: (a) deprecation period, (b) composite tools that need direct dispatcher access, (c) CodeMode `execute` sandbox. Hidden from `list_tools()` via `mcp.disable(tags={"internal"})`. Callable via `call_tool(name="entity_list", arguments={...})`.

### 4.3 Namespace / visibility matrix

| Namespace tag | Members | Default state | Unlock action |
|---|---|---|---|
| `namespace:domain:tracks` | tracks_list/get/import/analyze/audio_download | ON | — |
| `namespace:domain:sets` | sets_build/get | ON | — |
| `namespace:domain:sets:destructive` | sets_deliver | OFF | `unlock_namespace("sets:destructive")` |
| `namespace:domain:playlists` | playlists_list | ON | — |
| `namespace:domain:playlists:write` | playlists_sync, playlists_distribute | OFF | `unlock_namespace("playlists:write")` |
| `namespace:domain:transitions` | transitions_score | ON | — |
| `namespace:domain:library` | library_aggregate | ON | — |
| `admin` | unlock_namespace | ON | — |
| `internal` | 13 v1 dispatchers | OFF (permanently) | never unlocked; callable via `call_tool` |

Unlock semantics (per v3 docs): `unlock_namespace("playlists:write")` internally calls `ctx.enable_components(tags={"namespace:domain:playlists:write"})`. Per-session. Auto-fires `notifications/tools/list_changed`.

### 4.4 Resources (26) — unchanged

Per blueprint v1 §8. All v3-compliant (audit G10 PASS). No changes in this spec.

### 4.5 Prompts (6) — two rewritten

Per blueprint v1 §9. All v3-compliant (audit G11 PASS). **Phase 3 rewrites** `deliver_set_workflow` and `full_pipeline` to use new `sets_deliver` and `playlists_distribute` tools instead of referencing non-existent `app_export` entity. Other four prompts (`dj_expert_session`, `build_set_workflow`, `expand_playlist_workflow`, `quick_mix_check`) unchanged.

---

## 5. Mechanism

### 5.1 ToolTransform + ArgTransform facade

One file `app/server/surface.py` defines all manager configs; one call registers them.

```python
# app/server/surface.py

from __future__ import annotations

from fastmcp.server.transforms import ToolTransform
from fastmcp.tools.tool_transform import ArgTransform, ToolTransformConfig

TRACKS_LIST = ToolTransformConfig(
    name="tracks_list",
    description=(
        "List tracks with optional filtering, sorting, and field projection. "
        "Filters use Django-style lookups: bpm__gte, mood__in, key_code__eq, "
        "has_features, title__icontains, id__in, created_at__range."
    ),
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track"),
        "filters": ArgTransform(
            description='Django-style filter dict, e.g. {"bpm__gte": 120, "mood__in": ["peak_time", "acid"]}',
            examples=[
                {"bpm__gte": 120, "bpm__lte": 135},
                {"mood__in": ["peak_time"], "has_features": True},
                {"id__in": [42, 61, 88]},
            ],
        ),
    },
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

TRACKS_GET = ToolTransformConfig(
    name="tracks_get",
    description="Fetch a single track by local ID with optional field projection.",
    tags={"namespace:domain:tracks", "read"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track"),
    },
    annotations={"readOnlyHint": True, "idempotentHint": True},
)

TRACKS_IMPORT = ToolTransformConfig(
    name="tracks_import",
    description=(
        "Import tracks from a provider. Fetches metadata and persists Track + "
        "provider-specific metadata (yandex: album, artist, cover, explicit). "
        "Idempotent: existing tracks re-fetched only if `force=true`."
    ),
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track"),
        "data": ArgTransform(
            description='{"provider": "yandex", "provider_track_ids": ["123", "456"], "force": false}',
            examples=[{"provider": "yandex", "provider_track_ids": ["61297756"]}],
        ),
    },
)

TRACKS_ANALYZE = ToolTransformConfig(
    name="tracks_analyze",
    description=(
        "Run tiered audio analysis on tracks. Level 1 (BPM/LUFS), 2 (+mood via classifier), "
        "3 (+key/MFCC for scoring), 4 (+structure for transitions), 5 (all + structure)."
    ),
    tags={"namespace:domain:tracks", "write"},
    version="2.0",
    transform_args={
        "entity": ArgTransform(hide=True, default="track_features"),
        "data": ArgTransform(
            description='{"track_ids": [42, 61], "level": 2, "force": false}',
            examples=[{"track_ids": [42, 61], "level": 2}],
        ),
    },
)

# ... TRACKS_AUDIO_DOWNLOAD, PLAYLISTS_*, SETS_*, TRANSITIONS_SCORE, LIBRARY_AGGREGATE

MANAGERS: dict[str, ToolTransformConfig] = {
    "entity_list": TRACKS_LIST,  # produces tracks_list
    "entity_get": TRACKS_GET,
    "entity_create": TRACKS_IMPORT,  # multi-map: see §5.2 for many-to-one
    # ...
}
```

### 5.2 Multi-map problem and resolution

`ToolTransform` expects `{original_tool_name: config}` — one config per original. But we want **several domain managers** over **one** raw dispatcher (e.g., `entity_list` produces both `tracks_list` and `playlists_list`). Solution: use separate `ToolTransform` instances, one per manager. Each config's `name` differs so the registry gets separate entries.

```python
# app/server/surface.py

def register_managers(mcp: FastMCP) -> None:
    mcp.add_transform(ToolTransform({"entity_list": TRACKS_LIST}))
    mcp.add_transform(ToolTransform({"entity_list": PLAYLISTS_LIST}))
    mcp.add_transform(ToolTransform({"entity_list": SET_VERSIONS_LIST}))  # if needed
    mcp.add_transform(ToolTransform({"entity_get": TRACKS_GET}))
    mcp.add_transform(ToolTransform({"entity_get": SETS_GET}))
    # ... one line per manager
```

Each `ToolTransform(...)` creates a new derived tool in the registry with its configured name. The original `entity_list` remains unchanged and callable.

### 5.3 Hiding raw dispatchers

```python
# app/server/app.py

from app.server.surface import register_managers

def build_mcp_server() -> FastMCP:
    mcp = FastMCP("dj-music", ...)
    # ... providers, middleware, existing BM25 transform
    register_managers(mcp)
    mcp.disable(tags={"internal"})  # raw dispatchers hidden from list_tools
    # They remain callable via call_tool(name="entity_list", ...) for:
    #   - BM25 search_tools results (search sees all, respecting visibility)
    #   - composite managers that use them internally
    return mcp
```

**Visibility behavior per v3 docs §tool-search:** "Tools filtered by middleware, visibility transforms, or component-level auth checks won't appear in search results." Therefore `mcp.disable(tags={"internal"})` hides raw dispatchers from BOTH `list_tools()` and BM25 `search_tools`. This is the intended final-state behavior (Phase 7). During deprecation (Phase 1-6) we want v1 dispatchers STILL discoverable via search so that migration-in-progress callers (panel, scripts) can find them.

**Deprecation-period arrangement:** use tag `deprecated` instead of `internal` during Phase 1-6. `deprecated`-tagged dispatchers are:

- excluded from default `list_tools()` via `mcp.disable(tags={"deprecated"})`;
- re-enabled per-session on demand — `unlock_namespace(namespace="deprecated")` accepts this special token and calls `ctx.enable_components(tags={"deprecated"})`;
- BM25-discoverable only after the session-level unlock.

Phase 7 renames `deprecated` → `internal` (and/or drops v1 entirely via `remove_tool(name, version="1.0")`), after which search no longer surfaces them at all.

### 5.4 Composite tools (not via ArgTransform)

Three managers can't be expressed as pure `ToolTransform` over a single dispatcher — they are composites. Each gets a standalone `@tool` in `app/tools/domain/`:

- `app/tools/domain/sets_deliver.py` — `sets_deliver(set_id, sync_to_ym=False)` — see §6.1.
- `app/tools/domain/playlists_distribute.py` — `playlists_distribute(source_playlist_id, force=False)` — see §6.2.
- `app/tools/domain/transitions_score.py` — `transitions_score(track_ids, algorithm="greedy", top_k=10)` — thin composite over `transition_score_pool` + `sequence_optimize`. Phase 1 ships it; Phase 3 refines.

These live under `app/tools/domain/` to keep the directory convention (all `@tool` decorators under `app/tools/`). They delegate to lower-level dispatchers via direct Python calls (not `call_tool`), respecting UoW injection.

---

## 6. Handler gap closure (P0)

### 6.1 G1 — `sets_deliver` composite tool

**File:** `app/tools/domain/sets_deliver.py` (NEW).

**Signature:**

```python
from typing import Annotated, Literal

from fastmcp import tool, Context, Depends
from pydantic import BaseModel, Field

from app.server.di import get_uow, get_provider_registry
from app.repositories.unit_of_work import UnitOfWork

class SetsDeliverResult(BaseModel):
    set_id: int
    version_id: int
    quality_score: float
    exports: list[dict]  # [{"format": "m3u8", "file_path": "...", "size_bytes": 1234}, ...]
    mp3_copied: int
    mp3_skipped_icloud_stub: int
    ym_playlist_id: str | None
    hard_conflicts_at_start: int
    hard_conflicts_resolved: Literal["continue", "abort", "none"]

@tool(
    name="sets_deliver",
    description=(
        "Deliver a DJ set end-to-end: score transitions, review for hard conflicts "
        "(user-confirmed via elicitation), export M3U8/Rekordbox XML/JSON guide "
        "files, copy MP3s into generated-sets/, and optionally sync to Yandex "
        "Music. Replaces v0.7.1 deliver_set + deliver_set_workflow prompt."
    ),
    tags={"namespace:domain:sets:destructive", "write", "delivery"},
    annotations={"destructiveHint": True, "idempotentHint": False},
    version="2.0",
    timeout=600.0,  # 10 min budget for score + export + copy + sync
)
async def sets_deliver(
    set_id: Annotated[int, Field(description="DJ set ID (local).")],
    sync_to_ym: bool = False,
    version_id: int | None = None,  # defaults to latest
    uow: UnitOfWork = Depends(get_uow),
    providers = Depends(get_provider_registry),
    ctx: Context = ...,
) -> SetsDeliverResult:
    # Step 1: resolve set + version
    # Step 2: compute fresh transition scores via transition_score_pool logic (persist to DB)
    # Step 3: audit hard conflicts (from app/domain/audit/)
    # Step 4: if hard_conflicts > 0:
    #   elicit = await ctx.elicit(
    #       message=f"Set has {hard_conflicts} hard transition conflicts. Continue?",
    #       response_type=Literal["continue", "abort"],
    #   )
    #   if elicit.action != "accept" or elicit.data == "abort": return early
    # Step 5: write exports (M3U8, XML, JSON) via app/domain/delivery/writers (port from v0.7.1 delivery_service)
    # Step 6: copy MP3 files into generated-sets/<sanitized_name>/ (skip iCloud stubs <90% size)
    # Step 7: if sync_to_ym: providers.get("yandex").playlist_create_from_set(...)
    # Step 8: return SetsDeliverResult
    ...
```

**Handler/domain module organization:**

The writer logic (M3U8 tag formatting, XML generation, JSON guide) lives in a new `app/domain/delivery/` module (**pure, no I/O except file write at call site**) — ported from what blueprint v1 migration map (§14.3) labels as `app/services/delivery_service.py` → `app/handlers/set_deliver.py + app/domain/audit/`. Since we moved deliver to a standalone tool rather than a handler, the writer logic goes directly under `app/domain/delivery/` for test isolation; the tool function orchestrates.

**Elicitation:** `ctx.elicit(message, response_type=Literal["continue", "abort"])` returns `AcceptedElicitation(data="continue")` or equivalent. Abort returns `SetsDeliverResult(hard_conflicts_resolved="abort", exports=[], ...)` — no error raised (user made a choice, not a failure).

**Prompt `deliver_set_workflow` rewrite** (Phase 3):

```python
def _build_body(set_id: int, sync_to_ym: bool) -> str:
    return f"""Deliver set {set_id}:

1. Unlock destructive namespace if not already:
   unlock_namespace(namespace="sets:destructive", action="unlock")

2. Call sets_deliver(set_id={set_id}, sync_to_ym={str(sync_to_ym).lower()})

3. The tool will automatically:
   - Score transitions fresh
   - Elicit user confirmation if hard conflicts exist
   - Write M3U8/XML/JSON exports
   - Copy MP3 files
   - Sync to Yandex Music (if sync_to_ym=true)

4. Return the SetsDeliverResult for the user to review.
"""
```

Trivial: one tool call, no error path left for the LLM to mis-handle.

### 6.2 G2 — `MoodClassifier` wiring + `playlists_distribute`

**Wiring in `track_features_analyze_handler`:**

```python
# app/handlers/track_features_analyze.py (MODIFIED)

from app.audio.classification import MoodClassifier

async def track_features_analyze_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    pipeline: AnalysisPipeline,
    classifier: MoodClassifier,  # NEW — injected via DI per Phase 2
) -> dict[str, Any]:
    # ... existing loop ...
    for tid in track_ids:
        result = await pipeline.analyze_to_level(...)
        if result.level >= 2 and result.features is not None:
            mood_result = classifier.classify(result.features)  # NEW
            await uow.track_features.update_mood(
                track_id=tid,
                mood=mood_result.mood,
                mood_confidence=mood_result.confidence,
            )
        # ...
```

**DI update:**

```python
# app/server/di.py (MODIFIED)

def get_mood_classifier() -> MoodClassifier:
    return _CLASSIFIER_SINGLETON  # constructed in lifespan
```

```python
# app/server/lifespan.py (MODIFIED)

from app.audio.classification import MoodClassifier

@lifespan
async def audio_lifespan(server):
    pipeline = AnalysisPipeline(...)
    classifier = MoodClassifier(profiles=ALL_PROFILES)
    yield {"pipeline": pipeline, "mood_classifier": classifier}
```

**Repository method:**

```python
# app/repositories/track_features.py (NEW method)

class TrackFeaturesRepository(BaseRepository[TrackAudioFeaturesComputed]):
    async def update_mood(self, *, track_id: int, mood: str, mood_confidence: float) -> None:
        stmt = (
            update(TrackAudioFeaturesComputed)
            .where(TrackAudioFeaturesComputed.track_id == track_id)
            .values(mood=mood, mood_confidence=mood_confidence)
        )
        await self.session.execute(stmt)
```

**`playlists_distribute` tool:**

```python
# app/tools/domain/playlists_distribute.py (NEW)

class DistributeResult(BaseModel):
    source_playlist_id: int
    total_tracks: int
    classified: dict[str, int]  # {"peak_time": 42, "acid": 18, ...}
    target_playlists: dict[str, int]  # {"peak_time": 1234, "acid": 1235, ...}
    synced: dict[str, list[int]]  # {"peak_time": [track_id_1, ...], ...}
    skipped_missing_features: int
    errors: list[dict]

@tool(
    name="playlists_distribute",
    description=(
        "Distribute tracks from a source playlist across subgenre playlists based "
        "on mood classification. Auto-analyzes tracks at L2 if features missing. "
        "Target playlists are resolved per settings.subgenre_playlist_mapping."
    ),
    tags={"namespace:domain:playlists:write", "write"},
    annotations={"destructiveHint": True, "idempotentHint": True},
    version="2.0",
    timeout=1800.0,
)
async def playlists_distribute(
    source_playlist_id: int,
    force: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    pipeline: AnalysisPipeline = Depends(get_pipeline),
    classifier: MoodClassifier = Depends(get_mood_classifier),
    providers = Depends(get_provider_registry),
    ctx: Context = ...,
) -> DistributeResult:
    # 1. Load source playlist tracks
    # 2. For each track: if features missing, analyze at L2 (inline, not task); else use cached
    # 3. Classify each (or use cached mood)
    # 4. Group by mood
    # 5. For each mood: push to corresponding subgenre playlist via playlist_sync
    # 6. Report totals
    ...
```

Replaces v0.7.1 `distribute_to_subgenres` + `classify_mood` tools.

### 6.3 EntityRegistry changes

`track_features` config adds handler dependency on classifier:

```python
EntityConfig(
    name="track_features",
    # ...
    create_handler=track_features_analyze_handler,  # now uses classifier too
    update_handler=track_features_reanalyze_handler,  # also wired
)
```

No new entity registered. `playlists_distribute` and `sets_deliver` are tools, not entities.

---

## 7. Prompt rewrites

| Prompt | Current state | Phase 3 action |
|---|---|---|
| `dj_expert_session` | OK | no change |
| `build_set_workflow` | OK | no change |
| `deliver_set_workflow` | **Broken** — references `entity="app_export"` | **Rewrite** to call `sets_deliver` (see §6.1) |
| `expand_playlist_workflow` | references `provider_read(entity="similar_tracks", ...)` | verify exists in yandex adapter; if not, fix Phase 2 |
| `full_pipeline` | chains expand → build → deliver | **Update** delivery step to call `sets_deliver` |
| `quick_mix_check` | OK | no change |

---

## 8. FastMCP v3 features adoption

### 8.1 `task=True` for tracks_analyze (Phase 5)

```python
TRACKS_ANALYZE = ToolTransformConfig(
    name="tracks_analyze",
    # ...
)

# Additionally: in Phase 5, extend the handler wiring so that when level=5,
# the underlying entity_create is invoked with task_meta set, producing
# CreateTaskResult. The caller polls task status via MCP task protocol.
#
# Because ToolTransform cannot alter the tool's task config, we need a
# second approach: a parallel `tracks_analyze_bg` standalone tool with
# task=True that delegates to the handler.

@tool(
    name="tracks_analyze_bg",
    tags={"namespace:domain:tracks", "write", "background"},
    task=True,
    version="2.0",
)
async def tracks_analyze_bg(
    track_ids: list[int],
    level: int = 5,
    force: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    pipeline: AnalysisPipeline = Depends(get_pipeline),
    classifier: MoodClassifier = Depends(get_mood_classifier),
    progress: Progress = Progress(),
    ctx: Context = ...,
) -> dict:
    ...
```

Foreground `tracks_analyze` continues to work for level 1-3 (fast). Background `tracks_analyze_bg` for level 4-5. Namespace `namespace:domain:tracks:background` unlock required (avoid LLM accidentally using the background variant for cheap queries).

Backend: `memory://` default (single-process worker embedded). Prod: `FASTMCP_DOCKET_URL=redis://localhost:6379`. Multi-worker: `fastmcp tasks worker server.py`. Replaces VM `systemd-run` for L5 sweeps (Phase 5 is opt-in).

### 8.2 Per-tool timeouts (Phase 3)

```python
@tool(timeout=60.0)  # transition_score_pool
@tool(timeout=300.0)  # sequence_optimize
@tool(timeout=600.0)  # sets_deliver
@tool(timeout=1800.0)  # playlists_distribute
```

Replaces blueprint v1 §11 row 13 `ToolCallTimeoutMiddleware`.

### 8.3 Native OpenTelemetry (Phase 3)

Remove `app/server/middleware/otel_tracing.py` (if it exists; check). Blueprint v1 middleware list drops from 16 → 15 (or 14 if DbSessionMiddleware is also replaced with DI — see §8.5).

Prod enablement (runbook, not code):

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install

opentelemetry-instrument \
  --service_name dj-music-v1 \
  --exporter_otlp_endpoint http://localhost:4317 \
  fastmcp run server.py
```

Spans auto-generated with MCP semantic conventions (`tools/call {name}`, `resources/read`, `prompts/get {name}`, `delegate {name}`). Custom attributes: `fastmcp.server.name`, `fastmcp.component.type`, `fastmcp.provider.type`.

### 8.4 `ctx.elicit` in sets_deliver

Per §6.1. Deterministic hard-conflict gate; replaces natural-language instruction in old prompt.

### 8.5 UoW lifecycle — keep DbSessionMiddleware for now

Blueprint v1 §11 row 15 defines `DbSessionMiddleware` to open UoW and commit/rollback on success/exception. v3 docs §dependency-injection shows an alternative pattern where `Depends(get_uow)` uses an async context manager and the DI layer handles commit/rollback via generator protocol.

**Decision:** keep `DbSessionMiddleware` unchanged in Phase 3. The `ToolTransform` facade delegates to the underlying dispatcher which already receives `uow` via `Depends(get_uow)`; that chain works identically whether commit happens in middleware or in DI context manager. Migrating is a cross-cutting refactor with no surface benefit. Revisit only if a concrete pain point (e.g., middleware-DI ordering bug) surfaces.

### 8.6 CodeMode behind feature flag (Phase 6)

```python
# app/server/app.py

if settings.mcp_code_mode_enabled:  # DJ_MCP_CODE_MODE=1
    from fastmcp.experimental.transforms.code_mode import CodeMode, Search, GetSchemas
    mcp.add_transform(CodeMode(
        discovery_tools=[Search(default_detail="brief"), GetSchemas(default_detail="detailed")],
        sandbox_provider=MontySandboxProvider(
            limits={"max_duration_secs": 30, "max_memory": 100_000_000},
        ),
    ))
```

`settings.mcp_code_mode_enabled` goes in `app/config/mcp.py`. Default `False`. Extra: `pip install 'fastmcp[code-mode]'`.

### 8.7 Pydantic return types (Phase 3)

Audit `app/schemas/tool_responses.py`. Each dispatcher + manager returns a specific model, not `dict`. Outputs become self-documenting via `outputSchema`.

---

## 9. Phased rollout

Each phase = separate PR. Each PR targets `dev`. Squash-merge after review. Release window: ~2 weeks per phase, parallelism where safe.

### Phase 0 — Preflight (sequential, blocks all)

**0a. Runtime fix (user-driven, no code change).**
- User: `exit && claude`, `rm -rf ~/.claude/plugins/cache/dj-music-plugin/dj-music/0.7.1`, relaunch.
- Verify: `unlock_namespace(action="status", namespace="all")` returns v1 dispatchers.

**0b. Spec approval.** This document, approved by user before any implementation.

**Exit:** runtime green, spec signed off.

### Phase 1 — Domain Manager facade (1-2 days)

- Create `app/server/surface.py` with 12 `ToolTransformConfig`s.
- Register via `register_managers(mcp)` in `build_mcp_server()`.
- `mcp.disable(tags={"internal"})` to hide raw dispatchers from `list_tools`.
- Update always_visible set: `[tracks_list, tracks_get, transitions_score, sets_build, library_aggregate, unlock_namespace]`.
- Add `app/tools/domain/transitions_score.py` (composite).

**Tests:**
- Metadata: each manager has correct name, version=2.0, tags, description.
- Parity: `tracks_list(filters={"bpm__gte": 120})` produces identical result to `entity_list(entity="track", filters={"bpm__gte": 120})`.
- Visibility: `list_tools()` returns 8 always_visible + managers for unlocked namespaces. `internal` dispatchers absent.
- BM25 search: `search_tools("score transition")` returns `transitions_score` as top hit.

**Exit:** `make check` green. `fastmcp list server.py` shows 20+ managers alongside dispatchers. Smoke test via `Client(mcp)` in-memory.

### Phase 2 — Handler gap closure (2-3 days)

- Wire `MoodClassifier` into `track_features_analyze_handler` (§6.2).
- Add `TrackFeaturesRepository.update_mood` method.
- Add `app/tools/domain/playlists_distribute.py` (§6.2).
- Add `app/tools/domain/sets_deliver.py` (§6.1) + `app/domain/delivery/` module (port M3U8/XML/JSON writers from legacy `delivery_service.py`).
- Update `track_features_reanalyze_handler` to also run classifier at level>=2.

**Tests:**
- `track_features_analyze_handler` end-to-end: L2 features → mood persisted.
- `playlists_distribute` on seeded DB: classifies, groups, pushes to subgenre playlists (via yandex adapter mock).
- `sets_deliver` with no hard conflicts: exports + copy + sync.
- `sets_deliver` with hard conflicts + mocked `ctx.elicit` accept="continue": proceeds.
- `sets_deliver` with hard conflicts + mocked `ctx.elicit` accept="abort": short-circuits.

**Exit:** Phase 1 tests + new tests green. `entity_create(entity="track_features", data={"track_ids": [X], "level": 2})` produces features with `mood != None`.

### Phase 3 — Prompt rewrites + v3 cleanup (1-2 days)

- Rewrite `deliver_set_workflow` (§7) to call `sets_deliver`.
- Rewrite `full_pipeline` delivery step to call `sets_deliver`.
- Add `timeout=` to compute tools (§8.2).
- Remove custom `OTELTracingMiddleware`; document env-var enablement (§8.3).
- Audit `app/schemas/tool_responses.py` — migrate any `dict[str, Any]` returns to Pydantic models (§8.7).
- Evaluate replacing `DbSessionMiddleware` with `Depends(get_uow)` context manager (§8.5). Defer if behavior-preserving swap is non-trivial.

**Tests:**
- Prompt snapshot tests (`inline-snapshot`) for rewritten prompts.
- Tool-return schema validation.
- Timeout enforcement: construct `transition_score_pool(track_ids=[...2000 mocked...])` that would exceed 60s, assert MCP error `-32000`.

**Exit:** all v1 prompts produce valid chains; tool responses carry rich `outputSchema`; OTEL traceable via `opentelemetry-instrument` (dev test).

### Phase 4 — Panel migration (2-3 days)

- `panel/actions/*.ts`: replace `build_set` → `sets_build`, `classify_mood` + `distribute_to_subgenres` → `playlists_distribute`, `deliver_set` → `sets_deliver`, `analyze_track`/`analyze_batch` → `tracks_analyze`, `find_similar_tracks` → `provider_read(entity="track_similar")` via `provider.find_similar` manager alias (add if useful).
- `panel/lib/mcp-client.ts`: if any tool name hardcoded, update.
- E2E: start backend + panel, exercise dashboard + set-builder + delivery flow.

**Tests:**
- panel e2e via playwright smoke: library → classify → build set → deliver.

**Exit:** panel serves live data from v2 managers. No 0.7.1 name references remain.

### Phase 5 — `task=True` for L5 (opt-in, 2-3 days)

- Add `tracks_analyze_bg` standalone tool (§8.1).
- Namespace `namespace:domain:tracks:background` unlock-required.
- Default `FASTMCP_DOCKET_URL=memory://`. Prod deployment notes: `redis://`, multi-worker.
- Test: `tracks_analyze_bg(track_ids=[X], level=5)` returns task ID immediately; poll returns progress 0→100; final result has all L5 features + structure.

**Optional for Phase 5:** revive VM scripts as wrapper around `tracks_analyze_bg` via MCP client — replaces `systemd-run` pattern. Separate PR.

**Exit:** background analysis works end-to-end with polling. Redis deployment documented.

### Phase 6 — CodeMode feature flag (1 day)

- Add `mcp_code_mode_enabled` to `app/config/mcp.py`.
- Conditional `CodeMode(...)` transform in `build_mcp_server()` (§8.6).
- Document: `DJ_MCP_CODE_MODE=1` + `pip install 'fastmcp[code-mode]'`.
- Test manually via `full_pipeline` scenario.

**Exit:** flag works; experimental path available for power users.

### Phase 7 — v1 sunset (2-3 release cycles later)

- Inspect audit logs / `DeprecationWarningMiddleware` telemetry: confirm zero traffic to v1 dispatchers from external callers (only internal composites).
- Remove `tag="internal"` dispatchers from `list_tools` search results (switch to version filter `VersionFilter(version_gte="2.0")`).
- Drop v1.0 variants: `mcp.local_provider.remove_tool("entity_list", version="1.0")` etc.
- Update docs, CHANGELOG.

**Exit:** managers are the only surface. v1 dispatchers gone from registry.

---

## 10. Testing strategy

### 10.1 Per-phase coverage targets

| Layer | Phase | Test type |
|---|---|---|
| Manager registration | 1 | Contract test — name, version, tags, annotations match config |
| Manager delegation | 1 | Parity test — `tracks_list(...)` == `entity_list(entity="track", ...)` |
| BM25 search results | 1 | Assert natural queries return manager names |
| Visibility state | 1 | `list_tools` after unlock cycles |
| Classifier wiring | 2 | L2 analyze → mood persisted |
| `sets_deliver` | 2 | End-to-end with mocked filesystem + yandex |
| Elicitation | 2 | Mocked `ctx.elicit` accept/decline/cancel paths |
| Prompt outputs | 3 | `inline-snapshot` capture |
| Timeouts | 3 | Force slow mock, assert MCP error |
| Native OTEL | 3 | `InMemorySpanExporter` captures `tools/call {name}` spans |
| `task=True` | 5 | Task ID returned, polling returns progress + result |

### 10.2 Parity test pattern (Phase 1)

```python
@pytest.mark.parametrize(
    "manager_call, dispatcher_call",
    [
        (("tracks_list", {"filters": {"bpm__gte": 120}}),
         ("entity_list", {"entity": "track", "filters": {"bpm__gte": 120}})),
        (("sets_get", {"id": 25}),
         ("entity_get", {"entity": "set", "id": 25})),
        # ... every manager
    ],
)
async def test_manager_parity(mcp_client, seeded_db, manager_call, dispatcher_call):
    manager_result = await mcp_client.call_tool(*manager_call)
    dispatcher_result = await mcp_client.call_tool(*dispatcher_call)
    assert manager_result.structured_content == dispatcher_result.structured_content
```

### 10.3 Elicitation mock pattern (Phase 2)

```python
async def test_sets_deliver_hard_conflict_continue(mcp_server, ...):
    mock_elicit_accept("continue")
    result = await mcp_server.call_tool("sets_deliver", {"set_id": 42})
    assert result.structured_content["hard_conflicts_resolved"] == "continue"
    assert len(result.structured_content["exports"]) == 3  # m3u8, xml, json
```

### 10.4 Snapshot pattern for prompts

```python
async def test_deliver_set_workflow_output(mcp_client):
    result = await mcp_client.get_prompt("deliver_set_workflow", {"set_id": 42})
    assert result.messages[0].content == snapshot()  # inline-snapshot fills on --snapshot-update
```

---

## 11. Import-linter contracts

Blueprint v1 §16 defines 9 contracts. This spec **adds one and updates one**:

**Updated `tools-thin`:** `app/tools/domain/*` CAN import `app/repositories/*` and `app/providers/*` when they are composite tools (e.g. `sets_deliver` needs provider for YM sync, uses repo via UoW). Contract allows this explicitly.

```ini
[importlinter:contract:tools-thin]
name = Tools may call handlers, repos, providers, domain; NOT audio
type = forbidden
source_modules =
    app.tools
forbidden_modules =
    app.audio
```

**New `surface-passes-through`:** the facade layer (`app/server/surface.py`) must not contain business logic — only `ToolTransformConfig`s.

```ini
[importlinter:contract:surface-declarative]
name = app/server/surface.py is declarative — no repos, models, providers
type = forbidden
source_modules =
    app.server.surface
forbidden_modules =
    app.repositories
    app.models
    app.providers
    app.audio
    app.domain
```

Total: 10 contracts.

---

## 12. Risks and open questions

### 12.1 Risks

| Risk | Mitigation |
|---|---|
| `ToolTransform` one-to-many mapping (one `entity_list` → N managers) breaks | Multiple separate `ToolTransform({...})` instances, one per manager (§5.2). Tested Phase 1. |
| v1 dispatchers disappearing from BM25 search if tagged `internal` | Use `Visibility` filter order carefully; confirm with v3 docs that disabled tools are excluded from search (per docs they are). Alternative: keep a distinct `deprecated` tag that stays in search. Decide Phase 1 implementation. |
| `DeprecationWarningMiddleware` produces noise before Phase 4 panel migration | Only log at DEBUG until Phase 3 completes; promote to WARN after. |
| `sets_deliver` elicitation — client support | FastMCP Client supports elicitation. Non-FastMCP clients must handle via spec (MCP 2025-06-18). If client lacks support, tool errors gracefully — document in tool description. |
| Classifier wiring increases `tracks_analyze` latency (+~50ms per track) | Classifier is fast (pure math, no I/O). Benchmark in Phase 2; if >10% regression vs blueprint v1 budget, make classifier optional via level param. |
| `task=True` requires async function | `tracks_analyze_bg` already async. OK. |
| Redis backend adds ops complexity | Default stays `memory://`. Prod adopts Redis only when L5 sweeps need horizontal scaling. |
| Panel regressions during Phase 4 | Backend stays backward-compat (v1 dispatchers still callable), so panel can incrementally migrate file-by-file. |

### 12.2 Open questions

| # | Question | Resolution |
|---|---|---|
| Q1 | Namespace `playlists:write` vs separate `playlists:distribute` namespace? | Merge into `playlists:write` (simplest). If distribute becomes a separate risk class, split later. |
| Q2 | Should `transitions_score` accept either `track_ids` (new orchestration-oriented) or `from_track_id+to_track_id` (pairwise)? | Phase 1: accept `track_ids` list. Pairwise already served by `local://transition/{a}/{b}/score` resource. |
| Q3 | `tracks_analyze` at level=5 should auto-route to `tracks_analyze_bg`? | Out of scope for Phase 1-4. Revisit Phase 5 — possibly route automatically based on `len(track_ids) * level >= threshold`. |
| Q4 | `sets_deliver` should generate cheatsheet inline or leave as separate resource read? | Phase 2 decision. Leaning toward inline (one-stop-shop), but resource still available. |
| Q5 | Version tags on 6 prompts too? | No — prompts with breaking changes would cause LLM confusion. Prompts stay unversioned. Rewrite in place in Phase 3. |
| Q6 | Expose raw dispatchers via search AT ALL, or remove completely from discovery? | Phase 7 decides after deprecation window. Initial: keep searchable tagged `deprecated`; after sunset, remove. |
| Q7 | `MoodClassifier` input changes? | Current classifier accepts `TrackFeatures`. L2 features include BPM/LUFS/energy/spectral/HP_ratio/kick — verify classifier's 6-8 weights match what L2 actually produces. Phase 2 unit tests. |

### 12.3 What this spec does NOT address

- **Runtime fix (G9)** — user-driven; `exit && claude` + cache cleanup.
- **Panel rewrite details** — Phase 4 contract only (tool name migration); deeper panel redesign (component composition, Supabase query shapes) = separate panel-dedicated spec.
- **VM campaign scripts (G6)** — Phase 5 offers `task=True` as replacement; actual script revival is out of scope unless user requests.
- **RLS / authentication (G4)** — separate future spec.
- **L3/L4 data gap (G5)** — data, not design. Close via normal `tracks_analyze(level=5)` or `tracks_analyze_bg` sweep.
- **15 dead DB tables (blueprint v1 D16 reversed)** — per CONTINUE.md, keep. No migration.
- **FastMCP 3.x upgrade path beyond current 3.1** — assume current major.

---

## 13. Relationship to Blueprint v1 (compatibility map)

This spec is **additive**. Blueprint v1 sections remain authoritative except where explicitly overridden:

| Blueprint v1 section | This spec updates | Direction |
|---|---|---|
| §3 Canonical layout | Adds `app/server/surface.py`, `app/tools/domain/`, `app/domain/delivery/` | ADD |
| §5 EntityRegistry | Handlers for `track_features` now depend on classifier | MODIFY |
| §7 Tool Catalog | 13 → 13 (raw, tag=`internal`) + 12 managers + 2 background tools (Phase 5) + 4 CodeMode meta (Phase 6 flag) | ADD/TAG |
| §8 Resource Catalog | unchanged | — |
| §9 Prompt Catalog | `deliver_set_workflow`, `full_pipeline` rewritten | MODIFY |
| §11 Middleware | Row 3 (OTEL) dropped, row 13 (timeout) dropped, row 15 (DbSession) possibly replaced with DI | REDUCE |
| §12 FastMCP v3 | `task=True` moved from deferred → Phase 5; `CodeMode` from flag → Phase 6 | ADOPT |
| §13 Deletions | 15 DB tables no longer dropped (D13 in this spec) | REVERSE |
| §16 Import-linter | +1 contract, 1 modified | ADD |

---

## 14. Migration of v1 tool callers

External callers of v1 dispatchers (panel, any user script, third-party MCP client) keep working through deprecation:

```python
# Old
await client.call_tool("entity_list", {"entity": "track", "filters": {...}})

# New (Phase 1+)
await client.call_tool("tracks_list", {"filters": {...}})

# Old still works (via BM25 search_tools + call_tool, or direct name):
await client.call_tool("entity_list", {"entity": "track", "filters": {...}})
# DeprecationWarningMiddleware logs; no behavior change.
```

Scripts + panel migrate in Phase 4. After Phase 7, v1 names return `NotFoundError`.

---

## 15. Success metrics

After Phase 1-4 complete:

- `tracks_list(filters={"bpm__gte": 120})` works from Claude Code, panel, and REST API.
- `sets_deliver(set_id=42)` end-to-end produces M3U8 + XML + JSON + copies MP3 files; elicits user on hard conflicts.
- `playlists_distribute(source_playlist_id=N)` classifies + distributes without manual `classify_mood` call first.
- Panel dashboards render using new tool names; no 0.7.1 references remain.
- BM25 search: `search_tools("analyze a track")` → `tracks_analyze` as top hit.
- `make check` passes. Import-linter clean. Parity tests 100%.

After Phase 5-6:

- `tracks_analyze_bg(level=5)` runs in background; no client timeout.
- `DJ_MCP_CODE_MODE=1` enables experimental pipeline orchestration.

After Phase 7:

- Registry contains 12 managers + 2 background + 4 CodeMode meta + 2 BM25 + `unlock_namespace`. v1 dispatchers gone.

---

## 16. Post-approval actions

1. User signs off this spec.
2. Merge this spec to `dev` as single commit.
3. Archive blueprint v1 §7, §9 overrides into this spec (cross-link, don't rewrite).
4. Invoke `superpowers:writing-plans` skill to produce implementation plan for Phase 1.
5. Phase 2-7 plans on completion of prior phase.

---

## Appendix A — File manifest

**New files (Phase 1-7 total):**

```text
app/server/surface.py                  # Phase 1: domain manager configs
app/tools/domain/__init__.py           # Phase 1: package marker
app/tools/domain/sets_deliver.py       # Phase 2: G1 fix
app/tools/domain/playlists_distribute.py  # Phase 2: G2 fix
app/tools/domain/transitions_score.py  # Phase 1: composite
app/tools/domain/tracks_analyze_bg.py  # Phase 5: task=True wrapper
app/domain/delivery/__init__.py        # Phase 2: port writers
app/domain/delivery/m3u8.py
app/domain/delivery/rekordbox.py
app/domain/delivery/json_guide.py
app/domain/delivery/cheatsheet.py
app/domain/delivery/mp3_copy.py
tests/test_server/test_surface.py      # Phase 1: manager tests
tests/test_tools/domain/test_sets_deliver.py    # Phase 2
tests/test_tools/domain/test_playlists_distribute.py  # Phase 2
tests/test_handlers/test_classifier_wiring.py   # Phase 2
```

**Modified files:**

```sql
app/server/app.py                      # Phase 1: register_managers(), disable(internal)
app/handlers/track_features_analyze.py # Phase 2: classifier injection
app/handlers/track_features_reanalyze.py  # Phase 2: classifier injection
app/repositories/track_features.py     # Phase 2: update_mood method
app/server/di.py                       # Phase 2: get_mood_classifier
app/server/lifespan.py                 # Phase 2: classifier singleton
app/prompts/deliver_set_workflow.py    # Phase 3: rewrite to sets_deliver
app/prompts/full_pipeline.py           # Phase 3: delivery step
app/config/mcp.py                      # Phase 6: mcp_code_mode_enabled
app/tools/compute/score_pool.py        # Phase 3: timeout=60
app/tools/compute/sequence_optimize.py # Phase 3: timeout=300
.importlinter                          # Phase 1: +1 contract
docs/tool-catalog.md                   # Phase 1: update catalog
CHANGELOG.md                           # per phase
```

**Deleted files:**

```bash
app/server/middleware/otel_tracing.py  # Phase 3 if exists
```

---

## Appendix B — Sign-off checklist

Before beginning Phase 1 implementation:

- [ ] User has read this spec end-to-end.
- [ ] Open questions §12.2 resolved or explicitly deferred.
- [ ] Runtime fix (Phase 0a) executed; v1 dispatchers callable.
- [ ] This spec committed to `dev` as single commit.
- [ ] `writing-plans` skill invoked for Phase 1.

Sign-off: _______________________________________

Date: ________________

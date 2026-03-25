# DJ Music Plugin — Architecture & Design Specification

> Design document for a FastMCP v3 server managing a personal DJ techno music library,
> building optimized DJ sets, and integrating with Yandex Music.
>
> Based on REQUIREMENTS.md. This document covers architecture decisions, component design,
> and implementation patterns. It does NOT duplicate the domain model or data schemas
> already defined in REQUIREMENTS.md.

---

## 1. System Overview

### 1.1 What This Is

A standalone MCP server (Python 3.12+, FastMCP v3) that exposes all DJ workflow
functionality through the Model Context Protocol. No REST API, no CLI, no web UI.

### 1.2 Key Architectural Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| MCP Framework | FastMCP v3.1 | Provider/Transform architecture, DI, visibility, OTEL |
| DB ORM | SQLAlchemy 2.0 async | Dual SQLite/PostgreSQL, mapped_column style |
| Migrations | Alembic | 44 tables need managed schema evolution |
| Audio | librosa (optional) + numpy | Core analyzers pure Python, librosa for beat/key/MFCC |
| HTTP Client | httpx async | For Yandex Music API |
| Validation | Pydantic v2 | Strict typing, structured output for MCP |
| Testing | pytest + FastMCP Client | In-memory MCP calls, in-memory SQLite |

### 1.3 Decomposition into Sub-Projects

The system is too large for a single implementation cycle. Each sub-project gets
its own plan → implementation → test cycle:

| # | Sub-Project | Depends On | Scope |
|---|------------|-----------|-------|
| 1 | **Foundation** — models, DB, repositories, services | — | 44 tables, base patterns |
| 2 | **MCP Server skeleton** — FastMCP setup, DI, lifespan, CRUD + search + admin tools | #1 | Server + 23 core tools |
| 3 | **Yandex Music Client** — async HTTP client, all API operations | — | Standalone client |
| 4 | **Audio Analysis Pipeline** — analyzers, pipeline, mood classifier | #1 | 10 analyzers + classifier |
| 5 | **Transition Scoring & Camelot** — scoring formula, key system | #1, #4 | Scoring engine |
| 6 | **Set Generation** — GA optimizer, greedy builder, templates | #1, #5 | Optimization engine |
| 7 | **MCP Tools (extended)** — delivery, discovery, curation, sync, YM, audio tools | #1-#6 | 21 extended + hidden tools |
| 8 | **Delivery & Export** — M3U8, Rekordbox XML, JSON guide, YM sync, AppExport records | #1, #3, #6 | Export pipeline |

---

## 2. FastMCP v3 Server Architecture

### 2.1 Server Configuration

```python
import os

mcp = FastMCP(
    name="DJ Music",
    instructions="DJ techno music library management, set building, and YM integration",
    list_page_size=50,
    on_duplicate="error",
    lifespan=db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan,
    sampling_handler=AnthropicSamplingHandler(
        api_key=settings.anthropic_api_key,
        model="claude-sonnet-4-5",
    ),
    sampling_handler_behavior="fallback",
)

# Background tasks configuration (via environment)
os.environ.setdefault("FASTMCP_DOCKET_URL", settings.docket_url)
os.environ.setdefault("FASTMCP_DOCKET_CONCURRENCY", str(settings.docket_concurrency))
```

### 2.2 Composable Lifespans

Four lifespans composed with `|` operator. Enter left-to-right, exit right-to-left.

```text
db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan
```

| Lifespan | Yields | Purpose |
|----------|--------|---------|
| `db_lifespan` | `db_engine`, `db_session_factory` | SQLAlchemy async engine + session maker |
| `ym_lifespan` | `ym_client` | YandexMusicClient with rate limiting |
| `analyzer_lifespan` | `analyzer_registry` | Plugin registry of audio analyzers |
| `cache_lifespan` | `transition_cache` | In-memory LRU cache for transition scores |

Each uses `@lifespan` decorator with `try/finally` for cleanup.

### 2.3 Provider Architecture

Single `FileSystemProvider` with hot reload in dev:

```text
app/mcp/
├── tools/
│   ├── crud.py          # list_tracks, get_track, manage_tracks, etc.
│   ├── search.py        # search, filter_tracks
│   ├── sets.py          # build_set, rebuild_set, score_transitions, get_set_cheat_sheet
│   ├── reasoning.py     # suggest_next_track, explain_transition, find_replacement,
│   │                    #   compare_set_versions, quick_set_review
│   ├── delivery.py      # deliver_set, export_set
│   ├── discovery.py     # find_similar_tracks, import_tracks, download_tracks
│   ├── curation.py      # classify_mood, audit_playlist, review_set_quality,
│   │                    #   distribute_to_subgenres, get_library_stats
│   ├── sync.py          # sync_playlist, push_set_to_ym
│   ├── ym.py            # ym_search, ym_get_tracks, ym_get_album,
│   │                    #   ym_artist_tracks, ym_playlists, ym_likes
│   ├── audio.py         # analyze_track, analyze_batch, separate_stems
│   └── admin.py         # unlock_tools, list_platforms
├── resources/
│   ├── status.py        # status://library, status://platforms
│   ├── templates.py     # set://{id}/summary, track://{id}/features,
│   │                    #   playlist://{id}/status, catalog://stats{?mood,bpm}
│   └── reference.py     # reference://camelot, reference://templates,
│                        #   reference://subgenres
└── prompts/
    └── workflows.py     # build_set_workflow, expand_playlist_workflow,
                         #   improve_set_workflow, deliver_set_workflow,
                         #   full_expansion_pipeline
```

Tools are auto-discovered via `@tool`, `@resource`, `@prompt` decorators.
No manual registration needed.

### 2.4 Transform Pipeline

```python
mcp.add_transform(ResourcesAsTools(mcp))    # resources → tools for tool-only clients
mcp.add_transform(PromptsAsTools(mcp))      # prompts → tools for tool-only clients
mcp.disable(tags={"audio"})                 # hidden at startup
```

### 2.5 Middleware Pipeline

Order: outermost (first added) → innermost (last added).

| Middleware | Purpose | Config |
|-----------|---------|--------|
| `StructuredLoggingMiddleware` | JSON request/response logs | — |
| `DetailedTimingMiddleware` | Per-tool execution timing | — |
| `RateLimitingMiddleware` | Global rate limiting | 10 req/s, burst 20 |
| `ResponseLimitingMiddleware` | Truncate huge responses | max 50KB |
| `PingMiddleware` | Keep long-lived connections alive | 30s interval |
| `YMRateLimitMiddleware` (custom) | YM API rate limiting | 1.5s between YM calls |

### 2.6 Transport

Primary: **stdio** (Claude Code integration).
Future: **streamable-http** for remote access (FastMCP default HTTP transport).

---

## 3. Dependency Injection

### 3.1 DI Chain

```text
get_db_session() ← async context manager, auto-commit/rollback
  ├── get_track_repo(session)
  │     └── get_track_service(track_repo)
  ├── get_set_repo(session)
  │     └── get_set_service(set_repo, track_repo)
  ├── get_playlist_repo(session)
  ├── get_transition_scorer(session, cache)
  └── get_feature_repo(session)

get_ym_client() ← from lifespan context
get_analyzer_registry() ← from lifespan context
get_transition_cache() ← from lifespan context
```

### 3.2 Key Pattern: Per-Request Session Caching

FastMCP's `Depends()` caches per-request. Multiple repos depending on
`get_db_session` receive the **same session instance**, guaranteeing
a single transaction per tool call.

```python
@asynccontextmanager
async def get_db_session():
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 3.3 Service Layer

- **Repositories**: data access only, flush but never commit
- **Services**: business logic, orchestration
- **Tools**: thin wrappers calling services, handling MCP concerns (progress, elicitation)

---

## 4. Tool Design

### 4.1 Summary Table

| Category | Tools | Tags | Visibility | Description | Background Tasks |
|----------|-------|------|-----------|-------------|-----------------|
| CRUD | 10 | `core` | Always visible | Tracks, playlists, sets, features | No |
| Search | 2 | `core` | Always visible | Universal search, parametric filter | No |
| Set Building | 5 | `sets` | Always visible | Build, rebuild, score, cheat sheet, **background scoring** | 1 optional |
| Set Reasoning | 5 | `sets` | Always visible | Suggest, explain, replace, compare, quick review | No |
| Delivery & Export | 2 | `delivery` | Extended | Deliver pipeline, export formats | No |
| Discovery | 3 | `discovery` | Extended | Find similar, **import+auto-analyze**, download | **import triggers tasks** |
| Curation | 5 | `curation` | Extended | Classify, audit, review, distribute, stats | No |
| Sync | 2 | `sync` | Extended | Bidirectional sync, push to YM | No |
| YM API | 6 | `ym` | Extended | Search, tracks, albums, artists, playlists, likes | No |
| Audio | 3 | `audio` | **Hidden** | **Analyze (optional), batch (optional), stems (required)** | **3 task-enabled** |
| Admin | 2 | `admin` | Always visible | Unlock tools, list platforms | No |
| **Total** | **45** | | | | **5 background-capable** |

At session start: **23 core tools** visible (~5K tokens in schemas).
Extended unlocked via `unlock_tools` or auto-unlock on first reference.
Audio requires explicit unlock.

### 4.2 Entity Resolution Pattern

Tools use **explicit typed parameters** instead of a single `ref: str`:

```python
async def get_track(
    id: int | None = None,       # exact ID
    query: str | None = None,    # text search
    ym_id: str | None = None,    # YM track ID
) -> TrackFull:
```

When `query` matches multiple tracks:
1. Try elicitation (show top-5 matches, let user pick)
2. Fallback: return best match + alternatives in `meta`

Reusable `EntityResolver` class handles this for all entity types.

### 4.3 Progressive Disclosure for Return Types

Tools support `view` parameter to control response size:

| View | ~Tokens | Content |
|------|---------|---------|
| `summary` | 100-300 | IDs, names, counts, scores |
| `tracks` | 1,000-1,500 | + ordered track list (brief) |
| `transitions` | 2,500-3,500 | + transition scores between pairs |
| `full` | 5,000-8,000 | + all audio features per track |

Default is always the lightest useful view.

### 4.4 Pagination

All list tools use cursor-based pagination:

```python
class PaginatedResult(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
    total: int
```

Default `limit=20`, max `limit=100`.

### 4.5 Tool Annotations

Every tool gets MCP annotations:

| Annotation | Tools |
|-----------|-------|
| `readOnlyHint=True` | All list/get/search/filter/review/stats tools |
| `destructiveHint=True` | deliver_set (writes files), manage_set(delete) |
| `idempotentHint=True` | import_tracks, archive/unarchive, analyze_track |
| `openWorldHint=True` | All YM tools, find_similar, download, sync |

### 4.6 Consolidated vs Dedicated Tools

**Rule**: consolidate only operations on **one entity type**.

- `manage_tracks(action=create|update|archive)` — one entity, rare ops
- `ym_playlists(action=get|list|create|rename|delete|add_tracks|remove_tracks)` — one entity, API wrapper
- NOT: `ym_all(action=search_tracks|get_album|artist_tracks)` — different entities

### 4.7 DJ-Specific Reasoning Tools

Five tools that turn the server from "CRUD wrapper" into "DJ assistant":

| Tool | What It Does | Why It Matters |
|------|-------------|---------------|
| `suggest_next_track` | Best tracks for a position, scored against BOTH neighbors | Natural DJ question: "what goes here?" |
| `explain_transition` | 5-component breakdown + human-readable reasoning | Claude can explain WHY to the user |
| `find_replacement` | Replacement candidates with combined neighbor scores | 1 call vs 5+ manual calls |
| `compare_set_versions` | Diff: tracks added/removed, scores improved/worsened | "Did rebuild make it better?" |
| `quick_set_review` | Complete review in one call (~1.5K tokens) | Replaces 3 separate calls (~10K tokens) |

### 4.8 Error Handling

#### Error Hierarchy (`app/core/errors.py`)

```text
DJMusicError (base)
├── NotFoundError            → ToolError "Entity not found"
├── ValidationError          → ToolError with details
├── ConflictError            → ToolError "Duplicate / version mismatch"
├── PipelineError
│   ├── AnalyzerUnavailableError  → ToolError "Install librosa"
│   └── AnalysisTimeoutError      → ToolError "Timeout after Ns"
├── YandexMusicError
│   ├── RateLimitedError     → retry hint in message
│   ├── AuthFailedError      → ToolError "Check YM token"
│   └── APIError             → masked in prod
└── ExportError              → ToolError with path details
```

#### Three levels of surface exposure

| Level | Mechanism | When |
|-------|----------|------|
| Input validation | `ToolError` | Bad params — Claude sees message, can fix |
| Domain error | `ToolResult` with warning in `meta` | Partial success — Claude sees what worked |
| Infrastructure | Masked error (`mask_error_details=True`) | DB/network failures — generic message |

### 4.9 Timeouts

| Tool | Timeout | Why |
|------|---------|-----|
| `build_set` | 120s | GA optimization |
| `analyze_track` | 120s | Audio processing |
| `analyze_batch` | 600s | Multiple tracks |
| `separate_stems` | 300s | ML model |
| `deliver_set` | 300s | File I/O + optional YM sync |
| `download_tracks` | 300s | Network I/O |
| All others | default (no limit) | Fast operations |

---

## 5. Resources

### 5.1 Static Resources (2)

| URI | Purpose | Tags |
|-----|---------|------|
| `status://library` | Library health: counts, coverage, health indicator | `core` |
| `status://platforms` | Connected platforms + linked track counts | `core` |

### 5.2 Template Resources (3)

| URI | Parameters | Purpose |
|-----|-----------|---------|
| `track://{track_id}/features` | track_id: int | Audio features summary |
| `set://{set_id}/summary` | set_id: int | Latest version: ID, score, label, track count, problems |
| `playlist://{playlist_id}/status` | playlist_id: int | Track count, source, last sync |

### 5.3 Parametric Resources (1)

| URI | Query Params | Purpose |
|-----|-------------|---------|
| `catalog://stats{?mood,bpm_min,bpm_max}` | mood, bpm_min, bpm_max | Filtered catalog statistics |

### 5.4 Reference Resources (3)

| URI | Purpose |
|-----|---------|
| `reference://camelot` | 24 Camelot keys with compatibility rules |
| `reference://templates` | 8 DJ set templates with slot definitions |
| `reference://subgenres` | 15 techno subgenres with descriptions and energy order |

These are **browsable context** for Claude — loaded on demand, not hardcoded.

`ResourcesAsTools` transform makes all resources callable for tool-only clients.

---

## 6. Workflow Prompts

Five multi-turn prompt templates guiding Claude through complex operations:

| Prompt | Parameters | Steps |
|--------|-----------|-------|
| `build_set_workflow` | playlist_name, template, duration_min | Get playlist → Audit → Fill gaps → Build → Review → Fix → Deliver |
| `expand_playlist_workflow` | playlist_name, target_count | Audit → Find similar → Import → Download → Analyze → Re-audit |
| `improve_set_workflow` | set_name | Review → Explain weak transitions → Find replacements → Rebuild → Compare |
| `deliver_set_workflow` | set_name, sync_ym | Score → Handle conflicts → Export → Copy files → YM sync |
| `full_expansion_pipeline` | source_playlist, target_per_subgenre | Audit → Discover → Import → Download → Analyze → Classify → Distribute |

Each returns `list[Message]` with user instructions + assistant acknowledgment.

`PromptsAsTools` transform makes prompts invocable as tools.

---

## 7. Elicitation Points

Five places where tools pause for user decisions:

| Tool | Trigger | Schema |
|------|---------|--------|
| `deliver_set` | Hard conflicts found (score=0.0) | `Literal["continue", "skip_conflicts", "abort"]` |
| `deliver_set` | YM playlist already exists | `Literal["overwrite", "append", "create_new", "cancel"]` |
| `sync_playlist` | Track deleted on one side | `bool` (keep locally?) per conflict |
| `distribute_to_subgenres` | `mode="clean_rebuild"` | `bool` confirmation |
| Entity resolution | Ambiguous text search | `Literal[top-5 match titles]` |

All use `safe_elicit()` wrapper that falls back gracefully when client
doesn't support elicitation.

---

## 8. Sampling Points

Two tools use LLM sampling via `ctx.sample()`:

| Tool | When | Prompt Purpose |
|------|------|---------------|
| `find_similar_tracks` | `strategy="llm"` or `"combined"` | Generate search queries based on track characteristics |
| Future: `smart_set_notes` | After set build | Generate DJ transition notes |

Sampling uses `result_type` for structured output (Pydantic models).

Fallback: `AnthropicSamplingHandler` when client doesn't support sampling.

---

## 9. Visibility System

### 9.1 Three Tiers

| Tier | Tags | Behavior | Tools |
|------|------|----------|-------|
| **Core** | `core`, `sets`, `admin` | Always visible | 23 tools |
| **Extended** | `delivery`, `discovery`, `curation`, `sync`, `ym` | Auto-unlock on need | 18 tools |
| **Hidden** | `audio` | Explicit unlock required | 3 tools |

### 9.2 Unlock Mechanism

```python
@tool(tags={"admin"})
async def unlock_tools(
    action: Literal["unlock", "lock", "status"],
    category: Literal["delivery", "discovery", "curation", "sync",
                       "ym", "audio", "all"] | None = None,
    ctx: Context = CurrentContext(),
) -> dict:
```

Session-scoped: each session manages its own visibility.
`ToolListChangedNotification` sent automatically on change.

---

## 10. Delivery, Export & Download Details

### 10.1 AppExport Entity

Every export operation creates an `AppExport` record in DB:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | int (PK) | Auto-increment |
| `target_app` | enum: traktor, rekordbox, djay, generic | Target DJ app |
| `export_format` | enum: m3u8, rekordbox_xml, json_guide, cheat_sheet | File format |
| `playlist_id` | FK → dj_playlists | Source playlist/set |
| `file_path` | str | Path to exported file |
| `file_size` | int | File size in bytes |
| `created_at` | datetime | Export timestamp |

Model in `app/models/export.py`, repository in `app/repositories/export.py`.

### 10.2 Rekordbox XML Format

Exported XML follows Rekordbox DJ XML format:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="DJ Music Plugin" Version="1.0"/>
  <COLLECTION Entries="N">
    <TRACK TrackID="..." Name="..." Artist="..." TotalTime="..."
           AverageBpm="..." Tonality="..." Location="file://...">
      <TEMPO Inizio="..." Bpm="..." Battito="..."/>  <!-- if beatgrid -->
      <POSITION_MARK Name="..." Type="..." Start="..."/>  <!-- if cues -->
      <!-- Saved loops as POSITION_MARK with End attribute -->
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="Root">
      <NODE Type="1" Name="Set Name" Entries="N">
        <TRACK Key="..."/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
```

Configurable inclusion via `RekordboxOptions`:
- `include_cue_points: bool = True`
- `include_saved_loops: bool = True`
- `include_beatgrid: bool = True`
- `include_sections: bool = False` (sections as position marks)

### 10.3 Download & iCloud Handling

**Download path resolution:**
1. Use `DJ_YM_LIBRARY_PATH` env var (e.g., `~/Music/Music/Media.localized/`)
2. Organize as `{library_path}/YM Downloads/{Artist} - {Title}.mp3`
3. Sanitize filenames (remove `/`, `\`, `:`, `*`, etc.)

**iCloud stub detection** (REQUIREMENTS section 8, item 4):
```python
async def is_icloud_stub(path: Path) -> bool:
    """File is an iCloud placeholder if actual blocks < 90% of reported size."""
    stat = path.stat()
    blocks_bytes = stat.st_blocks * 512
    return blocks_bytes < stat.st_size * 0.9
```

When delivering a set, iCloud stubs are:
- Skipped during MP3 copy
- Referenced by original path in M3U8
- Logged via `ctx.warning(f"iCloud stub: {path.name}")`

### 10.4 Sync Strategy

**Source of truth** (per playlist, field `source_of_truth`):
- `"local"` — local DB is authoritative, push changes to platform
- `"yandex"` — YM is authoritative, pull changes to local

**Pull from YM:**
1. Fetch YM playlist tracks via API
2. Compare with local playlist items
3. New tracks on YM → create local track + link to YM ID
4. Deleted tracks on YM → mark `pending_review` (soft delete), NOT auto-delete

**Push to YM:**
1. Compare local playlist with YM version
2. New local tracks with YM IDs → add to YM playlist
3. Removed local tracks → remove from YM playlist
4. Re-fetch YM playlist for fresh revision/indices after each modification

**Conflict resolution:**
- Source-of-truth wins by default
- When `conflict_strategy="ask"`: elicitation for each conflict
- When a track exists in a DJ set but was deleted: always ask via elicitation
- Metadata conflicts (title change, etc.): source-of-truth wins silently

---

## 11. Observability

### 11.1 Logging

- `StructuredLoggingMiddleware` for all MCP requests
- `ctx.info()` / `ctx.debug()` for tool-level progress
- `ctx.warning()` for non-fatal issues (missing features, iCloud stubs)
- `ctx.error()` for recoverable failures

### 11.2 OpenTelemetry

Zero-config auto-instrumentation via `opentelemetry-instrument`:

```bash
opentelemetry-instrument \
  --service_name dj-music \
  --exporter_otlp_endpoint http://localhost:4317 \
  fastmcp run app/server.py
```

Custom spans in heavy tools (`build_set`, `analyze_batch`, `deliver_set`)
for sub-operation visibility.

### 11.3 Optional Sentry

Sentry SDK integration for error tracking in production.
Configured via `SENTRY_DSN` environment variable.

---

## 12. Improvements Over REQUIREMENTS.md

Features added beyond the original spec:

| Improvement | Description |
|------------|-------------|
| **Event-driven pipeline** | Import → auto-analyze → auto-classify (future) |
| **Smart analysis queue** | Prioritize tracks in active sets |
| **Incremental transition scoring** | Recompute only affected pairs on track change |
| **Transition cache** | LRU cache with invalidation on feature change |
| **Sync conflict resolution** | Source-of-truth wins + soft delete + elicitation |
| **Visibility tiers** | 3-level tool visibility with per-session control |
| **Dry-run mode** | `dry_run=True` on destructive operations |
| **Progressive disclosure** | `view` parameter controls response size |
| **DJ reasoning tools** | 5 tools: suggest, explain, replace, compare, quick review |
| **Structured logging** | JSON logs + correlation via OTEL trace IDs |
| **Analyzer plugin system** | Registry pattern for extensible audio analyzers |
| **Component versioning** | FastMCP v3 versioning for future API evolution |

---

## 13. Project Structure

```bash
dj-music-plugin/
├── app/
│   ├── __init__.py
│   ├── config.py              # pydantic-settings, env vars
│   ├── server.py              # FastMCP instance, lifespan, middleware
│   ├── models/                # SQLAlchemy models (44 tables)
│   │   ├── __init__.py
│   │   ├── base.py            # DeclarativeBase, mixins
│   │   ├── track.py           # Track, Artist, Genre, Label, Release
│   │   ├── audio.py           # AudioFeatures, Section, Embedding, Timeseries
│   │   ├── library.py         # LibraryItem, Beatgrid, CuePoint, SavedLoop
│   │   ├── playlist.py        # Playlist, PlaylistItem
│   │   ├── set.py             # Set, SetVersion, SetItem, Constraint, Feedback
│   │   ├── transition.py      # Transition, TransitionCandidate
│   │   ├── key.py             # Key, KeyEdge (Camelot wheel)
│   │   ├── platform.py        # YandexMetadata, SpotifyMetadata, etc.
│   │   ├── ingestion.py       # Provider, ProviderTrackId, RawResponse
│   │   └── export.py          # AppExport
│   ├── repositories/          # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py            # BaseRepository with CRUD + pagination
│   │   ├── track.py
│   │   ├── playlist.py
│   │   ├── set.py
│   │   ├── feature.py
│   │   └── transition.py
│   ├── services/              # Business logic layer
│   │   ├── __init__.py
│   │   ├── track.py
│   │   ├── playlist.py
│   │   ├── set.py
│   │   ├── transition.py      # TransitionScorer
│   │   ├── optimizer.py       # GeneticAlgorithm, GreedyChainBuilder
│   │   ├── mood.py            # MoodClassifier (15 subgenres)
│   │   └── export.py          # M3U8, Rekordbox, JSON guide writers
│   ├── audio/                 # Audio analysis
│   │   ├── __init__.py
│   │   ├── registry.py        # AnalyzerRegistry (plugin pattern)
│   │   ├── pipeline.py        # AnalysisPipeline
│   │   ├── analyzers/
│   │   │   ├── bpm.py
│   │   │   ├── key.py
│   │   │   ├── loudness.py
│   │   │   ├── energy.py
│   │   │   ├── spectral.py
│   │   │   ├── beat.py        # requires librosa
│   │   │   ├── groove.py
│   │   │   ├── structure.py
│   │   │   ├── mfcc.py        # requires librosa
│   │   │   └── stems.py       # requires demucs
│   │   └── timeseries.py      # NPZ storage for frame-level data
│   ├── ym/                    # Yandex Music client
│   │   ├── __init__.py
│   │   ├── client.py          # YandexMusicClient (async httpx)
│   │   ├── models.py          # YM response models
│   │   └── rate_limiter.py    # Token bucket + exponential backoff
│   ├── mcp/                   # MCP components (auto-discovered)
│   │   ├── tools/
│   │   │   ├── crud.py
│   │   │   ├── search.py
│   │   │   ├── sets.py
│   │   │   ├── reasoning.py
│   │   │   ├── delivery.py
│   │   │   ├── discovery.py
│   │   │   ├── curation.py
│   │   │   ├── sync.py
│   │   │   ├── ym.py
│   │   │   ├── audio.py
│   │   │   └── admin.py
│   │   ├── resources/
│   │   │   ├── status.py
│   │   │   ├── templates.py
│   │   │   └── reference.py
│   │   ├── prompts/
│   │   │   └── workflows.py
│   │   └── dependencies.py    # Depends factories: get_db_session, etc.
│   ├── core/                  # Shared utilities
│   │   ├── __init__.py
│   │   ├── constants.py       # Enums, Camelot keys, domain constants
│   │   ├── errors.py          # DJMusicError hierarchy
│   │   ├── pagination.py      # CursorPagination
│   │   ├── entity_resolver.py # EntityResolver (flexible refs)
│   │   ├── camelot.py         # Camelot wheel distance/compatibility logic
│   │   └── schemas.py         # Shared Pydantic response models
│   └── migrations/            # Alembic
│       ├── env.py
│       └── versions/
├── tests/
│   ├── conftest.py            # Fixtures: client, seeded_db, synthetic_audio
│   ├── test_models/
│   ├── test_repositories/
│   ├── test_services/
│   ├── test_audio/
│   ├── test_ym/
│   ├── test_tools/            # MCP tool integration tests
│   │   ├── test_crud.py
│   │   ├── test_sets.py
│   │   ├── test_reasoning.py
│   │   └── ...
│   ├── test_resources/
│   └── test_prompts/
├── pyproject.toml
├── alembic.ini
├── .env.example
├── REQUIREMENTS.md
├── CLAUDE.md
└── docs/
    └── superpowers/
        └── specs/
            └── this file
```

---

## 14. Configuration

All via environment variables (pydantic-settings). **No magic numbers in code** — every
tunable value lives in `app/config.py` as a typed, documented, env-overridable field.

### 14.1 Settings Class

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DJ_", env_file=".env")

    # ── Database ──────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///dj_music.db"

    # ── Yandex Music ──────────────────────────────────
    ym_token: str = ""
    ym_user_id: str = ""
    ym_base_url: str = "https://api.music.yandex.net"
    ym_library_path: str = ""
    ym_rate_limit_delay: float = 1.5        # seconds between YM API calls
    ym_retry_attempts: int = 3
    ym_retry_backoff_factor: float = 2.0    # exponential backoff multiplier

    # ── MCP Server ────────────────────────────────────
    server_name: str = "DJ Music"
    pagination_size: int = 20
    pagination_max: int = 100
    cache_dir: str = "cache/"
    mcp_retry_attempts: int = 3
    mcp_retry_delay: float = 1.0
    payload_logging: bool = False
    debug: bool = False

    # ── Transition Scoring ────────────────────────────
    transition_cache_ttl: int = 3600        # seconds
    transition_cache_max_size: int = 10_000  # max cached pairs
    transition_hard_reject_bpm_diff: float = 10.0
    transition_hard_reject_camelot_dist: int = 5
    transition_hard_reject_energy_gap: float = 6.0  # LUFS

    # ── GA Optimizer ──────────────────────────────────
    ga_population_size: int = 100
    ga_max_generations: int = 200
    ga_mutation_rate: float = 0.15
    ga_elitism_rate: float = 0.05
    ga_tournament_size: int = 3
    ga_convergence_threshold: int = 20      # generations without improvement

    # ── Audio Analysis ────────────────────────────────
    audio_analysis_timeout: float = 120.0   # per-track timeout (seconds)
    audio_batch_timeout: float = 600.0
    audio_stem_timeout: float = 300.0
    audio_hop_length: int = 512
    audio_sample_rate: int = 22050
    audio_mfcc_n_coeffs: int = 13

    # ── Techno Quality Criteria ───────────────────────
    techno_bpm_min: float = 120.0
    techno_bpm_max: float = 155.0
    techno_lufs_min: float = -20.0
    techno_lufs_max: float = -4.0
    techno_energy_min: float = 0.05
    techno_onset_rate_min: float = 1.0
    techno_kick_prominence_min: float = 0.05
    techno_pulse_clarity_min: float = 0.02
    techno_hp_ratio_max: float = 8.0
    techno_centroid_min: float = 300.0      # Hz
    techno_centroid_max: float = 10_000.0   # Hz
    techno_flatness_max: float = 0.5
    techno_tempo_confidence_min: float = 0.3
    techno_bpm_stability_min: float = 0.3
    techno_crest_factor_max: float = 30.0   # dB
    techno_lra_max: float = 25.0            # LU
    techno_hnr_min: float = -30.0           # dB

    # ── Mood Classifier ───────────────────────────────
    mood_catch_all_penalty: float = 0.85    # penalty for driving/hypnotic
    mood_confidence_threshold: float = 0.3  # min confidence for classification

    # ── Delivery ──────────────────────────────────────
    delivery_output_dir: str = "generated-sets/"
    delivery_icloud_stub_threshold: float = 0.9  # blocks/size ratio

    # ── LLM Sampling ─────────────────────────────────
    anthropic_api_key: str = ""             # env: ANTHROPIC_API_KEY (no DJ_ prefix)
    sampling_model: str = "claude-sonnet-4-5"
    sampling_max_tokens: int = 512
    sampling_temperature: float = 0.8

    # ── Observability ─────────────────────────────────
    sentry_dsn: str = ""                    # env: SENTRY_DSN (no DJ_ prefix)
    otel_endpoint: str = ""                 # env: OTEL_EXPORTER_OTLP_ENDPOINT
    otel_service_name: str = "dj-music"     # env: OTEL_SERVICE_NAME

    @property
    def is_dev(self) -> bool:
        return self.debug

    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow ANTHROPIC_API_KEY, SENTRY_DSN, OTEL_* without DJ_ prefix
        env_nested_delimiter=None,
    )

settings = Settings()
```

### 14.2 Usage Pattern

All code references `settings.*` — never hardcoded values:

```python
# ✅ Correct — from settings
if bpm_diff > settings.transition_hard_reject_bpm_diff:
    return 0.0

scorer = TransitionScorer(
    bpm_threshold=settings.transition_hard_reject_bpm_diff,
    camelot_threshold=settings.transition_hard_reject_camelot_dist,
    energy_threshold=settings.transition_hard_reject_energy_gap,
)

optimizer = GeneticAlgorithm(
    population_size=settings.ga_population_size,
    max_generations=settings.ga_max_generations,
    mutation_rate=settings.ga_mutation_rate,
)

# ❌ Wrong — hardcoded magic numbers
if bpm_diff > 10:        # What is 10? Where does it come from?
    return 0.0
```

### 14.3 Domain Constants (`app/core/constants.py`)

Non-configurable domain constants that define the system's vocabulary:

```python
from enum import IntEnum, StrEnum

class TrackStatus(IntEnum):
    ACTIVE = 0
    ARCHIVED = 1

class SectionType(IntEnum):
    INTRO = 0
    ATTACK = 1
    BUILD = 2
    PRE_DROP = 3
    DROP = 4
    PEAK = 5
    BREAKDOWN = 6
    OUTRO = 7
    RISE = 8
    VALLEY = 9
    SUSTAIN = 10

class CueKind(IntEnum):
    CUE = 0
    HOT_CUE_1 = 1
    HOT_CUE_2 = 2
    HOT_CUE_3 = 3
    HOT_CUE_4 = 4
    HOT_CUE_5 = 5
    HOT_CUE_6 = 6
    HOT_CUE_7 = 7
    MEMORY = 8  # not in spec, but logical extension

class TechnoSubgenre(StrEnum):
    """15 subgenres ordered by energy intensity (low → high)."""
    AMBIENT_DUB = "ambient_dub"
    DUB_TECHNO = "dub_techno"
    MINIMAL = "minimal"
    DETROIT = "detroit"
    MELODIC_DEEP = "melodic_deep"
    PROGRESSIVE = "progressive"
    HYPNOTIC = "hypnotic"
    DRIVING = "driving"
    TRIBAL = "tribal"
    BREAKBEAT = "breakbeat"
    PEAK_TIME = "peak_time"
    ACID = "acid"
    RAW = "raw"
    INDUSTRIAL = "industrial"
    HARD_TECHNO = "hard_techno"

class ExportFormat(StrEnum):
    M3U8 = "m3u8"
    REKORDBOX_XML = "rekordbox_xml"
    JSON_GUIDE = "json_guide"
    CHEAT_SHEET = "cheat_sheet"

class TargetApp(StrEnum):
    TRAKTOR = "traktor"
    REKORDBOX = "rekordbox"
    DJAY = "djay"
    GENERIC = "generic"

class Provider(StrEnum):
    YANDEX_MUSIC = "yandex_music"
    SPOTIFY = "spotify"
    BEATPORT = "beatport"
    SOUNDCLOUD = "soundcloud"

class SetTemplate(StrEnum):
    WARM_UP_30 = "warm_up_30"
    CLASSIC_60 = "classic_60"
    PEAK_HOUR_60 = "peak_hour_60"
    ROLLER_90 = "roller_90"
    PROGRESSIVE_120 = "progressive_120"
    WAVE_120 = "wave_120"
    CLOSING_60 = "closing_60"
    FULL_LIBRARY = "full_library"

# Camelot wheel: 24 keys, static
CAMELOT_KEYS: dict[int, tuple[str, str]] = {
    # key_code: (camelot_notation, key_name)
    0: ("1A", "A♭ minor"),   1: ("1B", "B major"),
    2: ("2A", "E♭ minor"),   3: ("2B", "F♯ major"),
    4: ("3A", "B♭ minor"),   5: ("3B", "D♭ major"),
    6: ("4A", "F minor"),    7: ("4B", "A♭ major"),
    8: ("5A", "C minor"),    9: ("5B", "E♭ major"),
    10: ("6A", "G minor"),  11: ("6B", "B♭ major"),
    12: ("7A", "D minor"),  13: ("7B", "F major"),
    14: ("8A", "A minor"),  15: ("8B", "C major"),
    16: ("9A", "E minor"),  17: ("9B", "G major"),
    18: ("10A", "B minor"), 19: ("10B", "D major"),
    20: ("11A", "F♯ minor"),21: ("11B", "A major"),
    22: ("12A", "D♭ minor"),23: ("12B", "E major"),
}

# BPM constraints
BPM_MIN = 20.0
BPM_MAX = 300.0

# Confidence constraints
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0

# Energy constraints
ENERGY_MIN = 0.0
ENERGY_MAX = 1.0

# Hotcue index range
HOTCUE_INDEX_MIN = 0
HOTCUE_INDEX_MAX = 15

# Key code range
KEY_CODE_MIN = 0
KEY_CODE_MAX = 23

# Transition scoring weights (default, overridable per-template)
DEFAULT_TRANSITION_WEIGHTS = {
    "bpm": 0.25,
    "harmonic": 0.20,
    "energy": 0.25,
    "spectral": 0.15,
    "groove": 0.15,
}
```

### 14.4 Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| **Database** | | |
| `DJ_DATABASE_URL` | `sqlite+aiosqlite:///dj_music.db` | Database connection |
| **Yandex Music** | | |
| `DJ_YM_TOKEN` | — | Yandex Music OAuth token |
| `DJ_YM_USER_ID` | — | YM user ID |
| `DJ_YM_BASE_URL` | `https://api.music.yandex.net` | YM API base URL |
| `DJ_YM_LIBRARY_PATH` | — | iCloud library path for downloads |
| `DJ_YM_RATE_LIMIT_DELAY` | `1.5` | Seconds between YM API calls |
| **MCP** | | |
| `DJ_CACHE_DIR` | `cache/` | Audio cache directory |
| `DJ_PAGINATION_SIZE` | `20` | Default page size |
| `DJ_MCP_RETRY_ATTEMPTS` | `3` | Retry attempts for transient errors |
| `DJ_MCP_RETRY_DELAY` | `1.0` | Base retry delay (seconds) |
| `DJ_PAYLOAD_LOGGING` | `false` | Log full request/response payloads |
| `DJ_DEBUG` | `false` | Debug mode (hot reload, verbose logs) |
| **Scoring & Optimization** | | |
| `DJ_TRANSITION_CACHE_TTL` | `3600` | Transition cache TTL (seconds) |
| `DJ_GA_POPULATION_SIZE` | `100` | GA population size |
| `DJ_GA_MAX_GENERATIONS` | `200` | GA max generations |
| `DJ_GA_MUTATION_RATE` | `0.15` | GA mutation rate |
| **LLM Sampling** | | |
| `ANTHROPIC_API_KEY` | — | For sampling fallback |
| `DJ_SAMPLING_MODEL` | `claude-sonnet-4-5` | Sampling model name |
| `DJ_SAMPLING_MAX_TOKENS` | `512` | Max tokens for sampling responses |
| **Observability** | | |
| `SENTRY_DSN` | — | Optional Sentry error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | Optional OTEL endpoint |
| `OTEL_SERVICE_NAME` | `dj-music` | Service name for traces |

---

## 15. Testing Strategy

### 15.1 Test Types

| Type | Runner | DB | Purpose |
|------|--------|-----|---------|
| Unit | pytest | None | Domain models, utilities, Camelot, mood classifier |
| Service | pytest | In-memory SQLite | Repository + service logic |
| Audio | pytest | None | Synthetic WAV fixtures |
| MCP Integration | FastMCP Client | In-memory SQLite | Tool calls + structured output |
| MCP Metadata | FastMCP Client | None | Registration, tags, annotations, visibility |

### 15.2 Key Fixtures

```python
@pytest.fixture
async def client(seeded_db):
    """FastMCP Client with seeded database."""
    async with Client(mcp) as c:
        yield c

@pytest.fixture
def seeded_db():
    """In-memory SQLite with reference data:
    - 24 keys (Camelot wheel)
    - 4 providers
    - 50 test tracks with features
    - 3 playlists with items
    - 2 sets with versions
    """

@pytest.fixture
def synthetic_audio():
    """WAV files with known properties:
    - 440Hz sine wave (known frequency → key A4)
    - 128 BPM click track (known tempo)
    - White noise (known spectral flatness=1.0)
    """
```

### 15.3 Coverage Targets

| Component | Target |
|-----------|--------|
| Domain models | 100% constraint validation |
| Repositories | 90%+ CRUD operations |
| Services | 90%+ business logic |
| Audio analyzers | 80%+ with synthetic fixtures |
| MCP tools | 100% metadata + 90% integration |
| Resources | 100% |
| Prompts | 100% structure validation |

---

## 16. Documentation & Developer Infrastructure

### 16.1 CLAUDE.md — Project Rules

CLAUDE.md is the primary Claude Code instructions file. It must contain:

- Project purpose and pointer to REQUIREMENTS.md and design spec
- Language/framework constraints (Python 3.12+, async, strict typing)
- Dev commands (`uv sync`, `uv run pytest`, `uv run ruff`, `uv run mypy`)
- Architecture summary (layers: models → repos → services → tools)
- Plugin usage rules (when to use fastmcp-builder, mcp-server-dev, etc.)
- Key patterns: "no magic numbers", "settings.* for all config", "constants.py for enums"
- Commit conventions (conventional commits, Russian communication)

### 16.2 Path-Specific Rules (`.claude/rules/`)

Rules that activate only when Claude reads/writes files matching a path pattern:

| File | Glob Pattern | Rules |
|------|-------------|-------|
| `models.md` | `app/models/**/*.py` | SQLAlchemy 2.0 async style, mapped_column, CheckConstraint for domain ranges, __tablename__ convention, always add created_at/updated_at |
| `repositories.md` | `app/repositories/**/*.py` | Extend BaseRepository, session.flush() never commit, cursor pagination via _paginate(), return model instances not dicts |
| `services.md` | `app/services/**/*.py` | Never import session directly, receive repos via __init__, raise domain errors (NotFoundError, ValidationError), no MCP/FastMCP imports |
| `tools.md` | `app/mcp/tools/**/*.py` | Use @tool decorator, Depends() for DI, annotations required, tags required, descriptions ≤50 words, return Pydantic models for structuredContent |
| `resources.md` | `app/mcp/resources/**/*.py` | Use @resource decorator, return JSON strings or ResourceResult, tags required, template URIs for parametric |
| `tests.md` | `tests/**/*.py` | pytest-asyncio, use client fixture for MCP tests, use seeded_db for DB tests, assert on structured_content, never mock the database |
| `audio.md` | `app/audio/**/*.py` | Check optional deps with try/import, register in AnalyzerRegistry, return typed result dataclasses, handle partial failures |
| `ym.md` | `app/ym/**/*.py` | All methods async, respect rate_limiter, return typed Pydantic models, handle 429/403/400 specifically |
| `config.md` | `app/config.py` | All values in Settings class, env_prefix="DJ_", no magic numbers, document units in comments |

### 16.3 README.md Structure

```markdown
# DJ Music Plugin

> MCP server for DJ techno music library management

## Features
- 44 MCP tools across 10 categories
- Audio analysis pipeline (BPM, key, energy, mood classification)
- DJ set generation (genetic algorithm + greedy builder)
- Yandex Music integration (search, import, sync)
- Export: M3U8, Rekordbox XML, JSON guide

## Quick Start
1. `uv sync`
2. `cp .env.example .env` — fill in YM token
3. `uv run fastmcp run app/server.py`

## Development
- `uv run pytest -v` — tests
- `uv run ruff check && uv run ruff format --check` — lint
- `uv run mypy app/` — type check
- `uv run alembic upgrade head` — apply migrations

## Architecture
[pointer to design spec]

## Configuration
[pointer to §14 of design spec or .env.example]
```

### 16.4 CHANGELOG.md Format

```markdown
# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Initial project scaffolding
- Design specification (docs/superpowers/specs/)
```

### 16.5 pyproject.toml Structure

```toml
[project]
name = "dj-music-plugin"
version = "0.1.0"
description = "MCP server for DJ techno music library management"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=3.1.0",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27",
    "numpy>=1.26",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
audio = ["librosa>=0.10", "soundfile>=0.12"]
stems = ["demucs>=4.0", "torch>=2.0"]
postgres = ["asyncpg>=0.29", "pgvector>=0.3"]
otel = [
    "opentelemetry-distro",
    "opentelemetry-exporter-otlp",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "mypy>=1.13",
    "alembic>=1.14",
]

[tool.ruff]
line-length = 99
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 16.6 .env.example

```bash
# Database
DJ_DATABASE_URL=sqlite+aiosqlite:///dj_music.db

# Yandex Music (required for YM features)
DJ_YM_TOKEN=your_oauth_token_here
DJ_YM_USER_ID=your_user_id_here
DJ_YM_LIBRARY_PATH=/Users/you/Music/Music/Media.localized/

# Debug
DJ_DEBUG=false

# LLM Sampling (optional — for find_similar_tracks with strategy=llm)
# ANTHROPIC_API_KEY=sk-ant-...

# Observability (optional)
# SENTRY_DSN=https://...@sentry.io/...
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### 16.7 Makefile

```makefile
.PHONY: install test lint typecheck check migrate dev

install:
	uv sync --all-extras

test:
	uv run pytest -v

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

typecheck:
	uv run mypy app/

check: lint typecheck test

migrate:
	uv run alembic upgrade head

dev:
	uv run fastmcp dev app/server.py --reload
```

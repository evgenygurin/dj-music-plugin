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

| Category | Tools | Tags | Visibility | Description |
|----------|-------|------|-----------|-------------|
| CRUD | 10 | `core` | Always visible | Tracks, playlists, sets, features |
| Search | 2 | `core` | Always visible | Universal search, parametric filter |
| Set Building | 4 | `sets` | Always visible | Build, rebuild, score, cheat sheet |
| Set Reasoning | 5 | `sets` | Always visible | Suggest, explain, replace, compare, quick review |
| Delivery & Export | 2 | `delivery` | Extended | Deliver pipeline, export formats |
| Discovery | 3 | `discovery` | Extended | Find similar, import, download |
| Curation | 5 | `curation` | Extended | Classify, audit, review, distribute, stats |
| Sync | 2 | `sync` | Extended | Bidirectional sync, push to YM |
| YM API | 6 | `ym` | Extended | Search, tracks, albums, artists, playlists, likes |
| Audio | 3 | `audio` | **Hidden** | Analyze, batch, stems |
| Admin | 2 | `admin` | Always visible | Unlock tools, list platforms |
| **Total** | **44** | | | |

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
│   │   ├── errors.py          # DJMusicError hierarchy
│   │   ├── pagination.py      # CursorPagination
│   │   ├── entity_resolver.py # EntityResolver (flexible refs)
│   │   ├── camelot.py         # Camelot wheel, key distance
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

All via environment variables (pydantic-settings):

| Variable | Default | Purpose |
|----------|---------|---------|
| **Database** | | |
| `DJ_DATABASE_URL` | `sqlite+aiosqlite:///dj_music.db` | Database connection |
| **Yandex Music** | | |
| `DJ_YM_TOKEN` | — | Yandex Music OAuth token |
| `DJ_YM_USER_ID` | — | YM user ID |
| `DJ_YM_BASE_URL` | `https://api.music.yandex.net` | YM API base URL |
| `DJ_YM_LIBRARY_PATH` | — | iCloud library path for downloads |
| **MCP** | | |
| `DJ_CACHE_DIR` | `cache/` | Audio cache directory |
| `DJ_CACHE_TTL` | `3600` | Transition cache TTL (seconds) |
| `DJ_PAGINATION_SIZE` | `20` | Default page size |
| `DJ_MCP_RETRY_ATTEMPTS` | `3` | Retry attempts for transient errors |
| `DJ_MCP_RETRY_DELAY` | `1.0` | Base retry delay (seconds) |
| `DJ_PAYLOAD_LOGGING` | `false` | Log full request/response payloads |
| `DJ_DEBUG` | `false` | Debug mode (hot reload, verbose logs) |
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

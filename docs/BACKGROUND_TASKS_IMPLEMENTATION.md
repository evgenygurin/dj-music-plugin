# Background Tasks Implementation Summary

## Overview

Implemented FastMCP v3.1 background task support for long-running DJ operations. Enables async execution with progress tracking for audio analysis, transition scoring, and import workflows.

## Changes

### 1. Dependencies

**pyproject.toml**:
- Added `tasks = ["fastmcp[tasks]>=3.1.0"]` optional extra

### 2. Configuration

**app/config.py**:
```python
# Background Tasks
docket_url: str = "memory://"  # memory:// or redis://host:port/db
docket_concurrency: int = 4
task_poll_interval_seconds: int = 5
```

**app/server.py**:
- Map `DJ_DOCKET_*` to `FASTMCP_DOCKET_*` environment variables

**.env.example**:
- Added background tasks section with defaults

### 3. Task-Enabled Tools

#### Audio Tools (tag: `audio`)

All 3 audio tools now support background execution:

| Tool | Mode | Poll Interval | Why Background |
|------|------|---------------|----------------|
| `analyze_track` | optional | 5s | Single track analysis (30-60s) |
| `analyze_batch` | optional | 5s | Multi-track batch (minutes-hours) |
| `separate_stems` | **required** | 10s | ML inference always slow (5-10 min/track) |

**Implementation**:
- Accept `Progress` dependency for progress reporting
- Use `TaskConfig(mode=...)` decorator parameter
- Simulated progress stages in stubs (real pipeline TBD)

#### Set Building (tag: `sets`)

New tool: `score_track_transitions_background`
- Mode: optional
- Purpose: Score all possible transitions for a track (~3K pairs)
- Delegates to `app/services/background_tasks.py`

#### Discovery (tag: `discovery`)

Enhanced `import_tracks`:
- Accept `Docket` dependency via `CurrentDocket()`
- When `auto_analyze=True`, schedule background `analyze_batch` task
- Return `auto_analyze_scheduled=True` in result

### 4. Service Layer

**app/services/background_tasks.py**:
- `score_track_transitions()` — business logic for scoring
- `_features_to_dataclass()` — DB model → service dataclass converter
- No MCP imports (framework-agnostic)
- Accept `DocketProgress` for reporting

### 5. Documentation

**docs/background-tasks.md** — comprehensive guide covering:
- Installation (`uv sync --extra tasks`)
- Backend configuration (memory vs Redis)
- Environment variables
- Task modes (optional, required, forbidden)
- Progress API
- Worker scaling
- Event-driven pipeline (future)

**docs/tool-catalog.md**:
- Added "Task" column to tool tables
- Added legend explaining task modes
- Updated total to 45 tools

**docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md**:
- Updated tool summary table with background tasks column
- Added environment setup in §2.1

**CLAUDE.md**:
- Added `@docs/background-tasks.md` to documentation list

### 6. Tests

**tests/test_background_tasks.py**:
- Tool metadata tests (task annotations)
- Service layer tests (`_features_to_dataclass`, error handling)
- Placeholder for full integration tests (requires Docket setup)

## Usage

### Development (Memory Backend)

```bash
uv sync --extra tasks
uv run fastmcp dev app/server.py --reload
```

All tools work normally. When client requests background execution:
- Task runs in embedded worker (single process)
- Progress available via polling
- ~250ms pickup latency

### Production (Redis Backend)

```bash
# Terminal 1: Main server
FASTMCP_DOCKET_URL=redis://localhost:6379 uv run fastmcp run app/server.py

# Terminal 2: Worker
FASTMCP_DOCKET_CONCURRENCY=20 uv run fastmcp tasks worker app/server.py

# Terminal 3: Another worker
FASTMCP_DOCKET_CONCURRENCY=20 uv run fastmcp tasks worker app/server.py
```

Workers pull from shared queue. Tasks persist across restarts.

## Examples

### Background Analysis

```python
# Client requests analyze_batch as background task
result = await client.call_tool(
    "analyze_batch",
    arguments={"track_ids": [1, 2, 3], "priority": "high"},
    as_task=True,  # <-- background execution
)
# Returns: {"task_id": "xyz123"}

# Poll for progress
status = await client.get_task_status("xyz123")
# {"progress": 50, "message": "Analyzing track 2/3..."}

# Get result when done
final = await client.get_task_result("xyz123")
```

### Auto-Analysis After Import

```python
result = await client.call_tool(
    "import_tracks",
    arguments={
        "track_refs": ["123", "456", "789"],
        "auto_analyze": True,  # <-- schedules background task
    },
)
# Returns: {
#   "imported": 3,
#   "auto_analyze_scheduled": True,
#   "analysis_track_count": 3,
#   "note": "Scheduled background analysis for 3 imported tracks"
# }
```

### Background Transition Scoring

```python
result = await client.call_tool(
    "score_track_transitions_background",
    arguments={"track_id": 42},
    as_task=True,
)
# Scores all 3K transitions for track 42 in background
```

## Future Enhancements

1. **Event-driven pipeline**:
   ```
   import_tracks → TrackImported event
     → auto_analyze (background)
       → TrackFeaturesUpdated event
         → score_track_transitions_background
           → TransitionsScored event
             → classify_mood
   ```

2. **Smart scheduling**: Prioritize tracks in active sets

3. **Incremental cache warming**: Auto-score transitions for new tracks

4. **Batch consolidation**: Merge multiple analyze_track calls

## Architecture Notes

### Separation of Concerns

```
MCP Tool Layer (app/mcp/tools/)
  ├── Accept Progress, Docket dependencies
  ├── Handle MCP concerns (ctx.info, error mapping)
  └── Delegate to service layer

Service Layer (app/services/background_tasks.py)
  ├── No MCP imports
  ├── Accept DocketProgress for reporting
  ├── Pure business logic
  └── Framework-agnostic (testable, reusable)
```

### Task Lifecycle

```
Client → MCP Server → FastMCP → Docket
                                   ↓
                            Background Worker
                                   ↓ (DB session per task)
                            Service Function
                                   ↓
                            Result (stored by Docket)
                                   ↓
Client polls → MCP Server → FastMCP → Docket
```

### Progress Reporting

Tools use `Progress` (FastMCP wrapper), services use `DocketProgress`:

```python
# Tool:
async def my_tool(progress: Progress = Progress()):
    await progress.set_total(100)
    await progress.increment()

# Service:
async def my_service(progress: DocketProgress | None = None):
    if progress:
        await progress.set_message("Working...")
```

## Testing

```bash
# Syntax check
python3 -m py_compile app/services/background_tasks.py

# Run tests
uv run pytest tests/test_background_tasks.py -v

# Full suite
uv run pytest -v
```

## Limitations

- Memory backend: single process, no scaling
- Task discovery: tools must be registered at startup
- Session management: each task gets its own DB session
- No streaming: progress is poll-based (not pushed)

## Migration Notes

Existing tools unchanged. Background support is opt-in:
- Tools without `task=...` parameter work as before
- Clients can request background execution on any task-enabled tool
- No breaking changes to API contracts

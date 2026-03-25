# Background Tasks

FastMCP v3.1 background task support for long-running DJ operations.

## Overview

Background tasks allow clients to:
1. Start an operation and receive a task ID immediately
2. Track progress as the operation runs
3. Retrieve the result when ready

This prevents blocking the client during expensive operations like audio analysis or transition scoring.

## Installation

```bash
uv sync --extra tasks
```

## Backend Configuration

Two backends supported:

### Memory (Default)
- Zero config: `FASTMCP_DOCKET_URL=memory://`
- Single process only
- Ephemeral (tasks lost on restart)
- ~250ms task pickup latency

### Redis (Production)
- `FASTMCP_DOCKET_URL=redis://localhost:6379`
- Horizontal scaling: add workers with `fastmcp tasks worker app/server.py`
- Persistent tasks
- Single-digit millisecond latency

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_DOCKET_URL` | `memory://` | Backend URL (memory:// or redis://...) |
| `DJ_DOCKET_CONCURRENCY` | `4` | Concurrent tasks per worker |
| `DJ_TASK_POLL_INTERVAL_SECONDS` | `5` | Client poll interval hint |
| `FASTMCP_DOCKET_URL` | (from DJ_DOCKET_URL) | FastMCP backend override |
| `FASTMCP_DOCKET_CONCURRENCY` | (from DJ_DOCKET_CONCURRENCY) | FastMCP concurrency override |

## Tools with Background Support

### Audio Analysis (tag: `audio`)

| Tool | Task Mode | Poll Interval | Why |
|------|-----------|---------------|-----|
| `analyze_track` | optional | 5s | Single track analysis (~30-60s) |
| `analyze_batch` | optional | 5s | Multiple tracks (minutes to hours) |
| `separate_stems` | **required** | 10s | ML inference is always slow (5-10 min/track) |

**optional**: Client chooses sync or background.
**required**: Always runs as background task.

### Set Building (tag: `sets`)

| Tool | Task Mode | Poll Interval | Why |
|------|-----------|---------------|-----|
| `score_track_transitions_background` | optional | 5s | Score ~3K transitions for a track |

### Discovery (tag: `discovery`)

`import_tracks` with `auto_analyze=True` schedules background `analyze_batch` via Docket.

## Progress Reporting

All background-capable tools accept `Progress` dependency:

```python
from fastmcp.dependencies import Progress

@mcp.tool(task=TaskConfig(mode="optional"))
async def my_tool(progress: Progress = Progress()):
    await progress.set_total(100)
    await progress.set_message("Starting...")

    for i in range(100):
        # ... do work ...
        await progress.increment()
        await progress.set_message(f"Processing item {i}...")

    return {"done": True}
```

Progress API:
- `await progress.set_total(n)` — set total steps
- `await progress.set_message(text)` — update status message
- `await progress.increment(amount=1)` — increment progress

## Task Orchestration

Tools can schedule additional background tasks via `CurrentDocket()`:

```python
from docket import CurrentDocket, Docket

@mcp.tool()
async def import_tracks(
    track_refs: list[str],
    auto_analyze: bool = False,
    docket: Docket = CurrentDocket(),
):
    # ... import tracks ...

    if auto_analyze:
        from app.mcp.tools.audio import analyze_batch
        await docket.add(analyze_batch, track_ids=imported_ids)
```

## Event-Driven Pipeline (Future)

Planned event-driven flow:

```text
import_tracks
  ↓ (auto_analyze=True)
  → analyze_batch (background)
      ↓ (on completion, emit TrackFeaturesUpdated event)
      → score_track_transitions_background (background)
          ↓ (on completion, emit TransitionsScored event)
          → classify_mood (background)
```

Requires event bus integration — not yet implemented.

## Worker Scaling

### Development
Single embedded worker (automatic, no extra process needed).

### Production with Redis

```bash
# Terminal 1: Main server
uv run fastmcp run app/server.py

# Terminal 2: Additional worker
FASTMCP_DOCKET_CONCURRENCY=20 uv run fastmcp tasks worker app/server.py

# Terminal 3: Another worker
FASTMCP_DOCKET_CONCURRENCY=20 uv run fastmcp tasks worker app/server.py
```

Each worker pulls tasks from the shared Redis queue.

## Implementation Details

### Task Modes

Three modes per SEP-1686:

| Mode | Client calls without task | Client calls with task |
|------|---------------------------|------------------------|
| `forbidden` | Executes synchronously | Error: task not supported |
| `optional` | Executes synchronously | Executes as background task |
| `required` | Error: task required | Executes as background task |

### Service Layer Pattern

Background tasks delegate to services in `app/services/background_tasks.py`:

```python
# In tool:
@mcp.tool(task=TaskConfig(mode="optional"))
async def score_track_transitions_background(
    track_id: int,
    progress: Progress = Progress(),
    ctx: Context = CurrentContext(),
):
    from app.services.background_tasks import score_track_transitions

    async with await _get_session(ctx) as session:
        result = await score_track_transitions(
            track_id=track_id,
            session=session,
            progress=progress,
        )
        return result

# In service:
async def score_track_transitions(
    track_id: int,
    session: AsyncSession,
    progress: DocketProgress | None = None,
):
    # Business logic here, no MCP imports
    if progress:
        await progress.set_message("Scoring transitions...")
    # ...
```

This keeps business logic framework-agnostic and testable.

## Testing

Background tasks work in tests via `fastmcp.testing.Client`:

```python
from fastmcp.testing import Client

async def test_analyze_batch_as_task():
    async with Client(mcp) as client:
        # Request as background task
        result = await client.call_tool(
            "analyze_batch",
            arguments={"track_ids": [1, 2, 3]},
            as_task=True,  # <-- background execution
        )
        assert "task_id" in result
```

Tests use in-memory backend automatically.

## Limitations

- **Memory backend**: single process only, no horizontal scaling
- **Task discovery**: Tools must be registered at server startup (dynamic addition not supported)
- **Session management**: Each background task gets its own DB session (commit/rollback per task)
- **No streaming**: Progress is poll-based, not pushed (client must poll for updates)

## Future Enhancements

1. **Event bus**: TrackImported → AutoAnalyze → FeaturesUpdated → ScoreTransitions
2. **Priority queues**: High-priority tasks jump ahead
3. **Smart scheduling**: Analyze tracks in active sets before archived tracks
4. **Batch consolidation**: Merge multiple analyze_track calls into one analyze_batch
5. **Incremental cache warming**: Score transitions for new tracks automatically

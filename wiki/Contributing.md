# Contributing

## Development Setup

```bash
git clone https://github.com/evgenygurin/dj-music-plugin.git
cd dj-music-plugin
uv sync --all-extras
cp .env.example .env
```

## Code Style

### Python Version

Python 3.12+ with modern syntax:
- Type hints everywhere (strict mypy)
- `match/case` for pattern matching
- `StrEnum`, `IntEnum` for enums
- `async/await` for all I/O

### Linting

```bash
# Check
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/

# Auto-fix
uv run ruff check --fix app/ tests/
uv run ruff format app/ tests/
```

**Ruff configuration** (from `pyproject.toml`):
- Line length: 99
- Target: Python 3.12
- Rules: E, F, W, I, N, UP, B, SIM, RUF
- Pyright warnings are **ignored** -- they produce false positives on `@tool` decorators

### Type Checking

```bash
uv run mypy app/
```

**mypy configuration:**
- Strict mode enabled
- Pydantic plugin active
- `librosa`, `soundfile`, `demucs` imports ignored (optional deps)

### Formatting Quick Reference

```python
# Imports: isort-compatible, first-party = ["app"]
from __future__ import annotations

import logging
from typing import Literal

from fastmcp.tools import tool
from pydantic import BaseModel

from app.config import settings
from app.core.errors import NotFoundError
```

## Architecture Rules

### Layer Discipline

```
Tools -> Services -> Repositories -> Models
```

Each layer imports **only** the layer below. Never import MCP in services. Never import services in models.

### One File = One Responsibility

**Never** create duplicate/extending files (e.g., `middleware.py` + `custom_middleware.py`). Extend in the same file.

### No Magic Numbers

```python
# Correct: use settings
if bpm_diff > settings.transition_hard_reject_bpm_diff:
    return 0.0

# Wrong: hardcoded value
if bpm_diff > 10:
    return 0.0
```

All tunable values go in `app/config.py` (`settings.*`). All domain constants go in `app/core/constants.py`.

### MCP Tool Pattern

```python
from fastmcp.tools import tool              # standalone, NOT from app.server
from fastmcp.dependencies import Depends

@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def my_tool(
    id: int,
    view: Literal["summary", "full"] = "summary",
    svc=Depends(get_my_service),       # param=Depends() pattern
) -> MyModel:
    """Short description (max 50 words)."""
    return await svc.get(id, view=view)
```

> **Important:** Use `param=Depends(factory)`, NOT `Annotated[Type, Depends(factory)]` -- FastMCP doesn't resolve the Annotated pattern.

### Repository Pattern

```python
class MyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> MyModel:
        obj = MyModel(**data)
        self.session.add(obj)
        await self.session.flush()  # flush, NEVER commit
        return obj
```

Commit is handled by the DI wrapper `get_db_session()` at the tool boundary.

### Error Handling

```python
# In services: raise domain errors
from app.core.errors import NotFoundError, ValidationError

raise NotFoundError("Track", track_id)
raise ValidationError("BPM must be between 20 and 300", field="bpm")

# In tools: ToolError for input validation
from fastmcp import ToolError

raise ToolError("Provide either id or query")
```

### Feature Loading

```python
# Correct: classmethod + repository
feat = TrackFeatures.from_db(row)
feat = await feat_repo.get_scoring_features(track_id)
features_map = await feat_repo.get_scoring_features_batch(track_ids)

# Wrong: manual field copying
TrackFeatures(bpm=row.bpm, key_code=row.key_code, ...)  # Don't duplicate fields!
```

### Time Utilities

```python
# Correct: use utility functions
from app.utils.time import utc_now, utc_timestamp_iso, sa_now

created_at = utc_now()
timestamp = utc_timestamp_iso()

# Wrong: direct datetime usage
from datetime import datetime
datetime.now()     # Don't use
func.now()         # Don't use in SQLAlchemy
```

## Testing

### Running Tests

```bash
# All tests
uv run pytest -v

# Specific test file
uv run pytest tests/test_tracks.py -v

# Specific test function
uv run pytest tests/test_tracks.py::test_create_track -v

# With coverage
uv run pytest --cov=app -v
```

### Test Infrastructure

- **In-memory SQLite** for all tests (fast, no cleanup needed)
- **Synthetic audio fixtures** (generated WAV files with known frequencies)
- **MCP test fixtures** for each server variant

### Test Requirements

Every component must have tests:

| Component | Required Tests |
|-----------|---------------|
| Domain models | Constraint validation |
| Services | Unit tests with real DB (in-memory SQLite) |
| Audio utilities | Tests with synthetic audio |
| MCP tools | Metadata tests + client integration tests |
| DB-dependent tools | Tests with seeded data |

### MCP Tool Tests

```python
# Metadata test: verify tool registration
async def test_my_tool_registered(mcp_server):
    tools = await mcp_server.list_tools()
    my_tool = next(t for t in tools if t.name == "my_tool")
    assert "core" in my_tool.tags
    assert my_tool.annotations.get("readOnlyHint") is True

# Integration test: invoke tool with structured output
async def test_my_tool_returns_data(mcp_client, seeded_db):
    result = await mcp_client.call_tool("my_tool", {"id": 1})
    assert result.structured_content["title"] == "Expected Title"
```

### pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

All async tests run automatically without `@pytest.mark.asyncio`.

## Git Conventions

### Branch Naming

```
feat/add-groove-analyzer
fix/ym-rate-limit-429
docs/update-tool-catalog
refactor/scoring-cache
test/transition-scoring
```

### Commit Messages

Follow conventional commits:

```
feat(audio): add groove analyzer for rhythmic complexity
fix(ym): handle 429 rate limit with exponential backoff
docs: update tool catalog with new discovery tools
refactor(scoring): extract cache to separate module
test(sets): add GA optimizer integration tests
```

### Pre-Commit Checks

Before committing, run:

```bash
make check  # lint + typecheck + test
```

Or individually:

```bash
uv run ruff check app/ tests/        # Linting
uv run ruff format --check app/ tests/  # Formatting
uv run mypy app/                      # Type checking
uv run pytest -v                      # Tests
```

## Common Gotchas

| Gotcha | Solution |
|--------|---------|
| `Depends()`: Annotated pattern doesn't work | Use `param=Depends(factory)` |
| Linter removes unused imports on save | Add import + usage in the same edit |
| `from __future__ import annotations` breaks runtime | Real imports needed for runtime calls |
| `AsyncSession.delete()` is async | `await session.delete(obj)` is correct |
| Pipeline features don't match DB | Always use `filter_features()` |
| `ym_artist_tracks` needs string ID | Pass `artist_id="123"` not `123` |
| YM search type is plural | `type="tracks"` not `type="track"` |
| YM playlist add needs albumId | Format: `"trackId:albumId"` |
| Energy band column names | `energy_sub`, `energy_lowmid`, `energy_highmid` |
| Circular imports repos<->services | Use `TYPE_CHECKING` + lazy import |

## Makefile Reference

```bash
make install    # uv sync --all-extras
make test       # uv run pytest -v
make lint       # ruff check + format check
make format     # ruff check --fix + format
make typecheck  # mypy app/
make check      # lint + typecheck + test (CI pipeline)
make migrate    # alembic upgrade head
make migrate-new msg="description"  # Create new migration
make dev        # fastmcp dev with hot reload
make run        # fastmcp run (production)
make clean      # Remove caches (__pycache__, .pytest_cache, etc.)
```

## Related Pages

- **[Architecture](Architecture)** -- Layer rules and patterns
- **[Configuration Reference](Configuration-Reference)** -- All settings
- **[Known Issues](Known-Issues)** -- Gotchas with root cause analysis

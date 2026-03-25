# Getting Started

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** -- fast Python package manager
- SQLite (bundled, default) or PostgreSQL 16+ (production)

## Installation

### Basic Installation

```bash
git clone https://github.com/evgenygurin/dj-music-plugin.git
cd dj-music-plugin
uv sync
```

### With Audio Analysis (BPM, Key, Beat Detection)

```bash
uv sync --extra audio
```

### All Extras

```bash
uv sync --all-extras
# Includes: audio (librosa), stems (demucs+torch), postgres (asyncpg+pgvector),
#           otel (opentelemetry), sentry, dev (pytest+ruff+mypy+alembic)
```

### As a Claude Code Plugin

```bash
/plugin marketplace add evgenygurin/dj-music-plugin
/plugin install dj-music
```

## Configuration

### 1. Create `.env` File

```bash
cp .env.example .env
```

### 2. Configure Required Settings

Edit `.env` with your values:

```bash
# Required for Yandex Music features
DJ_YM_TOKEN=your_oauth_token_here
DJ_YM_USER_ID=your_user_id_here

# Path to your local music library (for file operations)
DJ_YM_LIBRARY_PATH=/Users/you/Music/Music/Media.localized/
```

### 3. Optional Settings

```bash
# Database (SQLite is the default, no config needed for dev)
DJ_DATABASE_URL=sqlite+aiosqlite:///dj_music.db

# For server-side LLM sampling (not needed for Claude Code MAX users)
DJ_ANTHROPIC_API_KEY=sk-ant-...

# Debug mode (verbose logging, error details exposed)
DJ_DEBUG=false
```

See **[Configuration Reference](Configuration-Reference)** for all available settings.

## Database Setup

### SQLite (Development -- Default)

No setup needed. The database file is created automatically on first run.

### PostgreSQL (Production)

```bash
# Install PostgreSQL extras
uv sync --extra postgres

# Configure connection
echo 'DJ_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dj_music' >> .env

# Run migrations
uv run alembic upgrade head
```

For vector embeddings, install the pgvector extension:

```sql
CREATE EXTENSION vector;
```

## Running the Server

### Development (with hot reload)

```bash
uv run fastmcp dev app/server.py --reload
```

### Production

```bash
uv run fastmcp run app/server.py
```

### With OpenTelemetry Tracing

```bash
opentelemetry-instrument \
  --service_name dj-music \
  --exporter_otlp_endpoint http://localhost:4317 \
  fastmcp run app/server.py
```

## First Steps

Once the server is running, the AI assistant can interact with it via MCP tool calls. Here's a typical first session:

### 1. Check Library Health

```python
# List what's in the library
list_tracks(limit=10)

# Get library statistics
get_library_stats()
```

### 2. Import Tracks from Yandex Music

```python
# Search for tracks
ym_search(query="Amelie Lens techno", type="tracks", limit=10)

# Import to local library
import_tracks(track_refs=["ym:12345", "ym:67890"])
```

### 3. Build a DJ Set

```python
# Build from a playlist using genetic algorithm
build_set(playlist_id=1, name="My Techno Set", template="classic_60", algorithm="ga")

# Review the result
quick_set_review(set_id=1)
```

### 4. Deliver the Set

```python
# Unlock delivery tools first
unlock_tools(category="delivery")

# Export with all formats
deliver_set(set_id=1, copy_files=True, formats=["m3u8", "json_guide", "cheat_sheet"])
```

## Workflow Prompts

For complex multi-step operations, use the built-in workflow prompts:

| Prompt | Description |
|--------|-------------|
| `build_set_workflow` | Build an optimized DJ set from a playlist (7 steps) |
| `expand_playlist_workflow` | Discover and add similar tracks (7 steps) |
| `improve_set_workflow` | Fix weak transitions in an existing set (6 steps) |
| `deliver_set_workflow` | Score, export, and optionally sync to YM (7 steps) |
| `full_expansion_pipeline` | Complete pipeline: audit, discover, import, analyze, classify, distribute (9 steps) |
| `llm_discovery_workflow` | Client-driven track discovery (no API key needed) (5 steps) |

## LLM Discovery Modes

Two modes for LLM-assisted tools (e.g., `find_similar_tracks` with `strategy="llm"`):

### Client-Driven (Recommended for Claude Code)

Claude Code itself is an LLM -- it generates search queries and passes them to tools. No API key needed.

```python
find_similar_tracks(
    track_id=42,
    strategy="llm",
    search_queries=["Amelie Lens acid techno", "FJAAK industrial"]
)
```

### Server-Side Sampling

For headless/automated scenarios. Requires `DJ_ANTHROPIC_API_KEY`:

```bash
DJ_ANTHROPIC_API_KEY=sk-ant-...
```

`ctx.sample()` inside tools calls the Anthropic API via fallback handler.

## Makefile Commands

```bash
make install    # uv sync --all-extras
make test       # uv run pytest -v
make lint       # ruff check + format check
make format     # ruff check --fix + format
make typecheck  # mypy app/
make check      # lint + typecheck + test
make migrate    # alembic upgrade head
make dev        # fastmcp dev with reload
make run        # fastmcp run (production)
make clean      # remove caches
```

## Next Steps

- **[Architecture](Architecture)** -- Understand the layer structure and data flow
- **[MCP Tools Reference](MCP-Tools-Reference)** -- Browse all 50 available tools
- **[E2E Pipeline](E2E-Pipeline)** -- Learn the full track processing flow

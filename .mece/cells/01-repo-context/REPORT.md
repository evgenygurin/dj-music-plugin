# Cell 01 — Repository Context Report

## What Changed
No files modified (read-only cell per mission).

## Architecture Baseline

### Core Technology Stack
- **MCP Server**: FastMCP v3 (entry: `server.py` → `fastmcp.json`)
- **Package Manager**: `uv` only (Python 3.12+)
- **Database**: PostgreSQL (asyncpg) + SQLite (aiosqlite) via SQLAlchemy 2.0 async
- **Audio/DSP**: librosa, essentia, demucs, soundfile, scipy, numba
- **Code Intelligence**: GitNexus (42,668 symbols, 94,133 relationships, 300 execution flows)

### Bounded Contexts (app/)
| Context | Path | Responsibility |
|---------|------|----------------|
| Domain | `app/domain/` | Pure business logic, no I/O |
| Audio | `app/audio/` | DSP, librosa, beatgrid, stem separation |
| Handlers | `app/handlers/` | Orchestration, background tasks |
| Tools | `app/tools/` | MCP tool definitions (20+) |
| Repositories | `app/repositories/` | DB queries, UoW pattern |
| Resources | `app/resources/` | MCP resources (27) |
| Prompts | `app/prompts/` | MCP prompts (30) |
| Schemas | `app/schemas/` | Pydantic models, DTOs |
| Registry | `app/registry/` | Entity/provider registries |
| Providers | `app/providers/` | External API clients (YM, Beatport, Suno) |
| Server | `app/server/` | FastMCP app, DI, lifespan, observability |

### MCP Surface
- **Tools**: 20+ (track CRUD, set building, render pipeline, provider sync, analysis)
- **Resources**: 27 (library views, set views, render studio, transition scores, Camelot wheel)
- **Prompts**: 30 (workflows: build-set, curate-library, deliver-set, validate-set, expand-playlist, suno, ym-sync)

## Conventions & Governance

### Mandatory Commands
```bash
make check          # lint + typecheck + tests + import-linter (primary gate)
uv run pytest -n auto  # parallel tests
uv run ruff check     # lint only
uv run mypy app/      # strict typecheck
uv run lint-imports   # architectural boundaries
```

### Quality Gates
- **No CI**: GitHub Actions unavailable (billing lock)
- **Local only**: `make check` before every commit
- **Pre-push hook**: Auto-runs `make check` (skip: `DJ_SKIP_CHECK=1 git push`)

### GitNexus Protocol (MANDATORY)
- **Before edit**: `gitnexus_impact({target: "symbol", direction: "upstream"})`
- **Before commit**: `gitnexus_detect_changes()`
- **Warning required**: If risk = HIGH/CRITICAL
- **Never**: Find-and-replace rename (use `gitnexus_rename`)

### Language
- All communication in Russian unless explicitly requested otherwise

## GitNexus Index Status
- **Repository**: dj-music-plugin
- **Last indexed**: 2026-09-03T16:39:01.880Z (today)
- **Branch**: mece/wave-2026-09-03
- **Commit**: c51079fd824b503ee5ebcfab7ebc997b2b8bf06b
- **Capabilities**: graph (ladybugdb ✓), fts (ladybugdb-fts ✓), vectorSearch (unavailable)

## Detected Contradictions

### 1. AGENTS.md Length Violation
- **Location**: `AGENTS.md:91` (router principle: "≈100 lines") vs `AGENTS.md:115` (actual: "~230 lines")
- **Impact**: Excessive context consumption by agents
- **Severity**: Medium (governance drift)

### 2. Version Consistency Check
- **AGENTS.md:4**: Version 1.12.0
- **pyproject.toml:3**: Version 1.12.0
- **Status**: Consistent ✓

### 3. FastMCP Version Pin
- **pyproject.toml:13**: `fastmcp[tasks,apps]>=3.2.4,<3.4`
- **Reason**: 3.4.x middleware refactor breaks ResponseCachingMiddleware (commented in pyproject.toml)
- **Status**: Intentional constraint, documented

## Recommendations for Other Cells

### Cell 02 — Audio Pipeline (`app/audio/`)
- Focus: librosa beat tracking, essentia analysis, demucs stem separation
- Key files: `app/audio/beatgrid.py`, `app/audio/stem_separation.py`, `app/handlers/render_*.py`
- Validate: numba ≥0.65 pin prevents segfault; essentia dev1389 wheel availability

### Cell 03 — DJ Domain (`app/domain/`, `app/schemas/`)
- Focus: Pure domain logic, Camelot/BPM/energy models, transition scoring
- Key files: `app/domain/transition_scoring.py`, `app/schemas/scoring.py`, `app/schemas/key_compatibility.py`
- Validate: No I/O in domain layer; import-linter boundaries enforced

### Cell 04 — MCP Server (`server.py`, `app/server/`, `app/tools/`, `fastmcp.json`)
- Focus: FastMCP v3 app wiring, DI, tool registration, lifespan, visibility
- Key files: `app/server/app.py`, `app/server/di.py`, `app/server/visibility.py`, `fastmcp.json`
- Validate: Middleware chain compatibility with pinned fastmcp <3.4

### Cell 05 — Providers & DB (`app/providers/`, `app/repositories/`, migrations/)
- Focus: Yandex Music/Beatport/Suno clients, SQLAlchemy repos, UoW, migrations
- Key files: `app/providers/yandex.py`, `app/repositories/unit_of_work.py`, `alembic.ini`
- Validate: Provider rate limits (YM 429 handling), transaction boundaries

### Cell 06 — Quality & Docs (`rules/`, `tests/`, `docs/`, `skills/`)
- Focus: Rule enforcement, test coverage ≥80%, documentation sync, skill accuracy
- Key files: `rules/*.md`, `tests/`, `docs/architecture.md`, `skills/*/SKILL.md`
- Validate: `make check` passes; skills match actual tool capabilities

## Verification
- Run `make check` to verify quality gates pass
- Run `gitnexus_query({search_query: "architecture"})` to confirm index freshness
- Check `git status` — only expected modified files: `.opencode/agents/dj-music.md`, `.opencode/opencode.json`, `AGENTS.md`, `CLAUDE.md`, `opencode.json`

## Blockers / Residual Risk
- **AGENTS.md bloat**: Should be refactored to ~100 lines with rules/ delegation (cell 06 scope)
- **Vector search unavailable**: Semantic code search limited to BM25+FTS
- **FastMCP <3.4 pin**: Blocks upstream features/fixes; revisit when middleware regression resolved
- **Essentia wheel**: dev1389 pinned; newer dev builds may drop CPython 3.12 wheels

## Session ID
Git commit: `c51079fd` (branch: `mece/wave-2026-09-03`)
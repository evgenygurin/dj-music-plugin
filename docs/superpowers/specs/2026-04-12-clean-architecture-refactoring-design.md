# Clean Architecture Refactoring — Design Spec

> Date: 2026-04-12
> Scope: Full structural refactoring of dj-music-plugin from layered architecture to Clean Architecture
> Scale: ~301 Python files, ~29K lines, 88 MCP tools

## Goal

Migrate the project from the current "5 bands" flat-layer architecture (`app/`) to a strict 4-layer Clean Architecture with src-layout (`src/dj_music_plugin/`). Enforce the Dependency Rule via import-linter contracts and CI tests. Eliminate all boundary violations (20 services importing ORM models directly). Group code by business domain within each layer.

## Current State

```text
app/                          # 301 files, 47 directories
├── core/                     # cross-cutting (config, constants, errors, utils)
├── controllers/              # MCP tools (88), prompts (6), resources (10), DI
├── services/                 # 35 flat service files + set/ + curation/ + workflows/
├── db/                       # models (15), repositories (20), migrations, session
├── entities/                 # 3 files (Entity, ValueObject, TrackFeatures)
├── transition/               # pure scoring (14 files)
├── optimization/             # GA, greedy, fitness (5 files)
├── camelot/                  # wheel math (1 file)
├── templates/                # set templates (2 files)
├── audit/                    # techno rules (1 file)
├── export/                   # M3U8, Rekordbox, JSON (5 files)
├── audio/                    # analyzers (18), pipeline, classification, core
├── ym/                       # Yandex Music client (4 files)
├── engines/                  # deck, mixer (5 files)
├── bootstrap/                # server assembly (7 files)
├── api/                      # REST wrapper (12 files)
└── schemas/                  # Pydantic DTOs (10 files)
```

### Key Problems

1. **No Dependency Rule enforcement**: services import `app.db.models` directly (20 violations)
2. **Mixed concerns**: pure domain logic (transition/, optimization/) at same level as infrastructure (ym/, audio/)
3. **No ports/interfaces**: services coupled to concrete implementations
4. **Flat services/**: 35 files without domain grouping
5. **No src-layout**: `app/` is importable without installation
6. **No domain events**: state changes not propagated cleanly
7. **Scattered DTOs**: schemas/ separate from their domain context

## Target Architecture

### 4 Concentric Layers

```text
┌─────────────────────────────────────────────────┐
│  PRESENTATION (mcp/)                            │
│  MCP tools, REST routes, middleware, DI wiring  │
├─────────────────────────────────────────────────┤
│  INFRASTRUCTURE (infrastructure/)               │
│  SQLAlchemy ORM, repos, YM client, audio,       │
│  analyzers, algorithms, cache, event bus        │
├─────────────────────────────────────────────────┤
│  APPLICATION (application/)                     │
│  Use case services, DTOs, mappers, UoW, ports   │
├─────────────────────────────────────────────────┤
│  DOMAIN (domain/)                               │
│  Entities, value objects, domain services,      │
│  events, ports (Protocol interfaces)            │
└─────────────────────────────────────────────────┘
  config/ + shared/ = cross-cutting (any layer can import)
```

### Dependency Rule

| Layer | Can import | Cannot import |
|---|---|---|
| domain/ | stdlib only | application, infrastructure, mcp, any framework |
| application/ | domain/ | infrastructure, mcp |
| infrastructure/ | domain/, application/ | mcp |
| mcp/ (presentation) | domain/, application/, infrastructure/ | — |
| config/ + shared/ | stdlib | any layer (but layers can import them) |

### Target Directory Structure

```text
dj-music-plugin/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── src/
│   └── dj_music_plugin/
│       ├── __init__.py
│       ├── main.py                         # Composition root
│       │
│       ├── domain/                         # LAYER 1: Pure business logic
│       │   ├── entities/                   # Identity-bearing aggregates
│       │   │   ├── track.py                # Track aggregate root
│       │   │   ├── playlist.py
│       │   │   ├── dj_set.py               # DJSet aggregate root
│       │   │   └── audio_features.py
│       │   ├── value_objects/              # Immutable, identity-less
│       │   │   ├── camelot_key.py          # CamelotKey + wheel logic
│       │   │   ├── bpm.py
│       │   │   ├── transition_score.py     # 6-component score
│       │   │   ├── energy_level.py
│       │   │   └── analysis_tier.py        # L1-L4 enum
│       │   ├── services/                   # Pure domain services (no I/O)
│       │   │   ├── harmonic_mixing.py      # Camelot compatibility rules
│       │   │   ├── transition_scoring.py   # 6-component scoring algorithm
│       │   │   └── set_constraints.py      # Set constraint validation
│       │   ├── events/                     # Domain events (frozen dataclasses)
│       │   │   ├── track_events.py
│       │   │   └── set_events.py
│       │   └── ports/                      # Protocol interfaces
│       │       ├── repositories.py
│       │       ├── audio_analyzer.py
│       │       ├── audio_loader.py
│       │       ├── set_builder.py          # SetBuildingStrategy Protocol
│       │       ├── music_provider.py       # External API port
│       │       └── analysis_cache.py
│       │
│       ├── application/                    # LAYER 2: Use cases
│       │   ├── services/                   # Application services
│       │   │   ├── track_service.py
│       │   │   ├── playlist_service.py
│       │   │   ├── set_builder_service.py  # Facade
│       │   │   ├── analysis_service.py
│       │   │   ├── transition_service.py
│       │   │   └── yandex_service.py
│       │   ├── dtos/                       # Pydantic v2 DTOs
│       │   │   ├── base.py
│       │   │   ├── track_dtos.py
│       │   │   ├── playlist_dtos.py
│       │   │   ├── set_dtos.py
│       │   │   ├── analysis_dtos.py
│       │   │   └── yandex_dtos.py
│       │   ├── mappers/                    # Entity ↔ DTO ↔ ORM conversion
│       │   │   ├── track_mapper.py
│       │   │   ├── playlist_mapper.py
│       │   │   └── set_mapper.py
│       │   └── uow.py                     # Unit of Work
│       │
│       ├── infrastructure/                 # LAYER 3: Adapters
│       │   ├── persistence/
│       │   │   ├── database.py             # Engine, session factory
│       │   │   ├── models/                 # ORM models (44 tables)
│       │   │   │   ├── base.py
│       │   │   │   ├── track_model.py
│       │   │   │   ├── playlist_model.py
│       │   │   │   ├── set_model.py
│       │   │   │   ├── audio_features_model.py
│       │   │   │   └── yandex_model.py
│       │   │   └── repositories/           # Concrete implementations
│       │   │       ├── base_repository.py  # SQLAlchemyRepository[T]
│       │   │       ├── track_repository.py
│       │   │       ├── playlist_repository.py
│       │   │       └── set_repository.py
│       │   ├── audio/                      # Audio analysis
│       │   │   ├── pipeline.py
│       │   │   ├── analyzers/              # 18 analyzers
│       │   │   ├── core/                   # framing, loader, spectral
│       │   │   ├── classification/         # mood classifier
│       │   │   ├── loader.py
│       │   │   └── batch_processor.py
│       │   ├── algorithms/                 # Set-building strategies
│       │   │   ├── greedy_set_builder.py
│       │   │   └── genetic_set_builder.py
│       │   ├── yandex/                     # YM API adapter
│       │   │   ├── client.py
│       │   │   └── mapper.py
│       │   ├── cache/
│       │   │   └── analysis_cache.py
│       │   └── event_bus.py
│       │
│       ├── mcp/                            # LAYER 4: Presentation
│       │   ├── server.py                   # FastMCP factory + middleware
│       │   ├── tools/                      # Grouped by domain
│       │   │   ├── _shared/
│       │   │   ├── tracks/
│       │   │   ├── playlists/
│       │   │   ├── sets/
│       │   │   ├── audio/
│       │   │   ├── yandex/
│       │   │   └── system/
│       │   ├── resources/
│       │   ├── prompts/
│       │   ├── middleware/
│       │   │   ├── logging.py
│       │   │   ├── error_handling.py
│       │   │   ├── rate_limiting.py
│       │   │   └── telemetry.py
│       │   └── dependencies.py             # Depends() factories
│       │
│       ├── config/
│       │   └── settings.py                 # pydantic-settings
│       │
│       └── shared/
│           ├── exceptions.py               # Exception hierarchy
│           ├── types.py                    # Type aliases
│           ├── logging.py                  # structlog config
│           └── utils.py                    # Time, GUID helpers
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   ├── seed_data.py
│   └── benchmark_pipeline.py
│
└── docs/
    └── architecture.md
```

## Key Patterns

### Ports & Adapters (Dependency Inversion)

- **Ports** defined in `domain/ports/` as `Protocol` classes
- **Adapters** in `infrastructure/` implement the ports
- Application layer depends only on ports, never on concrete adapters
- Wiring happens in `main.py` (composition root) and `mcp/dependencies.py`

### Unit of Work

- UoW owns `AsyncSession`, creates repositories bound to it
- Services call `commit()` once at end of successful operation
- Repositories call `flush()` only — never commit
- `expire_on_commit=False` for async safety

### Domain Events

- Entities collect events internally (`_events: list`)
- Events are frozen dataclasses (immutable facts)
- `collect_events()` extracts and clears pending events
- `event_bus.py` dispatches events to handlers in infrastructure

### Strategy Pattern for Set Building

- `domain/ports/set_builder.py` defines `SetBuildingStrategy` Protocol
- `infrastructure/algorithms/greedy_set_builder.py` implements greedy
- `infrastructure/algorithms/genetic_set_builder.py` implements GA
- Selection at composition root based on user request

### Value Objects

- `@dataclass(frozen=True)` for all VOs
- CamelotKey encapsulates wheel logic
- TransitionScore is immutable 6-component record
- BPM includes tolerance/matching logic

### DTOs (Pydantic v2)

- Inheritance: Base → Create → Update → Response
- `ConfigDict(from_attributes=True)` for ORM compatibility
- Centralized in `application/dtos/`

### MCP Tool Organization

- `FileSystemProvider` scans `mcp/tools/` recursively
- `BM25SearchTransform` for large tool catalogs
- Tools grouped by domain: tracks/, sets/, audio/, yandex/, system/
- Each tool is a standalone `@tool` decorated function with `Depends()`

## Dependency Rule Enforcement

### import-linter contracts

```ini
[importlinter:contract:domain-pure]
name = Domain must have zero framework imports
type = forbidden
source_modules = dj_music_plugin.domain
forbidden_modules = sqlalchemy, fastmcp, pydantic, librosa, httpx, essentia, numpy

[importlinter:contract:application-no-infra]
name = Application must not import infrastructure or MCP
type = forbidden
source_modules = dj_music_plugin.application
forbidden_modules = sqlalchemy, fastmcp, librosa, httpx, dj_music_plugin.infrastructure, dj_music_plugin.mcp

[importlinter:contract:infrastructure-no-mcp]
name = Infrastructure must not import MCP presentation
type = forbidden
source_modules = dj_music_plugin.infrastructure
forbidden_modules = fastmcp, dj_music_plugin.mcp
```

### AST-based CI test

```python
# tests/test_architecture.py
LAYER_RULES = {
    "domain": {"forbidden": ["sqlalchemy", "fastmcp", "pydantic", "librosa", "httpx"]},
    "application": {"forbidden": ["sqlalchemy", "fastmcp", "librosa", "httpx"]},
}
```

## Migration Strategy

### Phase 1: Foundation
- Create `src/dj_music_plugin/` structure
- Move `alembic/` to project root
- Set up `pyproject.toml` with src-layout
- Create `main.py` composition root

### Phase 2: Domain Layer
- Extract entities from `app/entities/` → `domain/entities/`
- Create value objects from inline logic (CamelotKey, BPM, TransitionScore)
- Move pure logic: transition/, optimization/, camelot/, templates/, audit/, export/ → domain/
- Define ports in `domain/ports/`
- Create domain events

### Phase 3: Infrastructure Layer
- Move ORM models: `app/db/models/` → `infrastructure/persistence/models/`
- Move repositories: `app/db/repositories/` → `infrastructure/persistence/repositories/`
- Move audio: `app/audio/` → `infrastructure/audio/`
- Move YM client: `app/ym/` → `infrastructure/yandex/`
- Implement ports with concrete adapters
- Move GA/greedy: `app/optimization/` → `infrastructure/algorithms/`

### Phase 4: Application Layer
- Create application services from `app/services/`
- Create DTOs from `app/schemas/`
- Create mappers
- Implement UoW pattern
- Remove all `from app.db.models` imports from services

### Phase 5: Presentation Layer
- Move MCP tools: `app/controllers/tools/` → `mcp/tools/` (grouped by domain)
- Move middleware, resources, prompts
- Create `mcp/server.py` factory
- Set up DI factories in `mcp/dependencies.py`
- Add BM25SearchTransform

### Phase 6: Cleanup & Enforcement
- Add import-linter contracts for all 4 layers
- Add AST-based architecture test
- Update all documentation (CLAUDE.md, docs/, rules/)
- Remove old `app/` directory
- Update CI/CD, Dockerfile, scripts

### Phase 7: Test Migration
- Restructure tests: unit/ → domain/ + application/ + infrastructure/
- Integration tests with real DB
- E2E tests with MCP client
- Verify all 1200+ tests pass

## Design Rationale

| Decision | Rationale |
|---|---|
| src/ layout | Python packaging consensus since 2025; prevents accidental imports |
| Protocol over ABC for ports | Structural subtyping; adapters don't import domain base classes |
| UoW with commit in services | SQLAlchemy official recommendation; explicit transaction boundaries |
| expire_on_commit=False | Required for async SQLAlchemy (MissingGreenlet otherwise) |
| Cursor/keyset pagination | O(1) at any depth vs O(n) for offset; index-friendly |
| BM25SearchTransform | Prevents context window flooding with 50+ tool schemas |
| FileSystemProvider | Zero-boilerplate tool registration; hot-reload in dev |
| Frozen dataclasses for VOs/events | Immutability + __eq__ + __hash__ for free |
| Strategy pattern for set building | Swap greedy ↔ GA at composition root without touching services |
| Domain events | Decouple state changes from side effects cleanly |

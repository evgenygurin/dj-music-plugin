# Refactor v2 — DJ Music Plugin Architecture Rewrite

> Branch: `worktree-refactor+v2`
> Started: 2026-04-09
> Goal: 5-band layered architecture (Core + Transport + Application + Domain + Persistence + Infrastructure) with strict dependency rule, generic polymorphic kernel, and FastMCP 3.x canonical patterns.

## Baseline (2026-04-09, before Phase 1)

| Metric | Value |
|---|---|
| Total LOC (`app/`) | 22,911 |
| Python files | 215 |
| God-files (>400 LOC) | 4 (`audio/pipeline.py` 668, `ym/client.py` 632, `mcp/prompts/workflows.py` 439, `services/reasoning_service.py` 431) |
| Duplicate shim modules | 4 (`core/seed.py`, `core/storage.py`, `services/set_service.py`, `services/curation_service.py`) |
| Tests | 1116 passed, 8 failed (pre-existing), 48 skipped |
| Pre-existing failures | 6× audio pipeline (process pool, librosa/essentia env), 1× YM 403, 1× sets_meta (PG localhost:5432) |
| Import-linter contracts | **4 kept, 0 broken** — architecture already healthy, refactor is structural |

## Phases

| # | Status | Phase | Commit |
|---|---|---|---|
| 0  | ✅ | Worktree + import-linter contracts (4) + Makefile `arch` target + baseline doc | `04faaaf` |
| 1  | ✅ | Remove duplicate shim modules (`core/seed`, `core/storage`, `services/{set,curation}_service.py`) | `0c8bbc5` |
| 2  | ✅ | `core/` cleanup: nest utilities under `core/utils/` (34 callers updated) | `4e6ec8d` |
| 3  | ✅ | `db/` package — move `models/` `repositories/` `migrations/` `seed.py` (101 callers) | `0d28201` |
| 4  | ✅ | Drop `domain/` wrapper — flat top-level packages (`transition` / `optimization` / `templates` / `audit` / `export`, 43 callers) | `00f0384` |
| 5  | ✅ | `schemas/` hoisted to top-level (was `core/schemas/`, 9 callers) | `0ef7dc5` |
| 6  | ✅ | `core/` slim: extract `camelot.wheel`, `transition.intent` (Band 3 pure) | `37f9f2a` |
| 6.5| ✅ | Final `core/` slim: kill `elicitation` shim, move `ym_filters` → `ym/`, `entity_resolver` → `controllers/tools/_shared/` | `fb371ef` |
| 7a | ✅ | `entities/` package + `Entity` / `ValueObject` base + move `TrackFeatures` (21 callers) | `d1362c5` |
| 8  | ✅ | `UnitOfWork` aggregator + `get_uow` factory in `controllers/dependencies.py` | `b029640` |
| 10a| ✅ | Split `controllers/prompts/workflows.py` (439 → 6 modules) | `cd8033b` |
| 10b| ✅ | Split `controllers/resources/reference.py` (398 → 3 modules) | `f0b8e1e` |
| 11 | ✅ | Rename `app/mcp/` → `app/controllers/` (43 callers) | `81f86bd` |
| 12 | ✅ | `serve_http.py` → `app/api/server.py` (Phase 1 of api/ creation) | `f0fbaa8` |
| 13 | ✅ | Visibility — already canonical: `ctx.enable_components` per-session (no work needed) | — |
| 14a| ✅ | `engines/` stubs: `BaseEngine`, `DeckEngine` state machine, `MixerEngine`, `audio_lifespan` | `6c3cae2` |
| 14b| ✅ | Wire `engines/` to MCP tool surface — `decks.py` (8) + `mixer.py` (3) + `monitoring.py` (1) | `968d538` |
| 14c| ✅ | mypy strict pass — 0 errors after Phase 14b polish | `b5b1009` |
| **Deferred (require dedicated sessions):** |
| 7b | ⏳ | Composite VOs for `TrackFeatures` (touches scorer math) | — |
| 9  | ⏳ | Services migration to DTO returns (per-service PR) | — |
| 10c| ⏳ | Split `ym/client.py` 632 LOC → `ym/endpoints/` | — |
| 10d| ⏳ | Split `audio/pipeline.py` 668 LOC (process pool semantics) | — |
| 15 | ⏳ | Real audio engines: `sounddevice` + `pedalboard` + `soundtouch` + `LibraryIndex` | — |

## Key architectural decisions

See `.claude/rules/fastmcp.md` and `.claude/rules/architecture.md` (TBD) for full reference.

- **5 bands + Core** (orthogonal cross-cutting)
- **No `domain/` package name** — flat top-level pure packages (transition, optimization, templates, mood, camelot, audit)
- **`engines/` top-level** for long-lived runtime (Band 2B)
- **Composite VO** for `TrackFeatures` (9 nested VOs instead of 80 flat fields)
- **Generic kernel:** `BaseMapper[TModel, TEntity]` + `BaseRepository[TModel, TEntity]` + `BaseCRUD[TEntity, TCreate, TUpdate, TRead]`
- **Lifespan composition** via `|` operator (`db | audio | ym | library_index`)
- **Single ASGI process:** FastAPI parent + `mcp.http_app()` mounted, stdio = separate proxy process
- **Per-session visibility** via `ctx.enable_components` (replaces custom `unlock_tools`)
- **Audio stack:** `sounddevice` + `pedalboard` + `soundtouch` + `soundfile` + `miniaudio` + `numpy`

## Import-linter contracts (locked invariants)

```text
✓ services-no-mcp        — services framework-agnostic (no fastmcp/app.controllers)
✓ transition-pure        — scoring has no DB/HTTP/MCP/SQLAlchemy/httpx deps
✓ optimization-pure      — GA/greedy/fitness pure
✓ utils-leaf             — utils never reach domain code
```

Run `make arch` (or `uv run lint-imports`) to verify on every change.

## Final state (after 18 commits)

| Metric | Baseline | After v2 | Δ |
|---|---|---|---|
| LOC `app/` | 22,911 | ~22,800 | −0.5% |
| Python files | 215 | 226 | +11 (engines + entities + tools) |
| God-files (>400 LOC) | 4 | 2 | −2 (workflows + reference split) |
| Duplicate shim modules | 4 | 0 | −4 |
| Slово `domain` как пакет | yes | **no** | ✅ |
| Top-level packages reflecting bands | mixed | **5 + Core + boundary** | ✅ |
| `entities/` package | — | ✅ | new |
| `engines/` package | — | ✅ | new |
| `api/` package | `serve_http.py` at root | `app/api/server.py` | ✅ |
| `UnitOfWork` | — | ✅ | new |
| Import-linter contracts | 0 | **4** | ✅ |
| MCP tools registered | 52 | **64** | +12 deck/mixer/monitoring |
| pytest (full) | 1116 P / 8 F (baseline) | **1111 P / 8 F (same baseline)** | 0 regressions |
| mypy strict | clean (215 files) | **clean (238 files)** | ✅ |
| ruff check | clean | clean | ✅ |
| End-to-end tool tests | partial | **115 invocations** (105 pass + 7 skip + 3 pre-existing fail) | ✅ |

## Final structure

```text
app/
├── core/              # Band 0 — config, constants, errors, utils, middleware
├── controllers/       # Band 1 — MCP tools/prompts/resources, dependencies, middleware
├── api/               # Band 1 — FastAPI REST wrapper
├── schemas/           # Band 1 — Pydantic DTOs
├── services/          # Band 2A — request-scoped use cases
├── engines/           # Band 2B — long-lived runtime singletons (NEW)
├── entities/          # Band 3 — pure dataclass domain (NEW)
├── transition/        # Band 3 — 6-component scoring (was app/domain/transition/)
├── optimization/      # Band 3 — GA/greedy/fitness (was app/domain/optimization/)
├── templates/         # Band 3 — set templates (was app/domain/templates/)
├── audit/             # Band 3 — techno audit (was app/domain/audit/)
├── export/            # Band 3 — writers (was app/domain/export/)
├── camelot/           # Band 3 — wheel math (was app/core/camelot.py)
├── audio/             # Band 5 — analysis pipeline (analyzers, classification)
├── ym/                # Band 5 — Yandex Music client
├── infrastructure/    # Band 5 — storage backend
└── db/                # Band 4 — models/, repositories/, migrations/, seed
```

## Documentation status

After Phase 14c, all docs reflect the new structure:
- `CLAUDE.md` — updated layout, commands, dependency rule
- `.claude/rules/*.md` — 7 files updated
- `docs/architecture.md`, `docs/structure.md`, `docs/tool-catalog.md`, `docs/transition-scoring.md`, `docs/panel-guide.md`, `docs/audio-schema.md`, `docs/sync-service-api-design.md`, `docs/agent-prompts.md` — paths updated

Historical docs preserved as-is (`docs/reports/*`, `docs/superpowers/specs/*`, `docs/research/*`).

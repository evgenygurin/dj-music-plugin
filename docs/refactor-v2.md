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

| # | Status | Phase | LOC delta |
|---|---|---|---|
| 0 | ✅ | Worktree + import-linter setup + baseline | +importlinter, +Makefile target |
| 1 | ✅ | Remove duplicate shim modules | −42 LOC |
| 2 | 🚧 | core/ cleanup (utils nested, middleware, lifespan skeleton) | TBD |
| 3 | ⏳ | db/ package (move models, repositories, migrations) | TBD |
| 4 | ⏳ | Generic Band 4 base classes (BaseMapper, BaseRepository, BaseCRUD, UoW) | +565 LOC kernel |
| 5 | ⏳ | entities/ package with composite VOs | TBD |
| 6 | ⏳ | Pure Band 3 packages (transition, optimization, templates, mood, camelot, audit) | rename only |
| 7 | ⏳ | services migration to DTO returns (per-service PRs) | TBD |
| 8 | ⏳ | Split god-files (yandex, audio pipeline, reasoning, workflows, reference) | redistribution |
| 9 | ⏳ | api/ + mounted mcp.http_app() (single ASGI process) | TBD |
| 10 | ⏳ | Visibility refactor (per-session ctx.enable_components) | −80 LOC custom |
| 11 | ⏳ | engines/ stubs + playback drivers + deck tools | new |
| 12 | ⏳ | Real engines impl + LibraryIndex | new |

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
✓ services-no-mcp        — services framework-agnostic
✓ transition-pure        — scoring has no DB/HTTP/MCP deps
✓ optimization-pure      — GA/greedy/fitness pure
✓ utils-leaf             — utils ≠ domain code
```

Run `make arch` or `uv run lint-imports` to verify on every change.

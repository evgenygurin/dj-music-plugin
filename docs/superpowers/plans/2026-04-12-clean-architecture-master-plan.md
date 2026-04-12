# Clean Architecture Refactoring — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each phase plan.

**Goal:** Restructure dj-music-plugin from flat `app/` monolith to Clean Architecture with flat top-level packages in `src/dj_music/`.

**Architecture:** Entity-First (schemas = entities), flat packages (no infrastructure/presentation/application wrappers), dependency rule enforced by import-linter. Pydantic everywhere, BaseRepository[TModel, TSchema] generic.

**Tech Stack:** Python 3.12+, FastMCP 3.x, SQLAlchemy 2.0, Pydantic v2, structlog, asyncpg

**Spec:** `docs/superpowers/specs/2026-04-12-clean-architecture-refactoring-design.md`

---

## Phase Overview

Each phase is a separate plan, independently executable, producing working code with green tests.

| Phase | Plan File | Description | Files | Est. |
|-------|-----------|-------------|-------|------|
| 0 | `phase-0-setup.md` | Root package `src/dj_music/`, pyproject.toml, ghost dir cleanup | ~10 | 30m |
| 1 | `phase-1-core.md` | `core/` — config split, errors, constants, camelot, utils, logging, observability | ~15 | 1h |
| 2a | `phase-2a-schemas.md` | `schemas/` — BaseEntity, BaseFilter, BaseSort, BasePagination + all entity schemas | ~12 | 2h |
| 2b | `phase-2b-domain-logic.md` | Move transition/, optimization/, export/, templates/ to top-level | ~50 | 1h |
| 3 | `phase-3-repositories.md` | `repositories/` — BaseRepository[TModel, TSchema], ports.py, UoW, session | ~25 | 2h |
| 4 | `phase-4-services.md` | `services/` — remove ORM imports, depend on ports | ~30 | 2h |
| 5 | `phase-5-tools.md` | `tools/`, `prompts/`, `resources/`, `middleware/` — MCP presentation layer | ~65 | 2h |
| 6 | `phase-6-infra.md` | `models/`, `ym/`, `audio/`, `engines/`, `api/` — infrastructure + runtime | ~45 | 1.5h |
| 7 | `phase-7-di-server.md` | `di/`, `server.py` — DI composition root + entry point + import-linter | ~10 | 1h |
| 8 | `phase-8-cleanup.md` | Remove shims, ghost dirs, update CLAUDE.md, docs, tests, migrations path | ~10 | 1h |

**Total:** ~260 files, ~12 hours estimated

---

## Execution Order

Phases MUST be executed in order (0 → 1 → 2a → 2b → 3 → 4 → 5 → 6 → 7 → 8).

Each phase:
1. Creates new files in `src/dj_music/`
2. Adds re-export shims in `app/` for backward compat
3. Updates tests to import from new paths
4. Runs `make check` (lint + typecheck + arch + tests)
5. Commits

Phase 8 removes all shims and the `app/` package.

---

## Migration Strategy: Re-export Shims

Each moved module gets a re-export shim in the old location:

```python
# app/core/errors.py (shim — will be removed in Phase 8)
from dj_music.core.errors import *  # noqa: F401,F403
```

This ensures:
- All 300+ existing imports continue to work during migration
- Tests stay green after each phase
- Panel (Next.js) REST API paths unchanged
- MCP tool names unchanged

---

## ⚠️ ОБЯЗАТЕЛЬНО перед каждой фазой

1. Изучить соответствующие FastMCP docs из спеки (секция "ОБЯЗАТЕЛЬНАЯ документация")
2. Прочитать текущее состояние файлов перед перемещением
3. Запустить `make check` перед И после каждого PR
4. НЕ менять бизнес-логику — только moves + import rewrites

---

## Phase Plans (создаются отдельно)

Каждый phase plan содержит:
- Точные файлы (create/modify/delete)
- Полный код каждого шага
- Команды запуска тестов
- Команды коммита

Начинаем с Phase 0.

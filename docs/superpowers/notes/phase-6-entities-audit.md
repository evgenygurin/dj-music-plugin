# Phase 6 — `app/entities/` delete-candidate audit

> Task 14 of `docs/superpowers/plans/2026-04-17-phase-6-domain-audio.md`.
> No deletions here — this document records what Phase 7 should remove.

## Legacy tree inventory

```text
app/entities/
├── __init__.py              # re-exports Entity, ValueObject, HasId, HasTimestamps
├── base.py                  # (empty re-export; real definitions in __init__.py)
├── audio/
│   ├── __init__.py
│   └── features.py          # TrackFeatures dataclass (179 lines)
└── value_objects/
    └── __init__.py          # (empty)
```

Every file is small; the whole package is ~200 meaningful LOC.

## v2 replacement status

| Legacy symbol | Legacy path | v2 replacement | v2 path |
|---|---|---|---|
| `Entity` base | `app/entities/__init__.py` | not needed (v2 uses plain dataclasses, no identity-eq base) | — |
| `ValueObject` base | `app/entities/__init__.py` | not needed (v2 uses `@dataclass(frozen=True, slots=True)` directly) | — |
| `HasId` / `HasTimestamps` protocols | `app/entities/__init__.py` | not needed (Pydantic v2 models carry these via ORM schemas) | — |
| `TrackFeatures` | `app/entities/audio/features.py` | **`TrackFeatures` (ported)** | `app/v2/domain/transition/features.py` |

## Live references to `app.entities.*` (legacy only)

38 files, none under `app/v2/` (verified: `grep -R "from app.entities" app/v2/` returns nothing).

Grouped by package:

- `app/transition/**` — scorer + components + recipe_engine + neural_mix + style + hard_constraints (11 files)
- `app/optimization/**` — genetic, greedy, fitness, protocol (4 files)
- `app/services/**` — set/builder, prefetch_service (2 files)
- `app/db/repositories/**` — feature.py, candidate.py (2 files)
- `tests/**` — legacy tests still green (kept intentionally)
- `scripts/**` — transition_alignment_benchmark.py
- `docs/**` — plan/spec references (fine to leave)

## Delete-candidates for Phase 7

All of `app/entities/` is a delete-candidate **after** Phase 7 removes its legacy consumers.

Deletion sequence Phase 7 should follow:

1. First delete `app/transition/`, `app/optimization/`, `app/services/`, `app/db/repositories/feature.py`, `app/db/repositories/candidate.py`, `app/services/prefetch_service.py`, and the corresponding `tests/test_transition/`, `tests/test_domain/`, `tests/test_optimization/`, `tests/test_services/test_transition*`, `tests/test_services/test_fitness*`, `tests/test_services/test_set_*`, `tests/test_services/test_optimizer*`, `tests/test_services/test_prefetch*`, `tests/test_audio/test_pipeline_refactored.py`, `scripts/transition_alignment_benchmark.py`.
2. Then `app/entities/` has zero in-tree consumers and can be removed wholesale:
   - `rm -rf app/entities/`
3. Finally, delete `tests/v2/domain/transition/test_*_parity.py` — the parity harness only has value while BOTH implementations exist.

## Do NOT delete before Phase 7

- `app/entities/audio/features.py` — legacy transition/optimization still imports `TrackFeatures` from here; removing it breaks 38 files.
- `app/entities/__init__.py` — same reason (Entity/ValueObject bases).

## Notes

- `app/entities/base.py` is effectively dead (the real base classes are defined inline in `__init__.py`). It could be deleted even before Phase 7, but the gain is ~0 and the risk of a missed import is nonzero. Leave it.
- `app/entities/value_objects/__init__.py` is empty. Same story — safe to leave until Phase 7.
- No `app/entities/` file is imported from `app/v2/` (Task 14 audit), which satisfies the v2-backflow-gate contract direction (legacy → v2 forbidden; v2 → legacy also de facto absent).

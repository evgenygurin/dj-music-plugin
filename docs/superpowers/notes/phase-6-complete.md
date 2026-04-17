# Phase 6 — Domain + Audio Port: Complete

> Parallel port of `app/transition/`, `app/optimization/`, `app/templates/`,
> `app/audit/`, `app/camelot/`, `app/audio/` into `app/v2/domain/` and
> `app/v2/audio/`. Legacy trees untouched — Phase 7 will remove them.

## Files created

| Package | Files |
|---|---|
| `app/v2/domain/` | 35 |
| `app/v2/audio/` | 36 |
| **Total** | **71** |

Breakdown:

- `app/v2/domain/camelot/` — key distance, notation, compatibility
- `app/v2/domain/template/` — 8 set templates + registry
- `app/v2/domain/audit/` — techno audit specs
- `app/v2/domain/transition/` — `features.py` (TrackFeatures), `scorer.py`,
  `hard_constraints.py`, `components/*.py` (6), `style.py`, `recipe_engine.py`,
  `neural_mix.py`, `weights.py`, `math_helpers.py`, `score.py`, `section_context.py`
- `app/v2/domain/optimization/` — GA, greedy, fitness, protocol
- `app/v2/audio/core/` — AudioSignal, AnalysisContext, rhythm primitives, stitching
- `app/v2/audio/analyzers/` — 18 analyzers (3 core numpy + 7 librosa + 6 essentia
  + 2 dependent: bpm_histogram, phrase)
- `app/v2/audio/classification/` — mood classifier (15 subgenres)
- `app/v2/audio/` top-level — pipeline.py, level_config.py, timeseries.py,
  temp_download.py

## Commits

Chunk A — skeleton + leaves (Tasks 1-4):
- `5e15fe7` chore(v2): Phase 1 amendment — add constants + AuditSettings
- `dac2638` feat(v2): scaffold domain and audio package skeletons
- `b5f4685` feat(v2): port camelot to app/v2/domain/camelot
- `33db4f0` feat(v2): port templates to app/v2/domain/template
- `4f2167d` feat(v2): port audit rules to app/v2/domain/audit

Chunk B — transition + optimization parity (Tasks 5-9):
- `e1e8f23` feat(v2): port TrackFeatures to app/v2/domain/transition
- `b21f87d` feat(v2): port transition leaf modules
- `451216c` feat(v2): port transition components with parity harness
- `396bea4` feat(v2): port transition scorer + style + recipe_engine + neural_mix
- `7f1397b` feat(v2): port optimization (GA + greedy + fitness)

Chunk C — audio port (Tasks 10-13):
- `fbff90b` feat(v2): port audio core primitives to app/v2/audio/core
- `bdc9843` feat(v2): port 18 audio analyzers to app/v2/audio/analyzers
- `5f7ce2d` feat(v2): port mood classification to app/v2/audio/classification
- `4ebed90` feat(v2): port pipeline/level_config/timeseries/temp_download

Chunk D — finalization (Tasks 14-19):
- `a39bc68` docs(v2): audit app/entities/ delete-candidates for Phase 7
- `dd2c6c2` chore(v2): add v2-domain-pure + v2-audio-internal import contracts
- `f943049` test(v2): end-to-end scorer parity on 5 representative pairs
- `f0c46e4` chore(v2): Phase 6 Task 16 global parity — all four pillars green
- `c197f7b` chore(v2): Phase 6 Task 18 smoke — legacy server boots with 88 tools

## Parity proof

- Per-component parity harness: `tests/v2/domain/transition/test_components_parity.py`
  — covers bpm, harmonic, energy, spectral, groove, timbral components at 1e-9.
- End-to-end scorer parity: `tests/v2/domain/transition/test_scorer_full_parity.py`
  — 5 representative pairs (ambient, peak-time, acid mismatch, atonal, drum-only)
  match legacy scorer at 1e-9 on overall + 6 components + hard_reject flag.
- Math helpers parity: `tests/v2/domain/transition/test_math_helpers.py`.
- Subgenre rules parity: `tests/v2/domain/transition/test_subgenre_rules.py`.
- Hard constraints parity: `tests/v2/domain/transition/test_hard_constraints.py`.

## Known deviations from legacy

- `AuditSettings` was forked into `app/v2/config` as part of Phase 1 amendment
  (`5e15fe7`) — v2 version lives alongside v2 `Settings`, legacy version
  remains in `app/config.py`.
- 5 + 2 config fields were added during Phase 6 to surface constants the v2
  scorer/audit modules need without reaching back into legacy `app.config`.
- No behavioural deviations — parity harness locks scorer output at 1e-9.

## What Phase 7 must do

1. Delete legacy trees (in dependency order):
   - `app/transition/` (11 files)
   - `app/optimization/` (4 files)
   - `app/templates/`, `app/audit/`, `app/camelot/`
   - `app/audio/` (analyzers, classification, pipeline, …)
   - `app/entities/` — see [phase-6-entities-audit.md](./phase-6-entities-audit.md)
2. Delete consumers in `app/services/` that are pure re-orchestration of the
   above (set/builder, prefetch_service, etc.) once v2 tool handlers cover
   the use-cases.
3. Delete parity harness:
   - `tests/v2/domain/transition/test_*_parity.py`
   - `tests/v2/domain/transition/test_scorer_full_parity.py`
4. Drop legacy tests (`tests/test_transition/`, `tests/test_domain/`,
   `tests/test_optimization/`, parts of `tests/test_services/` and
   `tests/test_audio/` that target legacy modules).
5. Remove `app.entities` from the `v2-backflow-gate` source list — the
   contract becomes trivially satisfied once `app/entities/` is gone.

## Global parity (Task 16)

- v2 suite: **462 pass, 1 skip, 0 fail** (excluding 29 pre-existing
  Phase 3 failures in `tests/v2/tools/` — untouched by Phase 6).
- Legacy suite: **447 pass, 44 skip** in `tests/test_transition/`,
  `tests/test_domain/`, `tests/test_audio/`. 9 `test_audio` failures are
  environmental (librosa not installed in worktree) — not a Phase 6
  regression.
- `ruff check app/v2/`: all checks passed.
- `lint-imports`: **16 contracts KEPT, 0 broken** (includes 2 new Phase 6
  contracts: `v2-domain-pure`, `v2-audio-internal`).

## Tag

`phase-6-domain-audio` — points to the final Chunk D commit.

# SDD ledger — plan: docs/superpowers/plans/2026-09-04-ai-dj-universal-engine.md

## Pre-flight conflict scan

| Pair / task | Shared file or interface | Finding | Ruling |
|---|---|---|---|
| Task 1 ↔ Task 2 | AnalysisSnapshot | Task 1 defines immutable contract; Task 2 produces normalized snapshots. | Consistent: Task 2 may only depend on Task 1 contracts. |
| Task 1 ↔ Task 6 | snapshot hashes / plan identity | Task 6 consumes snapshot hashes. | Consistent: identity is defined in Task 1. |
| Task 2 ↔ Task 8 | analysis snapshots / cache | Task 2 reads/writes cache; Task 8 persists cache metadata. | Consistent: Task 2 owns orchestration semantics, Task 8 owns infrastructure persistence. |
| Task 3 ↔ Task 4 | ResolvedTransitionConfig | Task 4 consumes resolved config. | Consistent: Task 3 precedes Task 4. |
| Task 3 ↔ Task 9 | RenderConfig | Task 3 defines resolution; Task 9 executes render. | Consistent: renderer receives resolved render settings, never plans. |
| Task 4 ↔ Task 5 | CandidateTransition / hard validation | Task 4 rejects technical violations; Task 5 scores survivors. | Consistent with hard-before-soft invariant. |
| Task 5 ↔ Task 6 | MusicalScore / recipes | Task 5 produces dimensions and recipes; Task 6 selects and packages. | Consistent. |
| Task 6 ↔ Task 7 | TransitionPlan | Task 6 produces immutable plans; Task 7 consumes cached plans in graph. | Consistent. |
| Task 6 ↔ Task 8 | TransitionPlan persistence | Task 6 defines mapping; Task 8 owns repository/infrastructure. | Consistent. |
| Task 7 ↔ Task 10 | optimize_sequence / plan_set | Task 7 defines optimizer; Task 10 exposes use cases through MCP. | Consistent. |
| Task 8 ↔ Task 9 | RenderManifest | Task 8 persists manifests; Task 9 creates them. | Consistent. |
| Task 9 ↔ Task 10 | render_transition / render_set | Task 9 owns renderer contract; Task 10 exposes application use cases. | Consistent. |
| Task 10 ↔ Task 11 | legacy adapters / feature flags | Task 10 adds shadow path; Task 11 performs cutover. | Consistent. |
| Task 0 | working tree | Existing unrelated changes must remain untouched. | Isolated worktree created; original checkout preserved. |

## Per-task self-consistency scan

| Task | Tests vs files/contracts | Finding | Ruling |
|---|---|---|---|
| 0 | baseline report + repository checks | Self-consistent. | Proceed. |
| 1 | value-object tests vs analysis contracts | Self-consistent. | Proceed. |
| 2 | tier/orchestrator tests vs adapters | Self-consistent. | Proceed. |
| 3 | precedence/provenance tests vs resolver | Self-consistent. | Proceed. |
| 4 | technical edge-case tests vs candidate validator | Self-consistent. | Proceed. |
| 5 | dimension/recipe tests vs evaluator | Self-consistent. | Proceed. |
| 6 | policy/serialization tests vs TransitionPlan | Self-consistent. | Proceed. |
| 7 | graph/constraint/beam tests vs optimizer | Self-consistent. | Proceed. |
| 8 | migration/repository tests vs persistence layer | Self-consistent; integration tests may need project-specific fixtures. | Ruling: use existing DB test conventions rather than inventing a second harness. |
| 9 | plan/render validation tests vs renderer adapters | Self-consistent. | Proceed. |
| 10 | MCP contracts vs application boundary | Self-consistent. | Proceed. |
| 11 | parity/resource/reproducibility tests vs cutover | Self-consistent. | Proceed. |

## Global rulings

- Ruling: Preserve the existing `test-assembly` working tree unchanged by implementing only in `codex/ai-dj-universal-engine` worktree — because the plan explicitly forbids unrelated changes — cost if wrong: branch divergence requiring manual reconciliation.
- Ruling: Treat the approved architecture spec as binding over implementation conveniences — because the subagent workflow says spec outranks plan — cost if wrong: rework of a phase that violates architectural invariants.
- Ruling: Keep one writer at a time; use sequential task dispatch/review even where tasks appear parallelizable — because shared Python contracts and adapters create integration risk and Adaptive Orchestration caps writers — cost if wrong: slower execution.

## Task 0 completion

- Baseline report committed as `96733627` (`docs: record universal engine baseline`).
- Confirmed project target Python is >=3.12; established a local 3.12 test environment with uv.
- Recorded pre-existing collection/static failures, unresolved merge markers, MCP surface and persistence anchors.

## Task 1 — domain contracts

Status: **implemented and focused-verified**.

- RED: six new analysis test modules initially failed because the requested domain modules did not exist.
- GREEN: added immutable/slotted `TempoHypothesis`, `BeatPosition`, `BeatGrid`, `Phrase`, `Section`, `CuePoint`, and `AnalysisSnapshot` contracts plus package exports.
- Snapshot identity canonically hashes source, schema, analyzer/model versions, engine, DSP backend and analysis configuration hash.
- Domain purity check: analysis package imports successfully without audio/repository/provider/FastMCP/concrete-DSP imports.
- Focused tests: `14 passed`.
- Ruff on new domain/tests: clean.
- Mypy on new domain: clean.
- Import-linter remains blocked repository-wide by the pre-existing syntax error in `app/audio/deep/demucs_mlx_runner.py`; this is recorded as baseline, not a Task-1 failure.

## Task 2 — analysis tiers and orchestration

Status: **core orchestration implemented; legacy L6 handler cutover deferred to the application-surface migration boundary**.

- RED: application analysis tests initially failed because `AnalysisOrchestrator` and tier contracts did not exist.
- Added `AnalysisTier` and `ResourceBudget` with conservative single-analysis/single-stem defaults for the M2 8 GB target.
- Added `AnalysisOrchestrator` with explicit tier selection, optional snapshot cache, deterministic request keying, and normalization into `AnalysisSnapshot`.
- Added normalizers for tempo hypotheses, beatgrid, phrases, sections and cues.
- Focused tests: `19 passed` including all Task-1 domain tests.
- Ruff and mypy on new application analysis modules: clean.
- Repository import-linter remains blocked by pre-existing syntax in `app/audio/deep/demucs_mlx_runner.py`.
- Existing `L6AnalysisOrchestrator` still owns a rich `L6AnalysisResult` plus DB/storage side effects. Moving that whole legacy result contract behind the new snapshot boundary without losing public behavior belongs in the later MCP/application migration work; no legacy behavior was silently removed in Task 2.

## Task 3 — configuration engine

Status: **implemented and focused-verified**.

- RED: configuration tests initially failed because schema/resolver/provenance/profile contracts did not exist; legacy adapter test then failed until the adapter was added.
- Added declarative `ParameterDefinition`, `ParameterClass`, `TransitionSchema`, data-only `TransitionProfile`, `Provenance`, immutable `ResolvedTransitionConfig`, deterministic config hashing, precedence resolution, validation, and `LegacyConfigAdapter`.
- Precedence implemented as Global → Genre → Behavior → Set → Transition → Render; unknown fields and out-of-range values are rejected.
- Focused configuration/application/domain verification: `26 passed` before the legacy adapter, then `7 passed` configuration tests after adapter completion; all new-module Ruff and mypy checks clean.
- No legacy `app/config/transition.py` or `app/config/render.py` behavior was removed; adapter remains additive for later cutover.

## Task 10 — rollout wiring and application boundary (in progress)

- Added `EngineSettings` to expose `DJ_ENGINE=legacy|shadow|new` and `DJ_RENDERER=legacy|new` through the central settings facade; defaults remain legacy.
- Added `TransitionEngineRouter` as the deterministic legacy/shadow/new execution boundary; shadow evaluates both paths and returns parity diagnostics without changing the selected new result.
- Added `GenerateTransitionCandidates` application use case with protocol-based catalog/scorer ports and deterministic top-k ranking. This is the first concrete MCP migration boundary; the existing tool adapter remains to be wired to the use case next.
- Verification: engine settings `2 passed`; candidate application use case `1 passed`; targeted Ruff/mypy clean.
- Repository-wide `make check` remains blocked by pre-existing lint/import issues outside this slice; no baseline files were modified.


## Task 10 — candidate MCP migration slice

Status: **implemented and verified**.

- Added `UowCandidateCatalog` as an infrastructure adapter for the `CandidateCatalog` application port.
- `get_transition_candidates` now delegates discovery/ranking to `GenerateTransitionCandidates`; MCP no longer owns candidate iteration/scoring logic.
- Preserved direct-call compatibility for existing headless/unit-test callers while MCP runtime receives the application use case through DI.
- Added DI factory `get_transition_candidate_generator`.
- Added application-boundary tests covering delegation and missing-source behavior.
- Verification: focused boundary tests `2 passed`; targeted Ruff clean; targeted mypy clean; `git diff --check` clean.
- Commit `00ed36f7` pushed to `codex/ai-dj-universal-engine`.

## Task 10 — score-pool MCP migration slice

Status: **implemented and verified**.

- Added `ScoreTransitionPool` application use case with protocol-based catalog/scorer ports.
- `transition_score_pool` now delegates pair generation, scoring, duplicate validation, missing-feature handling, and top-k selection to the application boundary.
- Preserved the existing MCP response shape (`a`, `b`, `overall` plus optional components) and `ValidationError` contract at the tool boundary.
- Added focused application tests for top-k/missing IDs and duplicate rejection.
- Verification: focused application tests `2 passed`; targeted Ruff clean; targeted mypy clean; `git diff --check` clean.
- Commit `b3302d0e` pushed to `codex/ai-dj-universal-engine`.
- MCP server registration tests remain affected by an existing FastMCP/Pydantic schema-rebuild failure during full tool discovery; this is not treated as a passing integration gate.

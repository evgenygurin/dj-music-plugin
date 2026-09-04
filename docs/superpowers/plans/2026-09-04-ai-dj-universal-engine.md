# Universal AI DJ Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incrementally transform the existing DJ Music Plugin into the universal, technically constrained, musically aware, explainable and plan-driven AI DJ engine defined by the approved architecture spec.

**Architecture:** Preserve the current working pipeline and introduce explicit domain contracts around it. Normalize existing analysis into versioned snapshots, resolve declarative configuration before planning, generate and validate transition plans before sequence optimization, and make rendering consume immutable plans. Every phase keeps legacy adapters/shadow paths until regression and resource gates pass.

**Tech Stack:** Python >=3.12, Pydantic v2, dataclasses, NumPy/librosa/Essentia where already present, SQLAlchemy 2 async, Supabase PostgreSQL/Storage, pgvector, FastMCP 3.x, existing Demucs/MLX stem stack, pytest/pytest-asyncio/xdist, ruff, mypy, import-linter.

**Spec:** `docs/superpowers/specs/2026-09-04-ai-dj-universal-engine-design.md`

## Global Constraints

- Preserve existing analyzers and migrate them through adapters; do not rewrite the audio stack in one operation.
- Domain code must not depend on Supabase, MCP, Demucs, FFmpeg, torch or concrete DSP implementations.
- Hard technical constraints always reject; soft objectives can never compensate for a hard violation.
- Heavy stem/deep analysis runs only after cheap candidate reduction.
- `TransitionPlan` and `SetPlan` are immutable, serializable contracts.
- Renderer never selects BPM, cue, duration, recipe or musical intent.
- Optimizer never runs DSP or re-analyzes audio.
- MCP exposes application use cases rather than concrete analyzers.
- Configuration is declarative data with provenance; profiles are presets, not engines.
- Cache identities include source/config/schema/version information sufficient for invalidation and reproducibility.
- Target development environment is an Apple Silicon M2 MacBook Air with 8 GB RAM; memory safety takes priority over concurrency.
- Existing tests and public MCP behavior are regression gates; no big-bang migration.
- Do not modify unrelated existing worktree changes (`.opencode/package.json`, `dj-music-plugin-cell16`) unless a task explicitly requires it.

## Baseline and working-state policy

The current branch is `test-assembly` and already contains unrelated working-tree changes. The executor must isolate implementation work from those changes before coding. If a clean feature worktree can be created safely, use `superpowers:using-git-worktrees`; otherwise create a dedicated feature branch without resetting or stashing user changes.

The current repository already contains 125 transition-domain test files/entries, 41 render-domain test files/entries, 77 audio test files/entries and 10 config test files/entries. Existing `app/domain/transition`, `app/domain/optimization`, `app/domain/render`, `app/audio`, `app/tools/compute`, and `app/handlers/l6_analysis_orchestrator.py` are integration anchors rather than disposable code.

## Target dependency graph

```text
Raw Audio
  -> AnalysisSnapshot
  -> CandidateTransition
  -> Technical Validation
  -> Alignment / Structure / Musical Evaluation
  -> TransitionPlan
  -> CandidateGraph
  -> SetState / Beam Search
  -> SetPlan
  -> Plan-driven Renderer
  -> RenderedAudioValidator / RenderManifest
```

## Phase gates

Every phase ends with focused tests plus repository-wide verification appropriate to its blast radius. A phase is not complete when code merely imports: its contracts, tests, compatibility behavior, resource usage and diagnostics must be demonstrated.

### Task 0: Baseline, isolation and inventory

**Files:**
- Create: `docs/superpowers/reports/2026-09-04-ai-dj-universal-engine-baseline.md`
- Inspect: `app/domain/transition/**`, `app/domain/optimization/**`, `app/domain/render/**`, `app/audio/**`, `app/config/**`, `app/tools/compute/**`, `app/tools/render/**`, `app/handlers/l6_analysis_orchestrator.py`, `.importlinter`, `pyproject.toml`
- Test: existing repository test suite and import-linter checks

**Interfaces:**
- Consumes: approved design spec and current repository state.
- Produces: reproducible baseline inventory, test/quality commands, known working-tree boundaries and compatibility checklist used by all later tasks.

- [ ] **Step 1:** Run `git status --short --branch`, record current branch and unrelated modifications; do not reset them.
- [ ] **Step 2:** Run the smallest safe baseline suite for transition, optimization, render, audio, config and handlers, plus `ruff check app tests`, `mypy app`, and import-linter; record exact pass/fail output and known pre-existing failures.
- [ ] **Step 3:** Inventory current MCP tool names and map each legacy operation to its current handler/domain implementation; record public response schemas that must remain compatible.
- [ ] **Step 4:** Inventory current analysis outputs, beatgrid persistence, section persistence, embeddings, stem cache and render artifacts; identify existing data that can feed `AnalysisSnapshot` without recomputation.
- [ ] **Step 5:** Write the baseline report with commands, results, file anchors, current performance/resource observations and explicit non-goals for unrelated worktree changes.
- [ ] **Step 6:** Commit only the baseline report on the isolated feature branch.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 1: Domain contracts: analysis and immutable snapshots

**Files:**
- Create: `app/domain/analysis/tempo.py`, `beatgrid.py`, `phrase.py`, `structure.py`, `cue.py`, `snapshot.py`
- Create: `tests/domain/analysis/test_tempo.py`, `test_beatgrid.py`, `test_phrase.py`, `test_structure.py`, `test_cue.py`, `test_snapshot.py`
- - Modify: `app/domain/__init__.py` only if package exports are needed

**Interfaces:**
- Produces: `TempoHypothesis`, `BeatPosition`, `BeatGrid`, `Phrase`, `Section`, `CuePoint`, and immutable `AnalysisSnapshot` value objects.
- Consumes: existing scalar/array analyzer outputs only through plain values; no audio or repository imports.

- [ ] **Step 1:** Write failing tests for multiple tempo hypotheses, beat/downbeat positions, phrase boundaries, section types, cue metadata and immutable snapshot construction.
- [ ] **Step 2:** Implement frozen/slotted value objects with explicit units, confidence and validation; keep large arrays referenced rather than copied into relational metadata objects.
- [ ] **Step 3:** Implement deterministic snapshot identity inputs for source hash, schema/analyzer/model/DSP versions and analysis configuration; expose a stable canonical hash function.
- [ ] **Step 4:** Run focused domain tests and import-linter; verify these modules import without `app.audio`, `app.repositories`, `app.providers`, `fastmcp` or concrete DSP packages.
- [ ] **Step 5:** Commit the contracts separately from later adapters.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 2: Analysis normalization and tiered orchestration

**Files:**
- Create: `app/application/analysis/orchestrator.py`, `app/application/analysis/normalizers.py`, `app/application/analysis/tiers.py`
- Create: `app/audio/beatgrid/adapter.py`, `app/audio/structure/adapter.py` if required by existing implementation boundaries
- - Modify: `app/handlers/l6_analysis_orchestrator.py` to delegate through the new application boundary
- Test: `tests/application/analysis/**`, existing `tests/audio/analyzers/**`, `tests/handlers/test_deep_analysis.py`

**Interfaces:**
- Produces: `AnalysisOrchestrator.analyze(track_id, tier, config) -> AnalysisSnapshot` and deterministic normalization adapters.
- Consumes: existing analyzer classes, existing beatgrid/deep-analysis persistence and storage ports; deep tier remains optional.

- [ ] **Step 1:** Write failing tests proving BASIC does not invoke Demucs, MIX_READY builds tempo/beatgrid/phrase/structure/cues, and DEEP is only requested explicitly or by a justified candidate policy.
- [ ] **Step 2:** Normalize existing analyzer outputs into the new domain objects; map current `TrackFeatures`, beatgrid metadata and sections without duplicating DSP.
- [ ] **Step 3:** Add analysis cache lookup keyed by source/config/schema/model/DSP identity; return an existing valid snapshot instead of rerunning analyzers.
- [ ] **Step 4:** Introduce a resource budget object with maximum parallel analysis, stem jobs, memory, CPU/GPU and deep-candidate limits; fail or defer work when the budget is exceeded rather than oversubscribe the M2.
- [ ] **Step 5:** Route the current L6 handler through the orchestrator while preserving its existing result contract and storage side effects.
- [ ] **Step 6:** Run focused analysis/handler tests and a small deterministic audio fixture; verify no duplicate analyzer invocation when cache identity matches.
- [ ] **Step 7:** Commit the tiered orchestration and adapters.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 3: Configuration schema, profiles, resolver and provenance

**Files:**
- Create: `app/domain/configuration/schema.py`, `profile.py`, `resolver.py`, `validation.py`, `provenance.py`
- Create: `app/application/configuration/**` if an application facade is needed
- Create: `tests/domain/configuration/**`, `tests/application/configuration/**`
- - Modify: `app/config/transition.py`, `app/config/render.py` only through adapters; preserve existing settings compatibility

**Interfaces:**
- Produces: `TransitionProfile`, `ResolvedTransitionConfig`, `EffectiveConfiguration`, `ParameterDefinition`, `ConfigResolver`, and `LegacyConfigAdapter`.
- Consumes: global settings, declarative profile documents, behavior presets and set/transition/render override patches.

- [ ] **Step 1:** Write failing tests for global→genre→behavior→set→transition→render precedence, hard/boundary/soft/preference classification, provenance and deterministic hashes.
- [ ] **Step 2:** Implement schema validation with explicit ranges/types and reject unknown fields; represent overrides as patches, not duplicated full configs.
- [ ] **Step 3:** Implement profile and behavior presets as data-only declarations with limited one-level inheritance; ensure no profile contains executable Python business logic.
- [ ] **Step 4:** Implement legacy adapters mapping current transition/render settings to the resolved schema without changing existing public calls.
- [ ] **Step 5:** Implement incremental invalidation categories ANALYSIS, PLANNING and RENDER so render-only changes do not invalidate analysis or candidate graphs.
- [ ] **Step 6:** Expose an application-level `resolve_config` operation returning values, provenance, warnings, conflicts and hash.
- [ ] **Step 7:** Run config tests plus existing `tests/config/**` and verify legacy defaults remain compatible until the shadow cutover.
- [ ] **Step 8:** Commit the configuration engine.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 4: Candidate generation and hard technical validation

**Files:**
- Create: `app/domain/mixing/candidate.py`, `alignment.py`, `constraints.py`
- Create: `tests/domain/mixing/test_candidate.py`, `test_alignment.py`, `test_constraints.py`
- - Modify: current transition hard-constraint adapters under `app/domain/transition/**` only to delegate when safe

**Interfaces:**
- Produces: `CandidateTransition`, `ConstraintResult`, `AlignmentResult`, candidate generation and deterministic technical validation.
- Consumes: `AnalysisSnapshot` pairs and `ResolvedTransitionConfig`; produces no audio or repository side effects.

- [ ] **Step 1:** Write failing tests for 0.5x/1x/2x tempo hypotheses, beat/downbeat phase tolerance, phrase/bar alignment, pitch/time-stretch limits and accumulated drift over the actual transition duration.
- [ ] **Step 2:** Implement candidate generation from cue/section pairs, tempo hypotheses and allowed bar durations; keep candidates cheap and bounded before deep analysis.
- [ ] **Step 3:** Implement hard validation as an ordered technical gate. A hard violation must return an explicit rejection reason and must never be recoverable through a higher musical score.
- [ ] **Step 4:** Implement predicted drift from tempo mismatch over transition duration rather than comparing BPM scalars only; include both beat and millisecond margins.
- [ ] **Step 5:** Implement deterministic candidate IDs from source/target snapshot hashes, cues, hypotheses, duration and config hash.
- [ ] **Step 6:** Run focused tests including the known 128 vs 128.2 BPM long-transition drift case and verify the candidate is rejected when configured drift exceeds tolerance.
- [ ] **Step 7:** Commit candidate generation and hard validation.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 5: Musical evaluation, feature grouping and recipe engine

**Files:**
- Create: `app/domain/mixing/evaluation.py`, `recipes.py`, `recipe_validation.py`, `scores.py`
- Create: `tests/domain/mixing/test_evaluation.py`, `test_recipes.py`, `test_recipe_validation.py`, `test_scores.py`
- - Modify: `app/domain/transition/api.py` and current scorer adapters as compatibility facades, not as the new core

**Interfaces:**
- Produces: independent harmony/energy/low-end/spectrum/groove/timbre/vocal/stem dimensions, `MusicalScore`, `TransitionRecipe` and recipe validation.
- Consumes: validated candidates, `AnalysisSnapshot`, optional deep/stem features and resolved configuration.

- [ ] **Step 1:** Write failing tests proving hard-rejected candidates never reach musical ranking and that correlated spectral/low-end feature groups are normalized to avoid accidental double-counting.
- [ ] **Step 2:** Implement independent evaluators with explicit `DimensionScore` diagnostics and configurable weights; keep the scoring model decomposable rather than one giant `transition_score()` function.
- [ ] **Step 3:** Implement energy trajectory/section-aware scoring, harmonic confidence policies, low-end collision detection, groove/timbre comparisons and vocal overlap policy.
- [ ] **Step 4:** Implement stem-aware evaluation as an optional deep feature provider; do not trigger Demucs merely because the stem evaluator exists.
- [ ] **Step 5:** Implement recipe generation and independent recipe validation for FADE/EQ_BLEND/FILTER_BLEND/DRUM_SWAP/BASS_SWAP/STEM_BLEND/VOCAL_CUT/VOCAL_SUSTAIN/ECHO_OUT/LOOP_ROLL/HARD_CUT/DROP_SWAP/BREAKDOWN_TO_DROP/DROP_TO_DROP.
- [ ] **Step 6:** Run focused tests and current transition golden/parity tests; preserve a compatibility result through the legacy adapter while the new evaluator runs in shadow mode.
- [ ] **Step 7:** Commit musical evaluation and recipe planning.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 6: TransitionPlanner, decision diagnostics and persistence contract

**Files:**
- Create: `app/domain/mixing/plan.py`, `transition.py`, `selection.py`
- Create: `app/application/transition/planner.py`, `decision.py`
- Create: `tests/domain/mixing/test_plan.py`, `test_selection.py`, `tests/application/transition/test_planner.py`
- - Modify: `app/models/transition.py`, `app/repositories/transition.py`, related schemas only after contract tests exist

**Interfaces:**
- Produces: immutable `TransitionPlan`, `TransitionDecision`, alternatives/rejections and explainable diagnostics.
- Consumes: resolved config, validated candidates, alignment, musical dimensions and validated recipes.

- [ ] **Step 1:** Write failing tests for selection policies BEST, SAFEST, MOST_HARMONIC, MOST_ENERGETIC, MOST_GROOVY, MOST_CREATIVE, MOST_SMOOTH and EXPLICIT_PROFILE over the same candidate set.
- [ ] **Step 2:** Implement `TransitionPlan` as immutable and serializable, containing source/target cues/sections/hypotheses, duration, effective BPM, alignment, recipe, automation, constraints, scores and diagnostics.
- [ ] **Step 3:** Implement `TransitionDecision` with selected, alternatives, rejected and diagnostics; retain technical margins and rejection reasons so the decision is auditable.
- [ ] **Step 4:** Ensure selection policies can reorder acceptable candidates but cannot admit a hard-constraint violation.
- [ ] **Step 5:** Add persistence DTO/model mappings with schema/version/hash fields and backward-compatible reads for current transition records.
- [ ] **Step 6:** Run transition golden tests plus serialization round trips and deterministic reruns; verify equal execution identity produces byte-equivalent canonical plan serialization.
- [ ] **Step 7:** Commit the first end-to-end transition planner.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 7: CandidateGraph, SetState and Beam Search

**Files:**
- Create: `app/domain/sequence/state.py`, `graph.py`, `objective.py`, `constraints.py`, `optimizer.py`, `plan.py`
- Create: `app/application/sequence/**`
- Create: `tests/domain/sequence/**`, `tests/application/sequence/**`
- - Modify: `app/domain/optimization/protocol.py` and current strategies through adapters

**Interfaces:**
- Produces: `SetState`, `CandidateGraph`, `TransitionEdge`, `SetConstraints`, `SequenceObjective`, `BeamSearchOptimizer`, and immutable `SetPlan`.
- Consumes: cached `TransitionPlan` edges; never invokes audio analyzers or DSP.

- [ ] **Step 1:** Write failing tests for same-artist/release/track gaps, mandatory/excluded/fixed tracks, BPM/energy bounds and consecutive section/recipe constraints.
- [ ] **Step 2:** Implement `SetState` histories and dramaturgy state with energy/BPM/key/section/recipe/artist/genre/repetition context.
- [ ] **Step 3:** Implement `CandidateGraph` construction from cached transition plans and explicit missing-edge diagnostics; do not recompute DSP while optimizing.
- [ ] **Step 4:** Implement set objectives for energy/harmonic/novelty arcs, groove continuity, structural flow, recipe/artist diversity and repetition penalties without allowing diversity to force an invalid recipe.
- [ ] **Step 5:** Implement bounded Beam Search with configurable beam width/lookahead and deterministic tie-breaking; retain existing Greedy/Genetic strategies behind the common optimizer interface.
- [ ] **Step 6:** Implement immutable `SetPlan` with tracks, transitions, duration, curves, dramaturgy, alternatives and diagnostics.
- [ ] **Step 7:** Run sequence tests on synthetic candidate graphs and one small real-library fixture; measure memory and keep the graph bounded to configured top-K edges.
- [ ] **Step 8:** Commit the sequence planner.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 8: Persistence, cache and execution manifests

**Files:**
- Create: Alembic migration under `app/db/migrations/versions/` for additive analysis/plan/manifest structures
- Create: repositories for analysis snapshots, cue points, transition plans/edges, set plans and execution manifests
- Create: `app/infrastructure/cache/**`, `app/infrastructure/persistence/**`, `app/infrastructure/storage/**` adapters as needed
- Create: `tests/repositories/test_analysis_snapshot_persistence.py`, `test_plan_persistence.py`, `test_cache_identity.py`, `test_execution_manifest.py`

**Interfaces:**
- Produces: Postgres metadata/index persistence, Storage references for large artifacts, pgvector-compatible embedding identity and deterministic cache keys.
- Consumes: immutable domain contracts and Supabase/SQLAlchemy infrastructure.

- [ ] **Step 1:** Write failing migration/repository tests using SQLite-compatible metadata where possible and isolated Postgres integration markers where JSON/vector behavior requires Postgres.
- [ ] **Step 2:** Add tables/columns additively for analysis snapshots, tempo hypotheses, beatgrid metadata, phrases, sections, cue points, transition edges/plans, set plans and execution manifests; do not drop legacy structures.
- [ ] **Step 3:** Implement cache identity using source analysis hashes, resolved config hash, engine/schema/model/DSP versions and transition schema version.
- [ ] **Step 4:** Keep large waveform/time-series/stem/render artifacts in Supabase Storage references rather than embedding arrays in Postgres rows; retain pgvector for embeddings.
- [ ] **Step 5:** Implement dual-read and optional dual-write adapters so legacy records remain readable during migration; backfill only after schema validation passes.
- [ ] **Step 6:** Implement `ExecutionManifest` with config hash, engine/analyzer/renderer versions, model/DSP versions, source hashes and seed.
- [ ] **Step 7:** Run repository/migration tests and verify rollback is additive-safe; do not delete legacy data in this phase.
- [ ] **Step 8:** Commit persistence and cache infrastructure.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 9: Plan-driven renderer and post-render validation

**Files:**
- Create: `app/domain/mixing/automation.py`, `app/domain/render/plan_validator.py`, `app/domain/render/rendered_validator.py`, `app/domain/render/manifest.py`
- - Modify: `app/domain/render/models.py`, `plan_assembler.py`, `runner.py`, `app/handlers/_orchestrator/render_orchestrator.py`, `render_executor.py`
- - Modify: `app/tools/render/**` only after renderer contract tests pass
- Create: `tests/domain/render/test_plan_validator.py`, `test_rendered_validator.py`, `test_manifest.py`, plus regression updates under `tests/handlers/_orchestrator/**`

**Interfaces:**
- Produces: renderer input contract `TransitionPlan + RenderConfig + audio`, declarative `AutomationCurve`, `RenderedAudioValidator` and `RenderManifest`.
- Consumes: immutable `TransitionPlan`; may use existing FFmpeg/DSP/stem implementations only through infrastructure adapters.

- [ ] **Step 1:** Write failing tests proving renderer rejects invalid plans and never changes BPM, cues, duration or recipe internally.
- [ ] **Step 2:** Implement declarative automation curves with explicit parameter, start/end, duration, shape, bounds and safety constraints.
- [ ] **Step 3:** Adapt the existing classic/stem render paths so plan values drive tempo mapping, phase alignment, phrase synchronization, EQ/fader/stem/FX automation and master safety.
- [ ] **Step 4:** Implement pre-render plan validation and post-render validation for duration, channels, sample rate, peak/true peak, loudness, clipping, silence, NaN/Inf, beat alignment and drift.
- [ ] **Step 5:** Preserve preview/final rendering on the same plan; only DSP cost may differ. Do not let preview create a different musical decision.
- [ ] **Step 6:** Create render manifests containing plan/config/source/renderer/DSP/model identities and persist them through the new repository.
- [ ] **Step 7:** Run existing render tests plus a short synthetic audio render; verify the output is reproducible and remains within resource budget.
- [ ] **Step 8:** Commit plan-driven rendering.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 10: MCP application surface and legacy adapters

**Files:**
- Create: `app/application/transition/**`, `sequence/**`, `rendering/**`, `diagnostics/**` use cases as required by prior contracts
- Create: new MCP tools under `app/tools/` for `analyze_track`, `analyze_pool`, `get_analysis`, `invalidate_analysis`, `resolve_config`, `validate_config`, `generate_transition_candidates`, `validate_transition`, `score_transition`, `plan_transition`, `build_candidate_graph`, `optimize_sequence`, `plan_set`, `render_transition`, `render_set`, `validate_render`, `explain_transition`, `explain_sequence`, `get_execution_manifest`
- - Modify: current compute/render tools to call application use cases through legacy adapters
- Test: MCP contract/visibility/serialization tests and existing tool suites

**Interfaces:**
- Produces: application-level MCP boundary with stable typed responses and legacy compatibility.
- Consumes: application use cases; MCP layer does not import analyzers, DSP or repositories directly.

- [ ] **Step 1:** Write failing contract tests for each new use-case request/response schema and for legacy tool calls routed through adapters.
- [ ] **Step 2:** Implement DI wiring so MCP tools receive application services/ports rather than concrete analyzer or DSP classes.
- [ ] **Step 3:** Expose diagnostics and explainability in tool responses without leaking infrastructure internals or credentials.
- [ ] **Step 4:** Implement shadow mode comparing legacy/new technical constraints, BPM/cues, scores, recipe, ranking and diagnostics for the same request.
- [ ] **Step 5:** Keep `DJ_ENGINE=legacy|shadow|new` and `DJ_RENDERER=legacy|new` feature flags; default to legacy until shadow gates pass.
- [ ] **Step 6:** Run the MCP visibility/serialization suites and representative transition/render workflows; verify no tool directly imports a concrete analyzer.
- [ ] **Step 7:** Commit the new application/MCP surface.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

### Task 11: Cutover, legacy retirement and repository-wide verification

**Files:**
- - Modify: feature-flag/config wiring, legacy adapters and docs only after measured parity
- Create: `docs/superpowers/reports/2026-09-04-ai-dj-universal-engine-cutover.md`
- - Update: `docs/architecture.md` and relevant tool/catalog documentation

**Interfaces:**
- Produces: production default on the new engine with rollback retained until the final verification gate; no premature deletion of compatibility code.
- Consumes: all prior phase contracts, persisted plans/manifests and baseline comparisons.

- [ ] **Step 1:** Run shadow comparisons over representative transitions and sets; require technical constraint parity, expected musical-score deltas, deterministic ranking and explainability completeness before changing defaults.
- [ ] **Step 2:** Run resource tests with bounded candidate pools and deep candidates; confirm memory remains within the M2 8 GB safety envelope and concurrency never exceeds configured limits.
- [ ] **Step 3:** Run repository-wide `pytest`, `ruff check app tests`, `mypy app` and import-linter; classify any failures against the baseline rather than masking them.
- [ ] **Step 4:** Run deterministic execution twice with identical source/config/model/version/seed identity and compare canonical TransitionPlan, SetPlan and RenderManifest outputs.
- [ ] **Step 5:** Switch default engine/renderer to `new` only after all gates pass; retain rollback flags until post-cutover validation is recorded.
- [ ] **Step 6:** Perform additive DB migration validation, backfill verification and dual-read consistency checks before stopping legacy writes.
- [ ] **Step 7:** Remove legacy paths only when compatibility coverage, persistence migration, renderer validation and rollback confidence are documented in the cutover report.
- [ ] **Step 8:** Update architecture docs to reflect the implemented boundaries and actual MCP surface; do not claim features not demonstrated by tests.
- [ ] **Step 9:** Commit the cutover and documentation as the final migration change.

**Commit:** `git add <task files> && git commit -m "<task-specific message>"`

---

## Verification matrix

| Gate | Required evidence | Blocks |
|---|---|---|
| Domain purity | import-linter + pure unit tests | all domain work |
| Analysis identity | snapshot/cache tests + deterministic fixture | transition planning |
| Technical correctness | tempo/phase/downbeat/drift hard-reject tests | musical ranking |
| Musical scoring | independent dimensions + golden/parity tests | planner cutover |
| Transition contract | immutable serialization + decision diagnostics | renderer |
| Sequence | synthetic graph + Beam Search + constraint tests | set planning |
| Persistence | additive migration + repository tests | production cutover |
| Renderer | plan fidelity + rendered-audio validation | renderer default switch |
| MCP | typed contract + visibility + legacy adapter tests | API cutover |
| Resource safety | bounded memory/CPU/deep-candidate tests | M2 production use |
| Reproducibility | identical execution identity => identical canonical plans | final release |
| Legacy removal | shadow parity + rollback confidence + migration report | deletion of adapters |

## Explicit implementation order

```text
0 Baseline
  ↓
1 Domain contracts
  ↓
2 Analysis normalization
  ↓
3 Configuration
  ↓
4 Candidate + hard constraints
  ↓
5 Musical evaluation + recipes
  ↓
6 TransitionPlan
  ↓
7 CandidateGraph + Beam Search
  ↓
8 Persistence/cache
  ↓
9 Plan-driven renderer
  ↓
10 MCP/application surface
  ↓
11 Shadow → cutover → legacy removal
```

The sequence intentionally places configuration before transition scoring, persistence before final cutover, and renderer integration after `TransitionPlan` is stable. Existing code remains usable through adapters throughout the migration.

## Self-review against the approved spec

- Sections 1–4: covered by Tasks 1, 3, 4, 5 and 6; hard/boundary/soft/preference classification is explicit.
- Analysis/beatgrid/phrase/structure/cues: Task 1–2.
- Transition pipeline and independent musical dimensions: Tasks 4–6.
- SetState/CandidateGraph/Beam Search/dramaturgy: Task 7.
- Declarative configuration/provenance/versioning/invalidation: Task 3.
- Persistence/Storage/pgvector/cache identity: Task 8.
- Plan-driven renderer/validation/manifest: Task 9.
- MCP boundary/legacy adapters/shadow mode: Task 10.
- Incremental migration/rollback/resource budgets: Tasks 0, 2, 8, 10, 11.
- Reproducibility/explainability: Tasks 6, 8, 9, 11.
- M2 8 GB constraint: global constraint plus Tasks 2, 7, 9, 11.
- No big-bang rewrite: global constraint and every migration task uses adapters.

## Placeholder scan

No implementation-placeholder instructions (`TBD`, `TODO`, "implement later", or unbounded "write tests for the above") are used. Each task names concrete files/contracts, a focused test boundary, implementation behavior and a commit boundary.

## Type/contract consistency

The dependency chain is explicit: `AnalysisSnapshot → CandidateTransition → AlignmentResult/ConstraintResult → MusicalScore/TransitionRecipe → TransitionPlan → CandidateGraph/SetState → SetPlan → Renderer`. Configuration resolves before all planning stages and its hash participates in cache/execution identity.

# Universal AI DJ Engine — Design Specification

**Date:** 2026-09-04  
**Status:** Approved architecture / implementation design  
**Repository:** `evgenygurin/dj-music-plugin`

## 1. Purpose

Redesign the DJ engine into a universal AI-assisted mixing and electronic-music analysis system that can generate technically valid, musically coherent, explainable, reproducible transition and set plans, and render those plans deterministically.

The engine must support the full capability envelope in one implementation. Conservative, balanced, smooth, energetic, and creative behavior are configuration/policy choices, not separate engines.

## 2. Core architectural principles

1. Technical correctness is a hard constraint; musicality is an objective; creativity is a search/ranking policy.
2. The engine first constructs the allowed transition space, then validates technical constraints, then ranks musical quality.
3. Profiles are declarative configuration presets, never alternate algorithms.
4. `TransitionPlan` is the immutable contract between planning and rendering.
5. `SetPlan` is the immutable result of sequence optimization.
6. Analysis is computed once, versioned, hashed, cached, and reused.
7. Heavy analysis such as stem separation is performed only after cheap candidate reduction.
8. The domain layer is independent of Supabase, MCP, Demucs, FFmpeg, torch, librosa, and other infrastructure.
9. MCP/API operations target application use cases, not individual analyzers or DSP internals.
10. Every material decision is explainable and retains rejected alternatives/reasons.
11. Execution identity contains configuration, analysis, engine, renderer, model/DSP, source, and seed information for reproducibility.
12. Migration is incremental and backward-compatible; no big-bang rewrite.

## 3. Universal engine and configuration

The architecture contains one universal engine:

```text
UniversalEngine + ResolvedConfig + SelectionPolicy
```

Configuration hierarchy:

```text
Global Defaults
  -> Genre Profile
  -> Behavior Profile
  -> Set Overrides
  -> Transition Overrides
  -> Render Overrides
  -> ResolvedConfig
```

Overrides are patches rather than full copies. `ResolvedConfig` is immutable, validated, serializable, and carries parameter provenance and a deterministic hash.

Every parameter has a schema-level classification:

- `HARD` — violation rejects the candidate/plan.
- `BOUNDARY` — constrains the candidate search space.
- `SOFT` — affects objective/ranking.
- `PREFERENCE` — tie-breaks or prefers among otherwise acceptable options.

A lower-level soft preference may never weaken a hard constraint. Render overrides cannot invalidate an existing plan; changes to plan-level constraints require replanning.

Schema version is distinct from engine, analyzer, model, and renderer versions. Configuration migrations must be explicit; unknown fields must not be silently ignored.

## 4. Configuration domains

`TransitionProfile` covers:

- tempo: min/max BPM, relative change, half/double-time hypotheses, pitch/time-stretch limits, variable-tempo policy;
- beatgrid: validity/confidence/stability, downbeats, beats-per-bar, phrase length, phase correction;
- drift: maximum beats/ms, measurement window, model, tolerance, extrapolation;
- phrase: required boundaries, allowed/preferred/min/max bars, partial phrase policy;
- cues: cue type permissions and boundary tolerances;
- structure: section compatibility and structural feature weights;
- energy: target delta, direction, trajectory/slope, peak/cooldown behavior;
- harmony: Camelot/Tonnetz/chroma/dissonance, confidence, key policies;
- low-end: kick/bass collision thresholds, dual-kick/dual-bass policies, bass swap;
- spectrum, groove, timbre;
- vocals: overlap and vocal conflict policies, stem requirements;
- stems: enabled/required/allowed, processing budget, confidence and fallback;
- recipes: enabled/preferred/forbidden/fallback, complexity and FX limits;
- automation: gain, fader, EQ, filter, stems, effects, master guard;
- creativity: novelty and controlled risk dimensions;
- dramaturgy: energy/harmonic/novelty arcs, repetition, diversity, peak spacing;
- selection: selection strategy and objective policy;
- render: sample rate, format, loudness, true peak, normalization, limiter, time-stretch/pitch preservation, validation.

## 5. Analysis architecture

Analysis is layered:

```text
L1 Cheap Track Analysis
  -> L2 Tempo / Beat / Temporal Analysis
  -> L3 Phrase / Structure / Cue Analysis
  -> L4 Deep Stem / Collision / Vocal Analysis
```

The existing analyzer set remains a feature source rather than being discarded. Analyzer output is normalized into domain representations and assembled into an immutable `AnalysisSnapshot`.

`AnalysisSnapshot` contains:

- track/source identity;
- duration and sample rate;
- primary tempo plus `TempoHypothesis[]`;
- tempo curve and stability;
- beats, downbeats, bars, phase and confidence;
- phrases and boundaries;
- sections and structural boundaries;
- cue points;
- energy, harmony, spectrum, groove, timbre, vocal and stem features;
- analyzer/model/DSP versions, schema version, analysis hash and creation metadata.

A BPM scalar is not sufficient. Tempo, beatgrid, beat phase, downbeats, phrase structure, and accumulated drift are first-class concepts.

Tempo hypotheses explicitly support 0.5x/1x/2x interpretations. Beat alignment evaluates tempo ratio, phase error, downbeat error, bar/phrase alignment, phase correction and predicted drift over the actual transition duration.

EDM structure must use beat-grid-aware features including drum density, bass energy, spectral novelty, energy, vocal activity and harmonic activity. Generic segmentation such as SBic can remain a supporting signal but is not the sole structural authority.

Cue points carry timestamp, beat/bar/phrase, section, cue type, confidence, salience, novelty, energy and reasons. Typical types include `INTRO`, `OUTRO`, `BREAKDOWN_IN/OUT`, `BUILDUP_IN/OUT`, `DROP`, `DROP_OUT`, `VOCAL_IN/OUT`, `DRUM_IN/OUT`, `PHRASE_BOUNDARY`, and `CUSTOM`.

## 6. Transition planning pipeline

The transition engine follows:

```text
Track A + Track B
  -> Candidate Generation
  -> Hard Validation
  -> Alignment Analysis
  -> Structure Validation
  -> Musical Evaluation
  -> Recipe Generation
  -> Recipe Validation
  -> Ranking / Selection
  -> TransitionPlan
```

Candidate generation uses source/target cue points, section pairs, tempo hypotheses and allowed bar durations. Technical validation checks tempo limits, beatgrid validity, phase/downbeat tolerance, drift, pitch shift, time stretch, duration and signal constraints. Rejections are retained with explicit reasons.

Musical evaluation is decomposed into independent dimensions:

- harmony;
- energy;
- low-end;
- spectrum;
- groove;
- timbre;
- vocals;
- stems.

Correlated features must be normalized/grouped so that related metrics do not accidentally dominate through double-counting.

Recipe generation may produce several recipes for a candidate. Each recipe is independently validated. Example recipes include FADE, EQ_BLEND, FILTER_BLEND, DRUM_SWAP, BASS_SWAP, STEM_BLEND, VOCAL_CUT, VOCAL_SUSTAIN, ECHO_OUT, LOOP_ROLL, HARD_CUT, DROP_SWAP, BREAKDOWN_TO_DROP and DROP_TO_DROP.

Selection policies are policies over the same candidate space, for example:

- `BEST`
- `SAFEST`
- `MOST_HARMONIC`
- `MOST_ENERGETIC`
- `MOST_GROOVY`
- `MOST_CREATIVE`
- `MOST_SMOOTH`
- `EXPLICIT_PROFILE`

The decision result is:

```text
TransitionDecision
  selected
  alternatives[]
  rejected[]
  diagnostics
```

## 7. TransitionPlan contract

`TransitionPlan` is immutable and serializable. It contains:

- source track, positions, cue, section and tempo hypothesis;
- target track, position, cue, section and tempo hypothesis;
- duration in bars/beats/seconds;
- source/target/effective BPM;
- beat/downbeat offsets and phase correction;
- predicted drift and confidence;
- recipe and parameters;
- automation graph for gain/fader/EQ/filter/stems/effects;
- execution constraints such as maximum peak, drift, pitch shift and stretch;
- technical, musical, dramaturgical, creativity and final scores;
- diagnostics and provenance.

The planner decides **what** to do. The renderer decides only **how** to execute the plan.

## 8. Set-level optimization

Pairwise transition quality is insufficient for complete DJ-set planning. The sequence engine maintains `SetState` containing current track/position/BPM/energy/key/section plus histories of energy, BPM, key, section, recipe, artist, genre and repetition, and a dramaturgy state.

`CandidateGraph` stores transition edges and cached `TransitionPlan` candidates. Sequence optimization does not redo audio analysis or DSP.

Set hard constraints can include:

- maximum same artist/release;
- minimum track gap;
- repeated-track limits;
- consecutive section/recipe limits;
- BPM/energy bounds;
- required duration/count;
- mandatory/included/excluded tracks and fixed positions.

Set objectives include technical validity, transition quality, energy/harmonic arcs, novelty, groove continuity, structural flow, recipe diversity, artist/track diversity and repetition penalty.

Dramaturgy is modeled as trajectories rather than a scalar: target energy, novelty and harmonic curves; peak spacing; cooldown behavior; and repetition control.

`Beam Search` is the primary bounded optimizer because it is deterministic, controllable, explainable and appropriate for an M2 MacBook Air with limited memory. `Greedy`, optional `Genetic`, and future strategies can share the same `CandidateGraph` and constraint/objective interfaces.

Multi-objective priority is:

```text
1. HARD CONSTRAINTS
2. TECHNICAL MARGIN
3. SET OBJECTIVES
4. TRANSITION OBJECTIVES
5. PROFILE PREFERENCES
6. TIE-BREAK
```

The result is an immutable `SetPlan` containing tracks, transitions, duration, energy/BPM/key curves, dramaturgy, alternatives and diagnostics.

## 9. Rendering architecture

Renderer input:

```text
TransitionPlan + RenderConfig + source/target audio
```

Rendering pipeline:

```text
Audio Preparation
  -> Tempo Mapping
  -> Time Stretch / Pitch Preservation
  -> Beat Phase Alignment
  -> Phrase Synchronization
  -> Automation Graph
  -> Mix Bus
  -> Master Safety
  -> Post-render Validation
  -> RenderedTransition
```

The renderer must never re-select BPM, cue points, duration, recipe or musical intent. If a plan cannot be executed, rendering fails explicitly.

Automation is declarative: parameter, start/end, duration, curve/shape, bounds and constraints. Master safety remains mandatory regardless of profile and protects against clipping, true-peak violations, invalid values, corrupt output and invalid sample-rate conversion.

Preview and final rendering use the same plan; preview may use cheaper DSP. A `RenderManifest` records plan/config/source/renderer/DSP/model identities.

`TransitionPlanValidator` validates the plan before execution. `RenderedAudioValidator` verifies the actual rendered output against the plan, including duration, channels, sample rate, peak/true peak, loudness, clipping, silence, NaN/Inf, beat alignment and drift.

## 10. Layered code architecture

Target package structure:

```text
app/
├── domain/
│   ├── analysis/
│   ├── mixing/
│   ├── sequence/
│   ├── configuration/
│   └── common/
├── application/
│   ├── analysis/
│   ├── transition/
│   ├── sequence/
│   ├── rendering/
│   └── diagnostics/
├── audio/
│   ├── analyzers/
│   ├── beatgrid/
│   ├── structure/
│   ├── stems/
│   ├── dsp/
│   └── rendering/
├── infrastructure/
│   ├── persistence/
│   ├── cache/
│   ├── embeddings/
│   ├── storage/
│   └── resources/
└── interfaces/
    └── mcp/
```

Domain value objects include `TempoHypothesis`, `BeatPosition`, `Phrase`, `CuePoint`, `AlignmentResult`, `CandidateTransition`, `ConstraintResult`, `DimensionScore`, `MusicalScore`, `TransitionRecipe`, `TransitionPlan`, `SetState`, `CandidateGraph`, and `SetPlan`.

Infrastructure implements ports such as `AnalysisRepository`, `EmbeddingRepository`, `StemSeparator`, and `AudioRenderer`. Existing analyzers are migrated through adapters rather than rewritten in one operation.

## 11. Persistence and caching

Supabase/Postgres stores metadata and indexes such as tracks, analysis snapshots, tempo hypotheses, beatgrid metadata, phrases, sections, cue points, transition plans, transition edges, set plans and execution manifests.

Supabase Storage stores large waveform/time-series data, embeddings where appropriate, stems, deep-analysis artifacts and rendered audio. pgvector remains the vector search layer.

Cache identities include source analysis hashes, resolved configuration hash, engine/schema versions and relevant model/DSP identities. Large binary objects must not be moved unnecessarily through Postgres.

Dependency graph:

```text
Raw Audio
  -> Analysis
  -> BeatGrid
  -> Structure
  -> Transition Candidates
  -> Transition Plans
  -> Set Plan
  -> Render
```

Changes invalidate only downstream layers that depend on them.

## 12. Resource budget and reproducibility

The execution scheduler must support bounded:

- maximum parallel analysis;
- maximum parallel stem separation;
- memory budget;
- CPU budget;
- GPU memory budget;
- maximum deep candidates.

Memory safety has priority over concurrency for the target M2 8 GB environment.

Execution identity contains:

```text
config_hash
engine_version
analysis_versions
renderer_version
DSP backend
model versions
source analysis hashes
random seed
```

Supported randomness modes are deterministic, seeded and random. Production behavior should default to reproducible seeded/deterministic execution.

## 13. MCP/API boundary

New application-level operations should include:

- analysis: `analyze_track`, `analyze_pool`, `get_analysis`, `invalidate_analysis`;
- config: `resolve_config`, `validate_config`;
- transition: `generate_transition_candidates`, `validate_transition`, `score_transition`, `plan_transition`;
- sequence: `build_candidate_graph`, `optimize_sequence`, `plan_set`;
- rendering: `render_transition`, `render_set`, `validate_render`;
- diagnostics: `explain_transition`, `explain_sequence`, `get_execution_manifest`.

Existing MCP tools remain operational through legacy adapters during migration. MCP must not call analyzers or DSP directly.

## 14. Migration strategy

Migration is staged:

1. **Baseline** — inventory current tools, analyzers, domain services, persistence, cache, scoring, optimizer, renderer and tests; capture behavioral/performance baselines.
2. **Contracts** — introduce domain contracts without replacing existing analyzers.
3. **Analysis normalization** — build `AnalysisOrchestrator` and `AnalysisSnapshot` with BASIC/MIX_READY/DEEP tiers.
4. **Transition engine** — introduce candidate generation, hard validation, alignment, musical evaluation, recipes and `TransitionPlan`; route legacy calls through an adapter.
5. **Configuration engine** — introduce schema, resolver, validation, profiles, provenance, hashes and legacy parameter adapter.
6. **Sequence optimizer** — build `CandidateGraph`, `SetState`, Beam Search and dramaturgy objectives.
7. **Renderer integration** — make rendering plan-driven, deterministic and validated.
8. **MCP migration / legacy removal** — route tools to new use cases, then remove legacy paths only after regression coverage and rollback confidence.

The dependency order is:

```text
Contracts -> Analysis -> Configuration -> Transition -> Sequence -> Renderer -> MCP -> Legacy removal
```

Shadow mode should compare legacy and new transition decisions before production cutover. Feature flags should support `DJ_ENGINE=legacy|shadow|new` and `DJ_RENDERER=legacy|new` during migration.

Database migration should be additive: add structures, dual-read, optionally dual-write, backfill, validate, switch reads, stop old writes, and only then remove legacy structures.

## 15. Testing strategy

- Pure domain unit tests for constraints, alignment, scoring, recipes, configuration resolution and sequence objectives.
- Analysis integration tests with small deterministic audio fixtures.
- Limited heavy Demucs/stem E2E tests because of resource cost.
- Regression tests against legacy transition behavior during shadow migration.
- Renderer tests for plan fidelity and output validation.
- Configuration migration/provenance/hash tests.
- Determinism tests using identical execution identities.
- Performance/resource-budget tests, especially RAM and deep-analysis scheduling.

## 16. Architectural invariants

1. Hard constraint violation always rejects.
2. Renderer never plans.
3. Optimizer never runs DSP.
4. MCP never depends on a concrete analyzer.
5. Domain never depends on infrastructure technologies.
6. Configuration contains policy/data, not executable business logic.
7. Profiles are not separate engines.
8. Analysis results are versioned and hashed.
9. `TransitionPlan` is immutable.
10. `SetPlan` is immutable.
11. Soft scores cannot compensate for hard violations.
12. Heavy analysis happens after candidate reduction.
13. Material decisions are explainable.
14. Equal execution identities are reproducible.
15. Legacy APIs can route through adapters.
16. No hidden duplicate DSP between analysis, optimization and rendering.

## 17. Explicit non-goals

The redesign must not create separate engines for each profile, replace deterministic DSP with ML without need, require GPU/ML inference for ordinary operation, run Demucs for every track/candidate, retain a monolithic transition scorer, let the optimizer analyze audio, let the renderer choose musical decisions, or perform a big-bang rewrite.

## 18. Definition of done for the architecture

The redesign is considered implemented only when:

- domain boundaries and contracts are enforced;
- analysis is versioned, cached and invalidated correctly;
- transition planning separates technical constraints, musical scoring and recipes;
- set planning uses graph/state/beam search with dramaturgy;
- renderer executes immutable plans and validates output;
- MCP remains backward compatible while exposing the new application use cases;
- persistence and storage boundaries are respected;
- resource budgets are enforced;
- execution is reproducible and explainable;
- migration has regression coverage and rollback controls;
- legacy paths are removed only after all required validation gates pass.

## 19. Architectural conclusion

The target is a single universal AI DJ engine in which:

```text
Configuration
  -> AnalysisSnapshot
  -> Candidate Space
  -> Hard Technical Validation
  -> Alignment / Structure
  -> Musical Evaluation
  -> Recipe Selection
  -> TransitionPlan
  -> CandidateGraph / SetState
  -> SetPlan
  -> Deterministic Renderer
  -> Validated Audio + Manifest
```

The fundamental separation is:

> **Technical correctness is a constraint. Musicality is an objective. Dramaturgy is a set-level objective. Creativity is a controlled search policy. The planner decides what to do; the renderer decides only how to execute it.**

This specification is the architectural gate for implementation planning. No implementation phase should contradict these invariants without an explicit architecture decision record/update to this specification.

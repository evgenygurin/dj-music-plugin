# workflow-01: Set Building & Optimization

**Phase**: Workflow
**Status**: completed
**MCP Tools**: `build_set`, `rebuild_set`, `score_transitions`, `get_set_cheat_sheet`, `get_set_templates`
**Services**: `SetService`, `BuildSetWorkflow`, `TransitionScorer`, `GA/Greedy Optimizer`
**Dependencies**: core-01, core-02, workflow-02

## BR-SET-001: Set Generation from Playlist

**Description**: Build an optimized DJ set from a playlist using genetic algorithm or greedy chain builder, respecting template energy arcs and transition scoring.

**Rationale**: Manual set ordering is tedious for 15-60 tracks. Automated optimization using 6-component transition scoring produces better results.

### User Stories

#### US-SET-001: As a DJ, I want to build an optimal set from a playlist

**Acceptance Criteria:**
- [x] AC-SET-001: Given a playlist with analyzed tracks, when `build_set(playlist_id=5, template="peak_hour_60", algorithm="ga")` is called, then create set with scored transitions
- [x] AC-SET-002: Given tracks without L3 features, when building, then auto-trigger `TieredPipeline.ensure_level(L3)` before optimization
- [x] AC-SET-003: Given `dry_run=true`, when building, then return preview without persisting set to DB
- [x] AC-SET-004: Given `algorithm="greedy"`, when building, then use fast greedy chain (no GA) with best-next-transition heuristic

#### US-SET-002: As a DJ, I want to rebuild a set with pinned/excluded tracks

**Acceptance Criteria:**
- [x] AC-SET-005: Given an existing set, when `rebuild_set(set_id=6, pin_tracks=[42,55])` is called, then keep pinned tracks in place, re-optimize the rest
- [x] AC-SET-006: Given exclude list, when rebuilding, then never include excluded tracks in result
- [x] AC-SET-007: Each rebuild creates a new `SetVersion` — old versions preserved for comparison

## BR-SET-002: Transition Scoring

**Description**: 6-component weighted formula (BPM, harmonic, energy, spectral, groove, timbral) with hard constraints and section-aware relaxation.

**Rationale**: Transition quality determines the DJ set experience. Hard constraints prevent unplayable transitions; section-aware scoring relaxes harmonic rules on drum-only mix windows.

### User Stories

#### US-SET-003: As a DJ, I want to score transitions between specific tracks

**Acceptance Criteria:**
- [x] AC-SET-008: Given two track IDs, when `score_transitions(mode="pair", from_track_id=42, to_track_id=55)` is called, then return 6-component breakdown + overall score
- [x] AC-SET-009: Given BPM difference > 10, then `hard_reject=true` with `reject_reason`
- [x] AC-SET-010: Given both mix windows are drum-only sections, then floor harmonic score at 0.85 and boost groove weight

#### US-SET-004: As a DJ, I want a human-readable cheat sheet for my set

**Acceptance Criteria:**
- [x] AC-SET-011: Given a set with transitions, when `get_set_cheat_sheet(set_id=6)` is called, then return text with BPM flow, key changes, energy curve, transition types

## BR-SET-003: Set Templates

**Description**: 8 pre-defined templates (warm_up_30, classic_60, peak_hour_60, roller_90, progressive_120, wave_120, closing_60, full_library) with slot-based energy arcs.

**Rationale**: Templates encode DJ knowledge about energy management for different set lengths and contexts.

### User Stories

#### US-SET-005: As a DJ, I want to view available templates with slot definitions

**Acceptance Criteria:**
- [x] AC-SET-012: When `get_set_templates()` is called, then return all 8 templates with slots (position, target_mood, energy_target, bpm_range, duration, flexibility)

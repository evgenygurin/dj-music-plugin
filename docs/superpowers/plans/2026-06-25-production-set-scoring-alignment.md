# Production Set Scoring Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align optimization, persisted transition scoring, structural mix metadata, and cheatsheet provenance.

**Architecture:** Enrich the shared scoring DTO with provider and preferred-section metadata, then build one pure pair context used by all runtime scoring paths. Persist the resulting section/mix metadata through existing columns and expose the provenance in the set cheatsheet.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, Pydantic v2, FastMCP, pytest.

---

### Task 1: Pair Context

**Files:**
- Create: `app/domain/transition/pair_context.py`
- Modify: `app/shared/features.py`
- Test: `tests/domain/transition/test_pair_context.py`

- [ ] Write tests proving intent and section context are derived from position,
  LUFS delta, template, and preferred section fields.
- [ ] Run `uv run pytest -q tests/domain/transition/test_pair_context.py` and
  confirm the missing module/API failure.
- [ ] Implement `TransitionPairContext` and `build_pair_context`.
- [ ] Re-run the test and confirm it passes.

### Task 2: Structural Feature Enrichment

**Files:**
- Modify: `app/repositories/track_features.py`
- Modify: `app/shared/features.py`
- Test: `tests/repositories/test_track_features_repo.py`

- [ ] Add a repository test with intro/outro sections and phrase boundaries.
- [ ] Run the focused repository test and confirm preferred section fields are
  absent.
- [ ] Batch-load sections, select deterministic mix-in/mix-out candidates, and
  populate the shared DTO.
- [ ] Re-run repository tests.

### Task 3: Optimizer Context Parity

**Files:**
- Modify: `app/domain/optimization/fitness.py`
- Modify: `app/domain/optimization/genetic.py`
- Modify: `app/domain/optimization/greedy.py`
- Modify: `app/tools/compute/sequence_optimize.py`
- Test: `tests/domain/optimization/test_fitness.py`
- Test: `tests/tools/compute/test_sequence_optimize.py`

- [ ] Add tests proving scorer calls receive pair intent/sections and canonical
  moods reach the optimizer.
- [ ] Run focused tests and confirm failures.
- [ ] Route `build_pair_context` through fitness, greedy selection, and the GA
  cache; pass moods from loaded features.
- [ ] Re-run optimizer tests.

### Task 4: Persist Effective Transition Context

**Files:**
- Modify: `app/handlers/transition_persist.py`
- Modify: `app/handlers/set_version_build.py`
- Test: `tests/handlers/test_set_version_build.py`

- [ ] Add tests asserting scorer/recipe parity plus transition and set-item
  section metadata.
- [ ] Run the handler test and confirm failure.
- [ ] Persist section ids, overlap, transition id, and mix points using the same
  pair context used for scoring.
- [ ] Re-run handler tests.

### Task 5: Provenance-Aware Cheatsheet

**Files:**
- Modify: `app/resources/set.py`
- Test: `tests/resources/test_set_resources.py`

- [ ] Add assertions for canonical, audio, and Beatport key/BPM fields and next
  transition metadata.
- [ ] Run the resource test and confirm failure.
- [ ] Batch-load features/transitions and emit the expanded booth view.
- [ ] Re-run resource tests.

### Task 6: Verification

**Files:**
- Modify: `docs/transition-scoring.md`

- [ ] Update runtime documentation to match actual code.
- [ ] Run focused transition, optimization, repository, handler, and resource
  suites.
- [ ] Run `make check`; if an unrelated dirty-tree failure exists, report it
  separately with the exact failing command.

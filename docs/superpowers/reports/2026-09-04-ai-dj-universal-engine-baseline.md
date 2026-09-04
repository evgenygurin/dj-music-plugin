# AI DJ Universal Engine — Baseline Report

**Date:** 2026-09-04
**Branch:** `codex/ai-dj-universal-engine`
**Worktree:** `.worktrees/ai-dj-universal-engine`
**Base plan:** `docs/superpowers/plans/2026-09-04-ai-dj-universal-engine.md`
**Approved spec:** `docs/superpowers/specs/2026-09-04-ai-dj-universal-engine-design.md`

## 1. Isolation and working-state boundary

The implementation is isolated in a dedicated Git worktree. The original
`test-assembly` checkout is not modified by this implementation. The isolated
worktree was clean at baseline before this report was created.

The original checkout contained unrelated changes to `.opencode/package.json`
and `dj-music-plugin-cell16`; these are explicitly outside this migration.

Baseline command:

```text
git status --short --branch
```

Result in the feature worktree:

```text
## codex/ai-dj-universal-engine
```

No user changes were present in the isolated worktree before the report.
## 2. Python and test-environment baseline

`pyproject.toml` declares Python `>=3.12`, Ruff target `py312`, and mypy
`python_version = "3.12"`. The host `python3` is CPython 3.14.0. `uv` is
installed and can provision CPython 3.12.0.

There was no project `.venv` initially. `uv run --no-sync python --version`
provisioned `.venv` with CPython 3.12.0, but the environment has no project
pytest installation; the invoked pytest resolved to the host Python 3.11
installation. This is an environment/tooling mismatch, not a source fix.

Baseline test command attempted:

```text
uv run --no-sync pytest -q tests/domain/transition tests/domain/optimization \
  tests/domain/render tests/audio tests/config tests/handlers \
  --disable-warnings --maxfail=1
```

Result: **FAIL during collection**. The first error is Python 3.11 parsing
Python-3.12 syntax in `app/domain/render/segments.py`:

```text
type RenderSegmentList = list[TrackSegment] | list[StemSegment]
```

This confirms the earlier bare `pytest` failure was caused by the wrong
interpreter rather than by the new branch. Do not rewrite this syntax.

The next baseline test run must use a real Python 3.12 project environment
with the declared dev dependencies, preferably via `uv`, without installing
heavy optional audio/stem extras unless required by the focused test.
## 3. Static-quality baseline

`ruff check app tests` reports **191 errors**. Representative pre-existing
findings include import sorting/unused imports in audio tests and `SIM117` in
`tests/audio/deep/test_stems_runtime.py`. These findings predate the universal
engine work and are not being mass-fixed as part of baseline isolation.

`mypy app` reports **1 syntax error** and cannot continue:

```text
app/audio/deep/demucs_mlx_runner.py:44: error: expected an indented block
  after 'try' statement on line 43 [syntax]
```

`lint-imports` is not installed in the current environment; `uv run
--no-sync lint-imports` therefore fails with executable-not-found. The dev
group declares `import-linter>=2.11`, so this check remains a setup prerequisite
for later verification.

Repository source contains unresolved Git conflict markers in existing files:

- `app/config/stems.py` — multiple conflict blocks.
- `app/audio/deep/demucs_mlx_runner.py` — multiple conflict blocks.

The merge markers are treated as pre-existing baseline defects. They must not
be silently resolved while implementing unrelated domain contracts; if a later
task must touch one of these files, the conflict state becomes an explicit
integration concern and must be handled with focused tests.
## 4. Existing application surface

The repository catalog currently documents 30 model-visible tools, 44
resources, 33 prompts, 6 handlers and 11 registered entities. The compute
surface includes `transition_score_pool` and `sequence_optimize`; render
includes `render_beatgrid`, `render_mixdown`, `render_validate_grid` and
`render_diagnose`; deep analysis includes `deep_analyze_track`,
`deep_analyze_pool`, `find_compatible_tracks` and `get_cross_similarity`.
These names and response contracts are migration compatibility targets.

The principal implementation anchors are:

- `app/domain/transition/**` — current pair scoring, constraints, recipes and
  orchestration.
- `app/domain/optimization/**` — constructive, greedy and genetic sequencing.
- `app/domain/render/**` — render plans, timelines, segment/stem policies and
  execution models.
- `app/audio/analyzers/**` — current scalar/feature analyzers.
- `app/audio/core/**` — tempo, beatgrid, rhythm, tonal and spectral primitives.
- `app/audio/deep/**` — Demucs/stem analysis, embeddings, cross-similarity and
  time-series/waveform storage.
- `app/config/**` — current transition/render/stem configuration.
- `app/tools/compute/**` and `app/tools/render/**` — MCP/application entry
  points.
- `app/handlers/l6_analysis_orchestrator.py` — current deep-analysis handler.

The repository contains 388 Python files under the primary architecture
anchors (`transition`, `optimization`, `render`, `audio`, `config`, compute and
render tools).

## 5. Existing persisted analysis inputs

Beatgrid metadata is already represented in `track_features` and
`dj_beatgrids`; large beatgrid arrays use a storage URI/reference rather than
being duplicated in relational metadata. Existing time-series storage and
waveform storage use external artifacts. Track embeddings are persisted in
`track_embeddings` using pgvector, while per-stem deep features are persisted
in `stem_features`. Cross-similarity is persisted separately.

This existing data can feed future `AnalysisSnapshot` adapters without
recomputing DSP. The approved architecture therefore introduces normalization
contracts around existing outputs rather than replacing the audio pipeline.
## 6. Resource and migration constraints

The current render/deep-analysis surface performs heavy librosa/FFmpeg/
rubberband and Demucs work, with the deep pipeline additionally producing
per-stem analysis, embeddings and external time-series/waveform artifacts.
The new engine must therefore keep deep/stem work behind cheap candidate
reduction and an explicit resource budget. Development verification should
prefer serial or tightly bounded tests on the 8 GB M2 rather than increasing
parallelism to compensate for the broken baseline environment.

No audio files were processed during baseline. No Demucs, MLX, GPU/Neural
Engine or bulk Supabase operation was started.

## 7. Baseline decisions / non-goals

1. Do not reset, stash, or alter the original `test-assembly` working tree.
2. Do not mass-fix the 191 Ruff findings as part of Task 0.
3. Do not repair unrelated merge conflict markers unless a later migration
   task explicitly requires the affected file.
4. Do not rewrite Python 3.12 syntax to accommodate the host Python 3.11
   pytest executable.
5. Establish a proper Python 3.12 test environment before claiming a clean
   repository test baseline.
6. Keep optional heavy audio/stem dependencies out of the domain-contract
   phase unless a focused integration test requires them.

## 8. Task-0 gate

Task 0 has established the isolated branch, environment mismatch, static
quality baseline, application surface, persisted-analysis anchors and resource
constraints. The baseline report is the sole Task-0 artifact; implementation
work starts with Task 1 domain contracts after this report is committed.

# Universal AI DJ Engine Cutover Report

## Scope

This report records the verification gate for the incremental universal DJ engine
migration from the implementation plan dated 2026-09-04.

## Verified new-engine surface

- Immutable analysis contracts and deterministic snapshot identity.
- Tiered analysis orchestration with conservative resource budgets.
- Declarative configuration resolution and provenance.
- Cheap transition candidate generation and absolute hard technical validation.
- Musical score dimensions, grouped spectral weighting, and recipe validation.
- Immutable transition plans and auditable selection decisions.
- Bounded CandidateGraph / SetState / Beam Search sequence planning.
- Reproducibility identity, execution manifest, and bounded in-memory cache.
- Declarative render automation and pre/post-render validation contracts.
- Application sequence/transition facades, rollout mode model, shadow comparison.
- Read-only MCP facade for deterministic transition technical validation.

## Focused verification

The complete new-engine focused suite passes: 171 tests passed under Python 3.12
with xdist disabled to avoid unnecessary memory pressure on the M2 8 GB host.

Targeted Ruff and mypy checks for the new surface also pass.

## Repository-wide gate

Production cutover is **blocked** and the default engine must remain legacy.

The repository-wide pytest gate is blocked by pre-existing repository issues:

1. `app/config/stems.py` contains unresolved Git conflict markers and cannot be
   imported by the deep-audio test suite.
2. The environment used for this isolated verification does not contain the
   optional `pgvector` package required by the database/model test imports.
3. The repository has duplicate bare test module names in existing and newly
   added test trees; the new sequence tests were renamed to avoid introducing
   additional collection collisions.

The repository-wide Ruff gate currently reports 176 errors, while the new
architecture files have a clean targeted Ruff check. The repository-wide mypy
gate is blocked at the pre-existing syntax error in `app/audio/deep/
demucs_mlx_runner.py`.

## Cutover decision

Do not switch `DJ_ENGINE` or `DJ_RENDERER` defaults to `new` until the
repository-wide baseline blockers are repaired and shadow parity is measured
against representative real-library transitions and renders.

The migration remains additive and rollback-safe: legacy paths are preserved,
while the new domain/application contracts can be exercised independently.

# Universal AI DJ Engine — Cutover Report

## Current state

The migration remains incremental and production-safe. The universal engine contracts are implemented through sequence planning, additive persistence, and plan-driven render validation. Legacy execution remains the default.

## Verified slices

- Immutable analysis snapshots, tempo hypotheses, beatgrid/phrase/section/cue contracts.
- Tiered analysis orchestration with conservative resource budgets.
- Declarative configuration hierarchy and provenance.
- Candidate generation, hard technical validation, musical scoring and transition recipes.
- Immutable transition plans and deterministic selection.
- Bounded CandidateGraph and Beam Search set planning.
- Reproducibility identities, bounded transition cache and execution manifests.
- Additive persistence migration `0004_universal_engine_contracts`.
- Declarative render automation and pre/post-render safety validation.
- Legacy/shadow/new engine mode contracts and MCP-safe technical validation surface.

## Verification evidence

Focused architecture suites pass under Python 3.12 with xdist disabled. Targeted Ruff and mypy checks for the new architecture slices pass. The full repository gate is still blocked by baseline environment/repository issues, including an existing unresolved merge-conflict file in deep audio code and the missing optional `pgvector` dependency during broad test collection.

The broad gate was intentionally not masked or treated as a new-engine regression.

## Cutover decision

Do **not** switch `DJ_ENGINE` or `DJ_RENDERER` defaults to `new` yet. Production cutover requires successful repository-wide verification, shadow parity against representative real-library transitions, deterministic plan/manifest comparison, resource-budget evidence, and actual renderer/MCP application wiring.

## Remaining load-bearing work

1. Complete application-level TransitionPlanner integration across config, candidate generation, hard constraints, musical evaluation and recipes.
2. Wire renderer execution to `TransitionPlan` without internal re-planning.
3. Route existing MCP workflows through application use cases while preserving public tool behavior.
4. Implement shadow parity metrics beyond candidate/score comparison.
5. Add repository adapters and dual-read/dual-write behavior for the new persistence structures.
6. Resolve baseline repository blockers and run the complete verification matrix before cutover.
7. Only then remove legacy paths and change production defaults.

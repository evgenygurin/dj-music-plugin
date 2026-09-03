# Cell 13 — Quality and Integration

## Mission
Validate the Wave 4 fleet and consume all cell reports; do not own application implementation.

## Read
- all Wave 4 `TASK.md` and `REPORT.md`
- `tests/**`, `docs/**`, `README.md`
- quality configuration and existing Wave 3 evidence

## Scope
- Regression and cross-cell contract tests.
- Documentation consistency.
- Targeted quality gates and integration diagnostics.
- Ownership collision and GitNexus change-detection review.

## Write ownership
- `tests/**`
- `docs/**` unless explicitly owned by another cell.

## Constraints
- Separate pre-existing failures from regressions.
- Do not weaken tests for green status.
- Prefer targeted verification on the 8 GB M2 before broad gates.

## Deliverable
`REPORT.md` with verification evidence, regressions, documentation state, and next-wave recommendations.

## Dependency
Start after Cells 07–12 have produced reports.
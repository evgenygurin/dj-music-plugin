# Cell 06 — Quality and Documentation

## Mission
Own validation, regression coverage, and documentation updates that are not implementation-owned by another cell.

## Read
- `AGENTS.md` and relevant `rules/`
- `tests/**`
- `docs/**`
- `README.md`
- existing quality/tooling configuration
- current changelog and project specifications/plans

## Scope
- Regression and integration test coverage.
- Documentation consistency and architecture references.
- Quality-gate diagnostics.
- Cross-cutting validation that does not require changing implementation ownership.

## Write ownership
- `tests/**` by default.
- `docs/**` and documentation-facing root files when not explicitly owned elsewhere.
- Quality configuration only when explicitly delegated by parent.

## Do not touch
Implementation under `app/**`, MCP server implementation, root operational config, secrets, or another cell's files.

## Constraints
- Prefer targeted tests followed by `make check` when implementation changes exist.
- Never weaken tests merely to obtain a green gate without documenting the reason.
- Treat pre-existing failures separately from regressions introduced by a cell.
- Verify documentation claims against the actual repository.

## Deliverable
`REPORT.md` with tests run/results, documentation changes, regressions found, pre-existing failures, and recommended follow-ups.

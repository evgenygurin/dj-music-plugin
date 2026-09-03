# Cell 01 — Repository Context

## Mission
Establish the authoritative project-context baseline for later cells. Do not perform feature implementation.

## Read
- `AGENTS.md`
- `rules/`
- `pyproject.toml`
- `Makefile`
- `opencode.json`
- relevant top-level manifests/configuration

## Inspect
- Current architecture and bounded contexts.
- Existing agent instructions and skills.
- Existing quality gates and local development commands.
- GitNexus index status and repository-level execution flows.

## Write ownership
- `AGENTS.md` only if explicitly delegated by parent.
- `rules/**` only for narrowly scoped governance corrections explicitly requested by parent.
- Otherwise this cell is read-only.

## Do not touch
`app/**`, `tests/**`, `docs/**`, `opencode.json`, `pyproject.toml`, `.env*`, or another cell's files.

## Deliverable
`REPORT.md` containing architecture baseline, conventions, detected contradictions, and recommendations for other cells. No speculative refactor.

## Verification
No implementation verification is required unless this cell makes an explicitly delegated governance edit.

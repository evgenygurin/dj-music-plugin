# MECE Wave — DJ Music Plugin

> Wave planning artifact for OpenCode execution. Planning only at creation time: OpenCode MUST NOT be spawned by this file's creation.

## Objective

Create a bounded, parallelizable OpenCode cell fleet for `dj-music-plugin` without overlapping file ownership. Cells inspect and, when later authorized, implement changes inside distinct architectural domains. Parent orchestration owns cross-cutting coordination and synthesis.

## Repository snapshot

- Repository: `evgenygurin/dj-music-plugin`
- Default branch: `main`
- Baseline reviewed: commit `580870a4a4a89594720e48f6d0c1c311b7afa24a`
- Runtime: Python 3.12+, `uv`
- Architecture: FastMCP v3, bounded contexts
- Quality gate: `make check`
- Architectural guard: GitNexus impact analysis before symbol edits; `detect_changes()` before commit

## Mandatory project rules

1. Read `AGENTS.md` before any work.
2. Use `uv` for Python tooling; never invoke `python`, `pip`, `pytest`, `ruff`, or `mypy` directly.
3. Before editing a function/class/method, run GitNexus `impact` and respect HIGH/CRITICAL warnings.
4. Before commit, run GitNexus `detect_changes()`.
5. Preserve `app/domain/` purity: domain code must not depend on DB, HTTP, or FastMCP.
6. Preserve existing FastMCP/tool/resource/prompt architecture and generic dispatcher strategy.
7. Do not modify secrets or real `.env` credentials.
8. No GitHub Actions assumptions; local quality gates are authoritative.
9. Cells must not modify files owned by another cell.
10. Every execution cell must produce a `REPORT.md`; parent synthesis consumes reports only after all cells finish.

## Cell fleet

| Cell | Scope | Primary ownership | Mode |
|---|---|---|---|
| `01-repo-context` | Project conventions and architectural baseline | `AGENTS.md`, `rules/`, top-level governance/docs config | read-first / low-write |
| `02-audio-pipeline` | DSP, analysis, stems, rendering | `app/audio/`, audio-specific handlers/tests/docs | implementation |
| `03-dj-domain` | DJ domain, transitions, optimization, templates | `app/domain/`, domain-specific schemas/tests/docs | implementation |
| `04-mcp-server` | MCP composition and public surface | `app/tools/`, `app/resources/`, `app/prompts/`, `app/server/`, `server.py`, FastMCP config | implementation |
| `05-providers-and-db` | Persistence and external providers | `app/models/`, `app/repositories/`, `app/db/`, `app/providers/`, persistence/provider schemas/tests | implementation |
| `06-quality-and-docs` | Verification and documentation | `tests/`, `docs/`, quality configuration, non-owned documentation | validation / docs |

## Ownership constraints

- A cell may read the whole repository but may write only its declared ownership.
- Shared root files (`pyproject.toml`, `Makefile`, `opencode.json`, `.env.example`, `AGENTS.md`) are parent-owned unless explicitly delegated by the parent conductor.
- Cross-cell refactors are not to be silently performed. Report the required cross-cell change instead.
- `tests/` are normally owned by `06-quality-and-docs`; domain-specific test changes should be proposed to that cell or coordinated by the parent.
- Generated artifacts and caches are never cell deliverables.

## Required execution protocol

For any future OpenCode execution:

1. Establish the exact baseline SHA.
2. Read `AGENTS.md` and relevant rules/skills.
3. Inspect existing architecture before proposing edits.
4. Use GitNexus `query`/`context` for unfamiliar flows and `impact` before symbol edits.
5. Make only in-scope changes.
6. Run targeted tests first, then applicable project gates.
7. Run `gitnexus detect_changes()` and report unexpected scope.
8. Write `.mece/cells/<cell>/REPORT.md` with changes, tests, risks, and follow-ups.

## Integration policy

The parent conductor is responsible for:

- resolving cross-cell dependencies;
- deciding whether shared-file changes are necessary;
- running final integration verification;
- updating `SYNTHESIS.md`;
- committing/merging only after evidence is reviewed.

Cells must not spawn additional agents unless explicitly authorized by the parent conductor.

## Definition of done

The wave is complete only when:

- all authorized cells have produced reports;
- no ownership collision remains;
- targeted tests and relevant quality gates have evidence;
- GitNexus change detection is clean or explicitly explained;
- cross-cell follow-ups are recorded;
- final synthesis identifies accepted changes, rejected changes, risks, and next wave items.

## Current status

**PLANNED / NOT EXECUTING.** This artifact does not authorize OpenCode execution. Execution requires a separate explicit authorization.

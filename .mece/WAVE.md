# MECE Wave 4 — DJ Music Plugin

> Planning artifact. Creating or updating this file MUST NOT spawn OpenCode.
> OpenCode execution requires separate explicit authorization.

## Objective

Prepare a seven-cell, non-overlapping Wave 4 for the current repository state.
The wave prioritizes unresolved architectural gaps from Wave 3 and the current
Mem0/OpenCode worktree changes. Cells may inspect the whole repository but own
only their declared paths.

## Baseline

- Repository: `evgenygurin/dj-music-plugin`
- Branch: `mece/wave-2026-09-03`
- Current baseline: e9351f839403ec722f0ce530c69cd1c1f357ccfa
- Runtime: Python 3.12+, `uv`
- Architecture: FastMCP v3 + bounded contexts
- Machine constraint: M2 MacBook Air, 8 GB RAM; avoid heavyweight parallel jobs

## Mandatory rules

1. Read `AGENTS.md` and relevant `rules/` before work.
2. Use `uv` for Python tooling; do not call Python tooling directly.
3. Run GitNexus impact before symbol edits and `detect_changes()` before commit.
4. Preserve `app/domain/` purity and existing FastMCP dispatcher architecture.
5. Never modify secrets or real `.env` credentials.
6. Respect cell ownership; report cross-cell changes instead of editing them.
7. Every execution cell writes `REPORT.md` with evidence and unresolved risks.
8. Do not run full real Demucs inference on the local 8 GB machine unless explicitly authorized.
9. Existing uncommitted Mem0/OpenCode changes are pre-existing work and must be preserved.

## Cell fleet

| Cell | Scope | Ownership |
|---|---|---|
| 07 | Repo governance | `AGENTS.md`, `rules/` only if delegated |
| 08 | Audio pipeline | `app/audio/**`, isolated audio handlers/docs |
| 09 | DJ domain | `app/domain/**`, pure domain contracts |
| 10 | MCP server | `app/tools/**`, `app/resources/**`, `app/prompts/**`, `app/server/**` |
| 11 | Providers/DB | `app/models/**`, `app/repositories/**`, `app/db/**`, `app/providers/**` |
| 12 | Mem0 / agent memory | `.opencode/mem0-policy.js`, `.opencode/tests/**`, memory docs/specs |
| 13 | Quality/integration | `tests/**`, `docs/**` unless delegated elsewhere |

## Execution order

Cells 07–12 are independently inspectable. Cell 13 consumes their reports.
The parent conductor owns shared root files, integration, and final synthesis.

## Definition of done

All authorized cells report; ownership is clean; targeted verification exists;
GitNexus change detection is reviewed; cross-cell dependencies are explicit;
`SYNTHESIS.md` records accepted changes, rejected work, risks, and next wave.

## Current status

**EXECUTED — BOUNDED IMPLEMENTATION + RUNTIME AUDIT.**
# `docs/archive/` — Historical Documentation

> **Do not cite this tree from living docs.** The files here are frozen
> snapshots of pre-v1.0.0 design work, test artifacts, and phase-plan
> traceability. They describe paths, tools, and data shapes that no
> longer exist in the v1 bounded-contexts codebase.

## Layout

| Subdir | Contents |
|---|---|
| `designs/` | `refactor-v2.md` (superseded 5-band experiment), `agent-prompts.md` (pre-v1 batch prompts), `sync-service-api-design.md` (class-based sync proto replaced by `playlist_sync` tool) |
| `reports/` | Benchmarks, code reviews, audits, E2E tests, tool-inventory baselines from the v0.7-v0.8 era; `mcp-tools-*` refactor series |
| `reports/errors/` | Closed `BUG-NNN-*` triage notes from v0.7-v0.8 debugging |
| `plans/` | All 19 phase plans (`2026-03-27-tiered-analysis.md` through `2026-04-17-phase-7-cutover.md`). Executed and shipped as v1.0.0 |
| `notes/` | `phase-*-complete.md` + `phase-7-{preflight,postflight,migration,campaign-*}.md` — phase completion and campaign-ops notes |
| `specs/` | All pre-v1.0.0 design specs (14 files) superseded by `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` |

## What stayed in the live tree

These files remain outside `archive/` because they are cited by living docs
or remain the canonical reference:

| Path | Why kept |
|---|---|
| `docs/reports/tiered-analysis-design-2026-03-27.md` | Cited from `CLAUDE.md` + `README.md` — still the design rationale for L1→L4 pipeline |
| `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` | Canonical v1 architecture reference |
| `docs/superpowers/specs/2026-04-10-transition-recipe-engine-design.md` | Cited from `docs/transition-scoring.md` — recipe engine spec is live |
| `docs/superpowers/specs/2026-04-08-transition-system-redesign.md` | Cited from `docs/transition-scoring.md` — architecture decision record for the 6-component rebalance |
| `docs/research/2026-04-08-techno-transitions-research.md` | Cited from `docs/transition-scoring.md` — research backing the weight rebalance |
| `docs/research/2026-04-09-techno-transition-matrix.md` | Implementation cross-reference matrix for the transition subsystem |
| `docs/technical-requirements/features/*.md` | Feature specs — separate documentation lane, not pre-v1 history |

## Recovering an archived file

Everything is in git history. To restore at the old path:

```bash
git mv docs/archive/<category>/<file> docs/<category>/<file>
```

Or grep the archive tree directly — `fd . docs/archive/`.

## When to archive something new

Move a living doc here when:
- It is superseded by a newer doc (put a `HISTORICAL` banner on the old one first, then move).
- The described code/architecture is gone.
- It is a dated snapshot (benchmark, audit, E2E run) whose value is tracing "what was true then" not "what is true now".

Never archive:
- `CHANGELOG.md` — always at repo root.
- Anything cited by `CLAUDE.md`, `REQUIREMENTS.md`, `README.md`, `docs/*.md` living files, `.claude/rules/*.md`, or `.claude/agents/*.md` without first updating the citation.
- Active phase plans (none exist right now — v1.0.1 shipped).

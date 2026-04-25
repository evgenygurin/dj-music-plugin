# Dev Cleanup and Resync — Design

**Date:** 2026-04-25
**Author:** Claude Opus 4.7 (orchestrator) on behalf of repo owner
**Status:** Approved — user delegated decision-making; executing variant A.
**Successor:** implementation plan via `superpowers:writing-plans`.

---

## 1. Context

### 1.1 Observed state (snapshot 2026-04-25)

| Ref | HEAD | Drift vs `origin/main` | Notes |
|---|---|---|---|
| `origin/main` | `dfadc91` (PR #124, v1.0.4 + 7 follow-up fixes) | — | Production. `make check` expected green. |
| `dev` (local only — not on origin) | `f36b5df` (surface-redesign-v2 Phase 1 Task 1) | behind 181, ahead 20 | Stale integration branch. |
| 7× `claude/*` local | various | ahead-of-main = 0 | All commits already in `main` via squashed PRs. Dead duplicates. |
| `pr-123` local | `535b5d8` | ahead-of-main = 1 (already in `main` as `6c3ae5d` after squash) | Dead duplicate. |
| `test/openclaw-smoke-20260421-0500` | `dfadc91` | identical to `main` HEAD | Dead snapshot. |

- Open PRs: **0**.
- Open issues: **0**.
- Working tree: clean.

### 1.2 Anatomy of the 20 commits dev is ahead by

15 are pre-v1.0.1 history that already landed in `main` via squash-merges of release PRs #102/#103/#104. They linger on dev because squash-merge rewrites SHAs and `dev` was never re-synced.

5 are net-new work that exists nowhere else:

```bash
aa6254a  docs(superpowers): add surface-redesign-v2 design spec
aba0118  docs(superpowers): add Phase 1 implementation plan for surface redesign v2
b0b4bc4  test(surface): add failing test for surface module presence
4b99286  test(surface): restore missing import pytest in surface test
f36b5df  feat(surface): add ToolTransformConfig skeleton for 10 declarative managers
```

This is the start of a multi-phase feature (`surface-redesign-v2`) — Phase 1 Task 1 of ~10. Skeleton + a couple of tests; the rest of Phase 1 (and Phases 2–7) is unwritten.

### 1.3 Why dev is in this state

After v1.0.1, the workflow drifted from the documented model in `.github/BRANCH_STRATEGY.md` (`feat/* → dev → main`). All 14 PRs from #109 through #124 targeted `main` directly. The `dev` branch stopped being the integration point and became an orphan feature branch.

---

## 2. Goal

Bring `dev` to a state matching the documented branch policy: an integration branch that is **identical to `origin/main` HEAD** at the moment of cleanup, plus zero work-in-progress code, plus zero dangling references. After this, `dev` is "the final working version" the user asked for.

In-progress feature work (`surface-redesign-v2`) is preserved on a dedicated feature branch so it can re-enter `dev` through a normal PR when ready.

---

## 3. Approach (Variant A — chosen)

### 3.1 Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | `dev` is reset to `origin/main` HEAD (`dfadc91`). | Aligns with `BRANCH_STRATEGY.md`; resolves 181-commit lag in one move. |
| D2 | The 5 surface-redesign-v2 commits are preserved on a new branch `feat/surface-redesign-v2`. | No work is lost; future PR will re-introduce them once Phase 1 is complete. |
| D3 | All 9 orphan local branches (7× `claude/*`, `pr-123`, `test/openclaw-smoke-20260421-0500`) are deleted locally. | All are duplicates of `main`; they exist only on the local machine; deleting them is reversible via `git reflog` for at least 90 days. |
| D4 | Local `dev` is force-pushed to a fresh `origin/dev` so the remote matches the documented branch model. | `origin/dev` does not currently exist; this creates it cleanly. Force semantics not relevant — no upstream to overwrite. |
| D5 | No PR is opened from `dev → main` after the reset. | `dev` and `main` are pointer-equal at that moment; a PR would be a no-op. The next PR will be the one that brings `feat/surface-redesign-v2` back. |
| D6 | The `test/openclaw-smoke-20260421-0500` branch is deleted locally only. | If it exists as a tag elsewhere, that's separate. Locally it's a dead snapshot. |

### 3.2 Out of scope

- Do not rebase the 5 surface commits onto `main`. Keep them as-is on the new feature branch — they were authored against `dev`'s old base; rebasing might conflict with v1.0.2/3/4 changes. Rebasing is the responsibility of whoever resumes the feature.
- Do not modify `main`. Any "fix the cost_tracking middleware" task that came up earlier is already addressed by `main`'s commits #109 (`fix(mcp): restore runtime…`), #110 (`fix: drift between ORM/Supabase…`), #111 (`fix(mcp): repair 13 dispatch + handler bugs`). Variant A picks those up automatically. Independent verification is part of step 5.
- Do not delete the spawn_task chip the user has in their UI for the cost_tracking fix — it auto-resolves once verification confirms #109-#111 already fixed it.
- Do not touch GitHub issue or PR settings — there are none open.

### 3.3 Non-decisions (deliberately deferred)

- Whether to merge the future `feat/surface-redesign-v2` PR back into `dev` immediately after this cleanup. That happens when Phase 1 of surface-redesign-v2 is actually finished, which is a separate effort.
- Whether `feat/surface-redesign-v2` should rebase onto `main`'s newer base. Defer to whoever resumes the feature.

---

## 4. Execution outline

Six steps, each idempotent and individually verifiable:

1. **Snapshot** — record current `dev` SHA, current orphan-branch SHAs, into a transient note (`.git/RESET_BACKUP` or in-message). Reflog also retains them. Cost: seconds. Reversibility: `git reflog` → reset.
2. **Preserve surface work** — `git branch feat/surface-redesign-v2 dev` (creates new ref pointing at current `dev` HEAD `f36b5df`). Push to origin. Cost: seconds.
3. **Reset dev** — `git checkout dev && git reset --hard origin/main`. Cost: seconds. Reversibility: pre-reset SHA in reflog + `RESET_BACKUP` note.
4. **Push dev** — `git push -u origin dev` (creates `origin/dev` pointing at `dfadc91`). Cost: seconds.
5. **Verify** — run `make check` on the new `dev`. Smoke test: start REST API, hit `/api/health`, confirm `mcp_ready=true` and tool count matches expectation. Cost: 1–3 minutes.
6. **Prune orphans** — delete the 9 local-only branches. Cost: seconds. Reversibility: SHAs are in step-1 snapshot + reflog.

If step 5 fails, **stop and investigate before step 6**. Do not delete orphans until `dev` is verified green — they may carry information needed for repair.

---

## 5. Success criteria

| # | Check | How to verify |
|---|---|---|
| S1 | `dev` HEAD SHA = `origin/main` HEAD SHA | `git rev-parse dev origin/main` returns identical hashes. |
| S2 | `origin/dev` exists and matches local `dev` | `git ls-remote origin dev` matches `git rev-parse dev`. |
| S3 | `feat/surface-redesign-v2` exists locally and on origin, HEAD = `f36b5df` | `git rev-parse feat/surface-redesign-v2` and `git ls-remote origin feat/surface-redesign-v2`. |
| S4 | 9 orphan branches gone locally | `git branch` output contains only `main`, `dev`, `feat/surface-redesign-v2`. |
| S5 | `make check` exits 0 on `dev` | `cd /Users/laptop/dev/dj-music-plugin && git checkout dev && make check`. |
| S6 | REST API smoke passes | `uv run --extra http uvicorn app.rest.app:api --port 8001` → `curl /api/health` → `mcp_ready=true`. Use port 8001 to avoid clashing with anything currently on 8000. |
| S7 | A previously failing MCP tool call works (regression check that #109/#110/#111 fixes are in fact present) | `curl -X POST :8001/api/tools/entity_aggregate/call -d '{"arguments":{"entity":"track","operation":"count"}}'` returns a count, not 500. |

S7 is the critical post-condition: it confirms the cost_tracking middleware bug is actually fixed in the new `dev`. If S7 fails, the spawn_task chip needs to remain and the cleanup is not "the final working version".

---

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Step 5 fails — `make check` red on a fresh `main`. | Investigate with `engineering:debug` skill; do not proceed to step 6. Likely cause would be local env drift (uv lock, `.env` mismatch), not source code. |
| R2 | Step 7 fails — `entity_aggregate` still returns 500. | The cost_tracking fix in #109/#110/#111 didn't actually fix it (or fixed only partial). Open a fresh issue, leave the spawn_task chip, mark `dev` as "running but with a known MCP issue" rather than claiming fully clean. |
| R3 | Push of `dev` rejected (rare — origin/dev doesn't exist, so this should succeed). | If branch protection is configured for `dev`, disable it temporarily or push to a different name and ask the user to rename. |
| R4 | Step 6 deletes a branch that turns out to contain unique work. | Step 1 snapshot + reflog covers 90 days; 30-second `git branch <name> <sha>` recovery. Risk is real but cheap to undo. |
| R5 | Loss of historical context for surface-redesign-v2 once it's no longer on `dev`. | Mitigated by step 2 + design docs `2026-04-17-architecture-blueprint-design.md` and `2026-04-18-surface-redesign-v2-design.md` already in `main` history. |

---

## 7. Verification skill chain

The execution phase will use the following skills in order:

1. `superpowers:writing-plans` — turn this design into a step-by-step implementation plan with explicit checkpoints.
2. `superpowers:executing-plans` — drive the plan with TDD-discipline checkpoints.
3. `superpowers:verification-before-completion` — gate before any "done" claim; runs S1–S7.
4. `superpowers:finishing-a-development-branch` — once verified, decide branch hand-off (no PR needed since dev = main; the skill confirms that).

This order matches the "process skills first, implementation skills second" rule from `using-superpowers`.

---

## 8. Sign-off

User explicitly delegated decision-making ("сам принимай все решения"). This counts as approval to proceed without iterative section-by-section review.

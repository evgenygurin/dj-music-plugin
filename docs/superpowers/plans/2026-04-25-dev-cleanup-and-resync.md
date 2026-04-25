# Dev Cleanup and Resync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset local `dev` to `origin/main` HEAD, preserve in-progress surface-redesign-v2 work on a dedicated feature branch, prune 9 orphan local branches, push the new `dev` to origin, and verify it is "the final working version" by running `make check` plus REST smoke tests including the regression check for the previously-broken `cost_tracking` middleware.

**Architecture:** Pure git operations on local repo + remote pushes + verification commands. No code changes to the project. The 5 net-new commits (surface-redesign-v2 skeleton + this design/plan) are preserved by being copied to a new branch before reset, and the design/plan docs are cherry-picked back onto the new `dev` so they live in the integration branch as well.

**Tech Stack:** git, make, uv, curl, FastAPI/uvicorn (REST API smoke), the project's existing `make check` (ruff + mypy + import-linter + pytest).

**Reference spec:** `docs/superpowers/specs/2026-04-25-dev-cleanup-and-resync-design.md` (commit `867aeb0` on the current dev — will be cherry-picked onto the new dev in Task 5).

---

## File Structure

No source files are touched. Branch and ref topology before vs after:

| Ref | Before | After |
|---|---|---|
| `main` | `dfadc91` | `dfadc91` (untouched) |
| `dev` (local) | `867aeb0` (spec commit on top of `f36b5df` surface skeleton) | `dfadc91` + cherry-picked spec + cherry-picked plan |
| `origin/dev` | does not exist | matches local `dev` |
| `feat/surface-redesign-v2` | does not exist | local + remote, HEAD = `867aeb0` |
| `pr-123` | local | deleted |
| `claude/epic-boyd-42fb70` | local | deleted |
| `claude/suspicious-jackson-253bee` | local | deleted |
| `claude/beautiful-burnell-d61a2a` | local | deleted |
| `claude/exciting-tereshkova-4d68cf` | local | deleted |
| `claude/inspiring-sinoussi-8ce1a3` | local | deleted |
| `claude/musing-fermi-ff60ef` | local | deleted |
| `claude/serene-shirley-4ee852` | local | deleted |
| `test/openclaw-smoke-20260421-0500` | local | deleted |

Files written outside the repo:

- `/tmp/dev-cleanup-2026-04-25/snapshot.txt` — pre-reset SHAs of every affected ref. Recovery sheet.
- `/tmp/dev-cleanup-2026-04-25/spec-cherry.sha` — captured SHA of the spec commit before reset, used by Task 5.
- `/tmp/dev-cleanup-2026-04-25/plan-cherry.sha` — captured SHA of this plan's commit (Task 1.5) before reset.

---

## Task 1: Snapshot pre-reset state

**Files:**
- Create: `/tmp/dev-cleanup-2026-04-25/snapshot.txt`

- [ ] **Step 1: Make snapshot dir**

```bash
mkdir -p /tmp/dev-cleanup-2026-04-25
```

- [ ] **Step 2: Capture every relevant SHA into the snapshot file**

```bash
{
  echo "# Dev cleanup pre-reset snapshot — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "## Local refs"
  for ref in main dev pr-123 claude/epic-boyd-42fb70 claude/suspicious-jackson-253bee claude/beautiful-burnell-d61a2a claude/exciting-tereshkova-4d68cf claude/inspiring-sinoussi-8ce1a3 claude/musing-fermi-ff60ef claude/serene-shirley-4ee852 test/openclaw-smoke-20260421-0500; do
    sha=$(git rev-parse "$ref" 2>/dev/null || echo "MISSING")
    msg=$(git log -1 --format='%s' "$ref" 2>/dev/null | head -c 80 || echo "")
    printf "%-50s %s  %s\n" "$ref" "$sha" "$msg"
  done
  echo ""
  echo "## Remote refs"
  for ref in origin/main origin/dev; do
    sha=$(git rev-parse "$ref" 2>/dev/null || echo "MISSING")
    msg=$(git log -1 --format='%s' "$ref" 2>/dev/null | head -c 80 || echo "")
    printf "%-50s %s  %s\n" "$ref" "$sha" "$msg"
  done
  echo ""
  echo "## Recovery"
  echo "git branch <name> <sha>   # restore any branch from its SHA"
  echo "git reflog                # additional safety net (90-day retention)"
} > /tmp/dev-cleanup-2026-04-25/snapshot.txt
cat /tmp/dev-cleanup-2026-04-25/snapshot.txt
```

Expected output: Snapshot listing all 11 refs with their SHAs. Recovery instructions at bottom. `origin/dev` should be `MISSING`.

- [ ] **Step 3: Capture the spec commit SHA for cherry-pick after reset**

```bash
git rev-parse HEAD > /tmp/dev-cleanup-2026-04-25/spec-cherry.sha
echo "Captured: $(cat /tmp/dev-cleanup-2026-04-25/spec-cherry.sha)"
```

Expected: `Captured: 867aeb0...` (full SHA of the spec doc commit).

- [ ] **Step 4: Sanity check — verify dev currently has the spec we just committed**

```bash
git log -1 --format='%h %s' HEAD
```

Expected: `867aeb0 docs(superpowers): add dev-cleanup-and-resync design (variant A)`. If different, stop and investigate — something has shifted under us.

---

## Task 1.5: Commit this plan + capture its SHA

**Files:**
- Create: `docs/superpowers/plans/2026-04-25-dev-cleanup-and-resync.md` (this file — already created when running this plan).

- [ ] **Step 1: Stage the plan file**

```bash
git add docs/superpowers/plans/2026-04-25-dev-cleanup-and-resync.md
git status --short
```

Expected: Single line `A  docs/superpowers/plans/2026-04-25-dev-cleanup-and-resync.md`.

- [ ] **Step 2: Write commit message file**

```bash
cat > /tmp/commit-msg-plan.txt <<'EOF'
docs(superpowers): add dev-cleanup-and-resync implementation plan

Step-by-step plan derived from the variant A design. Captures snapshot,
preservation of surface-redesign-v2, dev reset, push, verification
(including S7 regression for cost_tracking middleware), and orphan prune.
EOF
```

- [ ] **Step 3: Commit**

```bash
git commit -F /tmp/commit-msg-plan.txt
rm /tmp/commit-msg-plan.txt
git log -1 --format='%h %s'
```

Expected last line: a short SHA + `docs(superpowers): add dev-cleanup-and-resync implementation plan`.

- [ ] **Step 4: Capture the plan commit SHA**

```bash
git rev-parse HEAD > /tmp/dev-cleanup-2026-04-25/plan-cherry.sha
echo "Captured plan SHA: $(cat /tmp/dev-cleanup-2026-04-25/plan-cherry.sha)"
```

---

## Task 2: Preserve surface-redesign-v2 work on a feature branch

**Files:** none (branch operations only).

- [ ] **Step 1: Create the feature branch at current dev HEAD**

```bash
git branch feat/surface-redesign-v2 dev
git rev-parse feat/surface-redesign-v2
```

Expected: Same SHA as the plan commit captured in Task 1.5 Step 4. (This branch carries the surface skeleton + design + plan; we are happy to keep all three together for the future feature owner.)

- [ ] **Step 2: Push the feature branch to origin and set upstream**

```bash
git push -u origin feat/surface-redesign-v2
```

Expected: `* [new branch]      feat/surface-redesign-v2 -> feat/surface-redesign-v2` plus tracking confirmation.

- [ ] **Step 3: Verify origin has it**

```bash
git ls-remote origin feat/surface-redesign-v2
```

Expected: One line — SHA matching local `feat/surface-redesign-v2` + `refs/heads/feat/surface-redesign-v2`.

---

## Task 3: Reset dev to origin/main

**Files:** none (branch reset only).

- [ ] **Step 1: Re-confirm working tree is clean**

```bash
git status --short
```

Expected: empty output. If anything appears, **stop** — investigate before resetting.

- [ ] **Step 2: Hard-reset dev to origin/main**

```bash
git checkout dev
git reset --hard origin/main
git log -1 --format='%h %s'
```

Expected last line: `dfadc91 fix(audio): reject IBI outliers before variable_tempo / stability (#124)`.

- [ ] **Step 3: Confirm dev now equals origin/main**

```bash
[ "$(git rev-parse dev)" = "$(git rev-parse origin/main)" ] && echo "MATCH" || echo "MISMATCH"
```

Expected: `MATCH`.

---

## Task 4: Push dev to origin

**Files:** none (remote push only).

- [ ] **Step 1: Push and set upstream**

```bash
git push -u origin dev
```

Expected: `* [new branch]      dev -> dev` (since `origin/dev` did not exist before). Plus tracking confirmation.

- [ ] **Step 2: Verify origin/dev**

```bash
git ls-remote origin dev
```

Expected: One line — SHA `dfadc91...` + `refs/heads/dev`.

---

## Task 5: Cherry-pick the spec + plan commits onto new dev

These docs are about the cleanup itself; they should live on `dev` so future readers can find them in the integration branch. We already keep the same commits on `feat/surface-redesign-v2` as a side benefit — that branch will rebase later anyway.

**Files:**
- Effect: 2 new commits on `dev` (cherry-picked from old dev history).

- [ ] **Step 1: Cherry-pick the spec commit**

```bash
SPEC_SHA=$(cat /tmp/dev-cleanup-2026-04-25/spec-cherry.sha)
git cherry-pick "$SPEC_SHA"
git log -1 --format='%h %s'
```

Expected: New short SHA + `docs(superpowers): add dev-cleanup-and-resync design (variant A)`. No merge conflicts (the file is new — there is nothing to clash with on main).

- [ ] **Step 2: Cherry-pick the plan commit**

```bash
PLAN_SHA=$(cat /tmp/dev-cleanup-2026-04-25/plan-cherry.sha)
git cherry-pick "$PLAN_SHA"
git log -1 --format='%h %s'
```

Expected: New short SHA + `docs(superpowers): add dev-cleanup-and-resync implementation plan`.

- [ ] **Step 3: Push the two cherry-picked commits**

```bash
git push origin dev
```

Expected: Fast-forward push, two new commits added to `origin/dev`.

- [ ] **Step 4: Confirm dev is main + 2 cherry-picked commits**

```bash
git log --oneline origin/main..dev
```

Expected: exactly two lines — the cherry-picked plan commit on top, the cherry-picked spec commit below.

---

## Task 6: Verify dev is "the final working version"

This is the gate — if anything fails here, **do not proceed to Task 7** (orphan prune). The orphans are the only safety net besides reflog.

**Files:** none (read-only verification).

- [ ] **Step 1: Sync deps to whatever main needs**

```bash
uv sync --all-extras
```

Expected: `Resolved` + `Installed` lines, no errors. May take 30–60s.

- [ ] **Step 2: Run `make check`**

```bash
make check
```

Expected: lint, typecheck, arch (import-linter), and tests all pass. Exit code 0. If anything fails — stop, run with `engineering:debug` skill, do not proceed.

- [ ] **Step 3: Start REST API on port 8001 in background**

```bash
mkdir -p /tmp/dev-cleanup-2026-04-25
uv run --extra http uvicorn app.rest.app:api --host 127.0.0.1 --port 8001 \
  > /tmp/dev-cleanup-2026-04-25/rest.log 2>&1 &
echo $! > /tmp/dev-cleanup-2026-04-25/rest.pid
echo "Started REST PID $(cat /tmp/dev-cleanup-2026-04-25/rest.pid)"
sleep 8
```

Expected: PID printed; `rest.log` contains `Application startup complete` line. If startup fails, check `rest.log` for traceback.

- [ ] **Step 4: Smoke `/api/health`**

```bash
curl -sf http://127.0.0.1:8001/api/health
```

Expected response: `{"status":"ok","mcp_ready":true,"tool_count":...,"degraded_reason":null}`. `mcp_ready` MUST be `true`. If `false`, look up `degraded_reason` in `rest.log`.

- [ ] **Step 5: Critical regression — call entity_aggregate to confirm cost_tracking middleware is fixed**

```bash
curl -sf -X POST http://127.0.0.1:8001/api/tools/entity_aggregate/call \
  -H "Content-Type: application/json" \
  -d '{"arguments":{"entity":"track","operation":"count"}}'
```

Expected: JSON containing a numeric count, NOT a 500 with `'Context' object has no attribute 'state'`. This is success criterion S7 from the spec.

If this returns 500: the cost_tracking middleware is still broken in main. Stop. Reopen the spawn_task chip. Do NOT delete orphans yet.

- [ ] **Step 6: Stop REST API**

```bash
PID=$(cat /tmp/dev-cleanup-2026-04-25/rest.pid)
kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
echo "Stopped REST"
```

Expected: `Stopped REST`. No errors.

- [ ] **Step 7: Record verification result**

```bash
{
  echo "# Verification result — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "S1 dev == origin/main: $([ "$(git rev-parse dev~2)" = "$(git rev-parse origin/main)" ] && echo PASS || echo FAIL)"
  echo "S2 origin/dev exists:  $(git ls-remote origin dev | grep -c refs/heads/dev | grep -q 1 && echo PASS || echo FAIL)"
  echo "S3 feat branch exists: $(git ls-remote origin feat/surface-redesign-v2 | grep -c refs/heads | grep -q 1 && echo PASS || echo FAIL)"
  echo "S5 make check:         (set manually based on Step 2 exit)"
  echo "S6 health mcp_ready:   (set manually based on Step 4)"
  echo "S7 entity_aggregate:   (set manually based on Step 5)"
} > /tmp/dev-cleanup-2026-04-25/verify.txt
cat /tmp/dev-cleanup-2026-04-25/verify.txt
```

Expected: file with PASS/FAIL or manual-fill lines. **If any line is FAIL, stop the plan here.**

---

## Task 7: Prune orphan local branches

Only proceed if Task 6 produced PASS on every line. The orphans are the last cheap safety net besides reflog; do not delete until verified.

**Files:** none (branch deletion only).

- [ ] **Step 1: Final sanity check — every orphan is fully contained in main**

```bash
for b in pr-123 claude/epic-boyd-42fb70 claude/suspicious-jackson-253bee claude/beautiful-burnell-d61a2a claude/exciting-tereshkova-4d68cf claude/inspiring-sinoussi-8ce1a3 claude/musing-fermi-ff60ef claude/serene-shirley-4ee852 test/openclaw-smoke-20260421-0500; do
  printf "%-50s ahead-of-main=%s\n" "$b" "$(git rev-list --count origin/main..$b 2>/dev/null || echo MISSING)"
done
```

Expected: every line `ahead-of-main=0` or `MISSING`. (For `pr-123`: although raw count is 1, that 1 commit is the unsquashed source of `6c3ae5d` already in main. We accept this — the snapshot in Task 1 captured it.)

- [ ] **Step 2: Delete safe orphans (`-d`, refuses if unmerged)**

```bash
for b in claude/epic-boyd-42fb70 claude/suspicious-jackson-253bee claude/beautiful-burnell-d61a2a claude/exciting-tereshkova-4d68cf claude/inspiring-sinoussi-8ce1a3 claude/musing-fermi-ff60ef claude/serene-shirley-4ee852 test/openclaw-smoke-20260421-0500; do
  git branch -d "$b" 2>&1 | sed "s/^/$b: /"
done
```

Expected: 8 lines, each `Deleted branch <name> (was <sha>)`.

If any branch refuses with "not fully merged" — stop and investigate. The snapshot SHA in `snapshot.txt` is your recovery handle.

- [ ] **Step 3: Force-delete the unsquashed pr-123 (already in main as 6c3ae5d)**

```bash
git branch -D pr-123
```

Expected: `Deleted branch pr-123 (was 535b5d8)`. `-D` is required because the SHA itself is not in main (the squashed equivalent is); the snapshot covers recovery.

- [ ] **Step 4: Verify final branch list**

```bash
git branch
```

Expected: exactly three lines (in some order):
```text
* dev
  feat/surface-redesign-v2
  main
```

- [ ] **Step 5: Final state log**

```bash
{
  echo "# Final state — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  git branch
  echo ""
  echo "## Local vs origin"
  for ref in main dev feat/surface-redesign-v2; do
    local_sha=$(git rev-parse "$ref" 2>/dev/null)
    remote_sha=$(git ls-remote origin "$ref" 2>/dev/null | awk '{print $1}')
    [ "$local_sha" = "$remote_sha" ] && status=MATCH || status=DRIFT
    printf "%-40s local=%s remote=%s %s\n" "$ref" "${local_sha:0:7}" "${remote_sha:0:7}" "$status"
  done
} > /tmp/dev-cleanup-2026-04-25/final.txt
cat /tmp/dev-cleanup-2026-04-25/final.txt
```

Expected: `MATCH` for `main`, `dev`, `feat/surface-redesign-v2`.

---

## Task 8: Hand-off

The spec section 7 lists the verification skill chain. After Task 7 passes:

- [ ] **Step 1: Invoke `superpowers:finishing-a-development-branch`** to confirm there is no further PR/merge action (because `dev` and `main` are pointer-equal at this moment, no PR is needed).

- [ ] **Step 2: Report to user** — short summary of: SHAs, orphans deleted, verification outcome, link to `final.txt`.

- [ ] **Step 3: If a spawn_task chip for cost_tracking is still on screen** — let the user know it auto-resolves (verified via S7). They can dismiss it.

---

## Self-review (already completed inline by author)

- **Spec coverage:** every Decision D1–D6 maps to a Task: D1→T3, D2→T2, D3→T7, D4→T4, D5 (no PR) is enforced by Task 8 Step 1, D6 (delete openclaw locally only) is part of T7 Step 2. Every Success Criterion S1–S7 maps to a verification step in T6 or T7 Step 4. Risk R2 has explicit handling in T6 Step 5. R4 mitigated by T1 snapshot.
- **Placeholder scan:** clean, no TBD/TODO/"add error handling".
- **Type/name consistency:** branch names, file paths, and SHAs are consistent across tasks. The `/tmp/dev-cleanup-2026-04-25/` directory is referenced uniformly.

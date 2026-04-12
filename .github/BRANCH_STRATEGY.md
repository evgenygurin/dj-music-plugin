# Branch Strategy

## Flow: Simplified Git Flow (Solo + AI)

```text
main ← production-ready, always deployable
  ↑ squash merge (PR only, never direct push)
dev  ← integration branch, all work merges here first
  ↑ squash merge or rebase (PR)
feat/*, fix/*, chore/* ← short-lived feature branches
```

## Rules

### 1. NEVER push directly to main
All changes reach main ONLY via PR from dev.
No cherry-picks to main. No direct commits. No force-push.

### 2. dev is the single integration point
Every feature branch merges into dev first.
dev accumulates changes. When stable → PR to main.

### 3. Feature branches are short-lived
Branch from dev, merge back to dev within 1-3 days.
Delete after merge (auto-delete enabled).

### 4. main ← dev sync cadence
After every major feature or milestone: create PR dev → main.
Keep them in sync — never let them diverge more than ~10 commits.

### 5. No cross-branch cherry-picks
Cherry-picking between main and dev caused the April 2026 divergence.
If a hotfix is needed on main: branch from main, fix, PR to main, then merge main back into dev.

## Branch naming

```text
feat/<scope>-<description>    # new feature
fix/<scope>-<description>     # bug fix
chore/<description>            # deps, config, CI
docs/<description>             # documentation
refactor/<scope>-<description> # code improvement
```

## Merge strategy

| Target | Strategy | Why |
|--------|----------|-----|
| dev ← feature | Squash merge | Clean single-commit history on dev |
| main ← dev | Squash merge | One commit per release on main |

## Anti-patterns (what went wrong)

1. ❌ Merging a massive restructuring PR directly to main, bypassing dev
2. ❌ Cherry-picking individual commits between main and dev
3. ❌ Working on main for "quick fixes" instead of branching from dev
4. ❌ Letting main and dev diverge for weeks without syncing

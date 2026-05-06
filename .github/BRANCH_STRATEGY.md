# Branch Strategy

## Flow: PR-to-main (Solo + AI)

```text
main ← production-ready, default branch, only mover via PR
  ↑ squash merge (PR only, never direct push)
release/*, feat/*, fix/*, chore/*, docs/*, refactor/* ← short-lived
```

The historical `dev` integration branch was retired 2026-05-07 — it
had been frozen at v1.0.8 (#129) for two weeks while v1.2.x and
v1.3.x shipped via PRs straight from `release/*` into `main`. The
documented dev→main path no longer matched practice, so the branch
was deleted and this strategy was rewritten to match what actually
happens.

## Rules

### 1. NEVER push directly to main

All changes reach `main` ONLY via PR. The pre-push hook
(`hooks/pre-push`) blocks `git push origin main` from a checked-out
`main`.

### 2. Branch from main, PR to main

Every short-lived branch starts from current `main` and lands back
into `main` via squash-merge. There is no integration branch.

### 3. Feature branches are short-lived

Branch from main, merge back within 1-3 days. GitHub auto-deletes the
remote branch on merge (`gh pr merge --squash --delete-branch`).

### 4. Squash, not merge

The repo only enables **squash merge** (and rebase merge as a backup).
Plain merge commits are disabled. One PR = one squash commit on main.

### 5. Releases live in `release/vX.Y.Z` branches

The release flow:
1. Branch `release/vX.Y.Z` from main.
2. Bump `pyproject.toml` / `CLAUDE.md` / `.claude-plugin/{plugin,marketplace}.json` / `CHANGELOG.md` and commit.
3. PR → main, squash-merge.
4. Tag the squash commit (`git tag -a vX.Y.Z`), push tag.
5. `gh release create vX.Y.Z --notes-file <CHANGELOG section>`.

See PR #199 (v1.3.5) and PR #200 (v1.3.6) for canonical examples.

## Branch naming

```text
release/v<X>.<Y>.<Z>           # version bump + CHANGELOG
feat/<scope>-<description>     # new feature
fix/<scope>-<description>      # bug fix
chore/<description>            # deps, config, CI, cleanup
docs/<description>             # documentation
refactor/<scope>-<description> # code improvement
```

## Merge strategy

| Setting | Value |
|---------|-------|
| Squash merge | enabled (default) |
| Rebase merge | enabled (backup) |
| Plain merge commits | disabled |
| Auto-delete branch on merge | enabled |
| Default branch | `main` |

## Anti-patterns (what went wrong, lessons kept)

1. ❌ Merging a massive restructuring PR directly to main without a PR.
2. ❌ Cherry-picking individual commits between long-lived branches.
3. ❌ Letting an integration branch (`dev`) drift for weeks unused while
   work landed elsewhere — the contradiction between the documented
   strategy and the actual flow caused confusion in May 2026.

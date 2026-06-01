---
description: Git workflow, branching, versioning, release process
alwaysApply: true
---

# Git Workflow — Project Rules

Extends global `~/.claude/rules/git.md`. Project-specific overrides below.

## Branch Strategy

See `.github/BRANCH_STRATEGY.md` for full details.

```text
main ← production-ready, default branch, only mover via PR
release/*, feat/*, fix/*, chore/*, docs/*, refactor/* ← short-lived
```

The historical `dev` integration branch was retired 2026-05-07 — the
documented dev→main path no longer matched practice (v1.2.x and v1.3.x
all shipped via PRs straight from `release/*` into `main`).

## Critical Rules

1. **NEVER push directly to main** — pre-push hook blocks it.
2. **Branch from main, PR back into main** — there is no integration branch.
3. **Squash-merge** is the only sanctioned merge strategy on main.
4. **Feature branches**: max 1-3 days, GitHub auto-deletes the remote branch on merge.
5. **Releases live in `release/vX.Y.Z`** branches — see release flow below.

## Merge Settings (configured via gh API)

| Setting | Value |
|---------|-------|
| Squash merge | ✅ enabled (default) |
| Merge commits | ❌ disabled |
| Rebase merge | ✅ enabled (backup) |
| Auto-delete branches | ✅ enabled |
| Default branch | main |

## Pre-push Hook

`hooks/pre-push` does two things on every push:

1. Prevents direct pushes to `main` when the current branch is `main`.
2. Runs `make check` (lint + typecheck + arch + test) locally before
   the push completes — the same gate as CI, run for FREE on the dev
   machine so development never depends on GitHub Actions being
   available (Actions on a public repo are free, but an account-level
   billing lock can still disable them). Skipped on branch deletes.
   Emergency bypass: `DJ_SKIP_CHECK=1 git push ...`.

Installed via: `ln -sf ../../hooks/pre-push .git/hooks/pre-push`.

## PR Conventions

- Template: `.github/pull_request_template.md`
- Title: `<type>(<scope>): <description>` (max 70 chars)
- Target: `main`
- Checklist includes `make check` pass

## Versioning (SemVer)

Single source of truth: `pyproject.toml` → `version = "X.Y.Z"`. The
same value is mirrored in `CLAUDE.md`, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`.

| Bump | When | Example |
|------|------|---------|
| MAJOR (X) | Breaking MCP tool interface changes | 1.0.0 |
| MINOR (Y) | New tools, features, analyzers | 0.7.0 → 0.8.0 |
| PATCH (Z) | Bug fixes, metadata, docs, refactors | 0.7.0 → 0.7.1 |

## Release checklist (PR-based)

```bash
# 1. Branch from current main
git checkout main && git pull --ff-only
git checkout -b release/vX.Y.Z

# 2. Bump version everywhere + CHANGELOG
# - pyproject.toml: version = "X.Y.Z"
# - CLAUDE.md: "Текущая версия:" line
# - .claude-plugin/plugin.json + marketplace.json: "version"
# - CHANGELOG.md: insert ## [X.Y.Z] - YYYY-MM-DD section

# 3. Commit + push
git add pyproject.toml CLAUDE.md CHANGELOG.md \
        .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -F /tmp/commit-msg.txt   # see global rules for format
git push -u origin release/vX.Y.Z

# 4. PR + squash-merge
gh pr create --base main --title "release: vX.Y.Z — <summary>" \
             --body-file /tmp/pr-body.md
gh pr merge <num> --squash --delete-branch

# 5. Sync local main
git checkout main && git pull --ff-only

# 6. Tag the squash commit + push tag
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z

# 7. GitHub Release
gh release create vX.Y.Z --title "vX.Y.Z — <summary>" \
                         --notes-file /tmp/release-notes.md

# 8. (Опционально) Manifest validation pre-tag — на pre-push hook нет, рекомендуется вручную
claude plugin validate .   # проверяет plugin.json + marketplace.json + frontmatter

# 9. User-side apply (что выполнить пользователям после tag-push)
# claude plugin marketplace update dj-music-plugin   # подтянуть свежий marketplace.json
# claude plugin update dj-music@dj-music-plugin      # apply (требует restart Claude Code)
```

Canonical examples: PR #199 (v1.3.5), PR #200 (v1.3.6), PR #214 (v1.3.7).

### Tag naming: `vX.Y.Z` (with `v` prefix)

### CHANGELOG format: Keep a Changelog (Added/Changed/Fixed/Removed)

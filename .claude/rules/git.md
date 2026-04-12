# Git Workflow — Project Rules

Extends global `~/.claude/rules/git.md`. Project-specific overrides below.

## Branch Strategy

See `.github/BRANCH_STRATEGY.md` for full details.

```text
main ← production, squash-merge PRs from dev ONLY
dev  ← integration, all work merges here
feat/*, fix/*, chore/* ← short-lived, branch from dev
```

## Critical Rules

1. **NEVER push directly to main** — pre-push hook blocks it
2. **NEVER cherry-pick between main and dev** — caused April 2026 divergence
3. **ALL PRs target dev** unless hotfix (then main → merge main back to dev)
4. **Sync cadence**: PR dev → main after each milestone (~10 commits max drift)
5. **Feature branches**: max 1-3 days, delete after merge

## Merge Settings (configured via gh API)

| Setting | Value |
|---------|-------|
| Squash merge | ✅ enabled (default) |
| Merge commits | ❌ disabled |
| Rebase merge | ✅ enabled |
| Auto-delete branches | ✅ enabled |
| Default branch | main |

## Pre-push Hook

`hooks/pre-push` prevents direct pushes to main from main branch.
Installed via: `ln -sf ../../hooks/pre-push .git/hooks/pre-push`

## PR Conventions

- Template: `.github/pull_request_template.md`
- Title: `<type>(<scope>): <description>` (max 70 chars)
- Target: `dev` (not `main`)
- Checklist includes `make check` pass

## When to sync main

After completing a milestone or ~10 dev commits:
```bash
gh pr create --base main --head dev --title "Release: <milestone>"
gh pr merge <num> --squash
```

## Versioning (SemVer)

Single source of truth: `pyproject.toml` → `version = "X.Y.Z"`

| Bump | When | Example |
|------|------|---------|
| MAJOR (X) | Breaking MCP tool interface changes | 1.0.0 |
| MINOR (Y) | New tools, features, analyzers | 0.7.0 → 0.8.0 |
| PATCH (Z) | Bug fixes, metadata, docs, refactors | 0.7.0 → 0.7.1 |

### Release checklist

```bash
# 1. Update version
# pyproject.toml: version = "X.Y.Z"
# CLAUDE.md: version line
# CHANGELOG.md: move [Unreleased] → [X.Y.Z] — YYYY-MM-DD

# 2. Commit
git add pyproject.toml CLAUDE.md CHANGELOG.md
git commit -m "release: vX.Y.Z"

# 3. Tag
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin dev --tags
git push origin dev:main --tags

# 4. GitHub Release
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file /tmp/release-notes.md
```

### Tag naming: `vX.Y.Z` (with `v` prefix)

### CHANGELOG format: Keep a Changelog (Added/Changed/Fixed/Removed)

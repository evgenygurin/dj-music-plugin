#!/usr/bin/env bash
# Release script: bump version → update files → commit → tag → push → GitHub release
#
# Usage: ./scripts/release.sh 0.7.2 "Brief description"
#   or:  make release VERSION=0.7.2 DESC="Brief description"
set -euo pipefail

VERSION="${1:?Usage: release.sh VERSION DESCRIPTION}"
DESCRIPTION="${2:?Usage: release.sh VERSION DESCRIPTION}"
TAG="v${VERSION}"

echo "=== Releasing ${TAG} ==="

# 1. Verify on dev branch (we release from dev, then sync to main)
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "dev" ]; then
    echo "ERROR: Must be on dev branch (currently on ${BRANCH})"
    exit 1
fi

# 2. Verify clean working tree
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working tree is dirty. Commit or stash changes first."
    exit 1
fi

# 3. Verify tag doesn't already exist
if git rev-parse "${TAG}" >/dev/null 2>&1; then
    echo "ERROR: Tag ${TAG} already exists."
    exit 1
fi

# 4. Update version in pyproject.toml (single source of truth)
sed -i '' "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml

# 5. Update version in non-Python files (can't read pyproject.toml)
sed -i '' "s/\"version\": \"[0-9]*\.[0-9]*\.[0-9]*\"/\"version\": \"${VERSION}\"/g" \
    .claude-plugin/plugin.json \
    .claude-plugin/marketplace.json

sed -i '' "s/^version: [0-9]*\.[0-9]*\.[0-9]*/version: ${VERSION}/" \
    skills/*/SKILL.md

# 6. Update CLAUDE.md version line
sed -i '' "s/Plugin v[0-9]*\.[0-9]*\.[0-9]*/Plugin v${VERSION}/" CLAUDE.md

# 7. Verify CHANGELOG has entry for this version
if ! grep -q "\[${VERSION}\]" CHANGELOG.md; then
    echo "ERROR: CHANGELOG.md has no entry for [${VERSION}]."
    echo "Add a ## [${VERSION}] section before running release."
    exit 1
fi

# 8. Commit version bump
git add pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json \
    skills/*/SKILL.md CLAUDE.md
git commit -m "chore(release): bump version to ${VERSION}"

# 9. Create annotated tag
git tag -a "${TAG}" -m "${TAG} — ${DESCRIPTION}"

# 10. Push dev + tag
git push origin dev --tags

# 11. Sync main
git push origin dev:main

# 12. Extract release notes from CHANGELOG and create GitHub release
awk "/^## \[${VERSION}\]/,/^## \[/" CHANGELOG.md | head -n -1 > /tmp/release-notes-${VERSION}.md
gh release create "${TAG}" \
    --title "${TAG} — ${DESCRIPTION}" \
    --notes-file "/tmp/release-notes-${VERSION}.md" \
    --verify-tag
rm -f "/tmp/release-notes-${VERSION}.md"

echo ""
echo "=== Released ${TAG} ==="
echo "https://github.com/evgenygurin/dj-music-plugin/releases/tag/${TAG}"

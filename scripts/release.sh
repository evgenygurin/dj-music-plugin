#!/usr/bin/env bash
# Финализация релиза vX.Y.Z — тег + GitHub Release по канону
# .claude/rules/git.md § "Release checklist".
#
#   bash scripts/release.sh            # версия берётся из pyproject.toml
#   bash scripts/release.sh 1.5.0      # явная версия
#   DRY_RUN=1 bash scripts/release.sh  # только проверки, без push/release
#
# Что делает (идемпотентно — повторный запуск не ломает уже сделанные шаги):
#   1. Резолвит версию (arg || pyproject.toml) и сверяет её во всех манифестах
#      (pyproject.toml, .claude-plugin/plugin.json + marketplace.json, CLAUDE.md).
#   2. Находит squash-коммит релиза на origin/main.
#   3. Создаёт аннотированный тег vX.Y.Z (если ещё нет) и пушит его.
#   4. Извлекает секцию [X.Y.Z] из CHANGELOG.md в release notes.
#   5. Создаёт GitHub Release через gh (если ещё нет).
#
# ВАЖНО: запускать там, где есть реальный git-доступ (локальный терминал или
# `claude --teleport`). В облачной песочнице claude.ai/code egress-прокси
# блокирует push тегов (refs/tags/* → 403) и api.github.com — теги/релизы
# оттуда создать нельзя (см. docs/dev-mode.md § "Доступ ... по окружениям").

set -u

cd "$(dirname "$0")/.." || exit 1

DRY_RUN="${DRY_RUN:-0}"

die() { echo "❌ $*" >&2; exit 1; }
note() { echo "→ $*"; }

# ── 1. Версия + сверка манифестов ──────────────────────────────────────────
VERSION="${1:-}"
PYPROJECT_VERSION="$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')"
[ -n "$PYPROJECT_VERSION" ] || die "не нашёл version в pyproject.toml"
VERSION="${VERSION:-$PYPROJECT_VERSION}"
TAG="v${VERSION}"
note "релиз $TAG"

check_manifest() {
  local label="$1" file="$2" got="$3"
  [ "$got" = "$VERSION" ] || die "$label ($file) = '$got', ожидалось '$VERSION'"
  note "  $label = $got ✓"
}
check_manifest "pyproject.toml" pyproject.toml "$PYPROJECT_VERSION"
check_manifest "plugin.json" .claude-plugin/plugin.json \
  "$(grep -m1 '"version"' .claude-plugin/plugin.json | sed -E 's/.*"version": *"([^"]+)".*/\1/')"
check_manifest "marketplace.json" .claude-plugin/marketplace.json \
  "$(grep -m1 '"version"' .claude-plugin/marketplace.json | sed -E 's/.*"version": *"([^"]+)".*/\1/')"

grep -q "## \[${VERSION}\]" CHANGELOG.md || die "в CHANGELOG.md нет секции [## ${VERSION}]"
note "  CHANGELOG.md содержит [${VERSION}] ✓"

# ── 2. Squash-коммит релиза на origin/main ─────────────────────────────────
git fetch origin --quiet || die "git fetch origin упал"
COMMIT="$(git rev-parse origin/main)"
note "origin/main = ${COMMIT:0:10}"
git merge-base --is-ancestor "$COMMIT" origin/main || die "$COMMIT не на origin/main"

# ── 3. Release notes из CHANGELOG ──────────────────────────────────────────
NOTES_FILE="$(mktemp -t release-notes-XXXXXX.md)"
# От строки "## [X.Y.Z]" до следующей "## [" (не включая), затем срезаем хвост.
awk -v ver="## [${VERSION}]" '
  $0 ~ /^## \[/ { if (started) exit; if (index($0, ver)==1) started=1 }
  started { print }
' CHANGELOG.md > "$NOTES_FILE"
[ -s "$NOTES_FILE" ] || die "не извлёк release notes для ${VERSION}"
note "release notes → $NOTES_FILE ($(wc -l < "$NOTES_FILE") строк)"

if [ "$DRY_RUN" = "1" ]; then
  echo ""
  echo "=== DRY_RUN: проверки пройдены, push/release пропущены ==="
  echo "--- release notes preview ---"
  cat "$NOTES_FILE"
  exit 0
fi

# ── 4. Тег ─────────────────────────────────────────────────────────────────
if git rev-parse "$TAG" >/dev/null 2>&1; then
  note "локальный тег $TAG уже есть"
else
  git tag -a "$TAG" "$COMMIT" -m "$TAG" || die "git tag упал"
  note "создан тег $TAG @ ${COMMIT:0:10}"
fi

if git ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
  note "тег $TAG уже на origin"
else
  for i in 1 2 3 4; do
    git push origin "$TAG" && { note "запушен тег $TAG"; break; }
    [ "$i" = 4 ] && die "push тега упал 4 раза (в облаке refs/tags/* блокируется прокси — запусти локально/teleport)"
    sleep $((2 ** i))
  done
fi

# ── 5. GitHub Release ──────────────────────────────────────────────────────
command -v gh >/dev/null 2>&1 || die "gh CLI не найден — создай Release вручную из $NOTES_FILE"
if gh release view "$TAG" >/dev/null 2>&1; then
  note "GitHub Release $TAG уже существует"
else
  TITLE="$(head -1 "$NOTES_FILE" | sed -E 's/^## \[[^]]+\] *-? *//')"
  gh release create "$TAG" --title "$TAG — ${TITLE:-release}" --notes-file "$NOTES_FILE" \
    || die "gh release create упал"
  note "создан GitHub Release $TAG"
fi

echo ""
echo "✅ Релиз $TAG готов. Пользователям плагина:"
echo "   claude plugin marketplace update dj-music-plugin"
echo "   claude plugin update dj-music@dj-music-plugin   # требует restart Claude Code"

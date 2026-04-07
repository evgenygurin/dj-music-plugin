#!/bin/bash
# Setup script for Claude Code web environment.
# Runs BEFORE Claude Code launches (from /tmp or any directory).
# Only installs dependencies — does NOT start servers.
# Servers are started via SessionStart hook in .claude/settings.json.
set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── Install Python dependencies ──
uv sync --extra http --extra dev

# ── Install panel dependencies ──
(cd panel && bun install)

# ── Ensure panel .env exists ──
if [ ! -f panel/.env ]; then
  cp panel/.env.example panel/.env
  echo "Created panel/.env from .env.example"
fi

# ── Install / update Claude Code plugin + MCP servers ──
# Marketplace берётся из текущего checkout (тот же dev-ref, что и сессия).
# Идемпотентно: add/install молча no-op, если уже добавлено/установлено.
if command -v claude >/dev/null 2>&1; then
  claude plugin marketplace add "$PROJECT_DIR" 2>&1 | sed 's/^/[plugin] /' || true
  claude plugin marketplace update dj-music-plugin 2>&1 | sed 's/^/[plugin] /' || true
  claude plugin install dj-music@dj-music-plugin 2>&1 | sed 's/^/[plugin] /' || true
  claude plugin update dj-music@dj-music-plugin 2>&1 | sed 's/^/[plugin] /' || true
else
  echo "[plugin] claude CLI не найден — пропускаю установку плагина"
fi

echo "Dependencies installed"

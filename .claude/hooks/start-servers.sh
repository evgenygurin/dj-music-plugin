#!/bin/bash
# SessionStart hook: installs tools, loads credentials, starts servers.
# Runs on every new Claude Code web session.
# Idempotent — safe to run multiple times.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── 1. System packages (cached after first run) ──────
if ! command -v ssh &>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq openssh-client libsndfile1 > /dev/null 2>&1
fi

# ── 2. MCP SSH Manager (for remote server access) ────
if ! command -v mcp-ssh-manager &>/dev/null; then
  npm install -g mcp-ssh-manager > /dev/null 2>&1
fi

# ── 3. SSH key + config for Selectel VM ──────────────
mkdir -p ~/.ssh
chmod 700 ~/.ssh
if [ -f "$PROJECT_DIR/.claude/selectel_key" ]; then
  cp "$PROJECT_DIR/.claude/selectel_key" ~/.ssh/selectel_ed25519
  chmod 600 ~/.ssh/selectel_ed25519
fi
if [ -f "$PROJECT_DIR/.claude/ssh-config.toml" ]; then
  cp "$PROJECT_DIR/.claude/ssh-config.toml" ~/.ssh/ssh-config.toml
fi

# ── 4. Load .env into session (Selectel creds, DB URL, YM token) ──
if [ -f "$PROJECT_DIR/.env" ] && [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    echo "export $line" >> "$CLAUDE_ENV_FILE"
  done < "$PROJECT_DIR/.env"
fi

# ── 5. Selectel API credentials (from .env, NOT hardcoded) ────
# Set SELECTEL_API_TOKEN, SELECTEL_PROJECT_ID, SELECTEL_ACCOUNT_ID in .env

# ── 6. Python deps (all extras for dev/test/audio) ────
uv sync --all-extras --quiet 2>/dev/null || true

# ── 7. Skip server start if already running ───────────
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "Servers already running"
  exit 0
fi

# ── 8. Start MCP backend (port 8000), fully detached ──
nohup uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload \
  > /tmp/backend.log 2>&1 &
disown

# ── 9. Start panel (port 3000), fully detached ────────
cd "$PROJECT_DIR/panel"
nohup bun run dev > /tmp/panel.log 2>&1 &
disown

echo "Servers starting in background (logs: /tmp/backend.log, /tmp/panel.log)"

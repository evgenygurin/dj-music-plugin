#!/bin/bash
# SessionStart hook: starts backend + panel dev servers.
# Runs AFTER Claude Code launches, on every new session.
# Processes are fully detached so the hook exits immediately.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── Skip if servers already running ──
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "Backend already running"
  exit 0
fi

# ── Start MCP backend (port 8000), fully detached ──
nohup uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload \
  > /tmp/backend.log 2>&1 &
disown

# ── Start panel (port 3000), fully detached ──
cd panel
nohup bun run dev > /tmp/panel.log 2>&1 &
disown

echo "Servers starting in background (logs: /tmp/backend.log, /tmp/panel.log)"

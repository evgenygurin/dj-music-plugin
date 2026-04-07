#!/usr/bin/env bash
# Restart DJ Music backend (REST API) and panel (Next.js).
# Always kills any existing processes on ports 8000/3000 and starts fresh.
# Called by SessionStart hook and /panel slash command.
#
# Env:
#   CLAUDE_PLUGIN_ROOT — plugin root (set by Claude Code)
#
# Ports:
#   8000 — FastAPI REST API wrapping MCP tools (serve_http.py)
#   3000 — Next.js panel (panel/)
#
# Logs:
#   /tmp/dj-music-backend.log
#   /tmp/dj-music-panel.log

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKEND_PORT=8000
PANEL_PORT=3000
BACKEND_LOG=/tmp/dj-music-backend.log
PANEL_LOG=/tmp/dj-music-panel.log

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -KILL 2>/dev/null || true
    fi
  fi
}

# Kill anything squatting on our ports (old uvicorn/bun/node from prior sessions)
kill_port "$BACKEND_PORT"
kill_port "$PANEL_PORT"

# Start REST API (FastAPI wrapping MCP)
(
  cd "$ROOT" || exit 1
  set -a; . .env 2>/dev/null || true; set +a
  nohup uv run --extra http uvicorn serve_http:api \
    --host 127.0.0.1 --port "$BACKEND_PORT" \
    >"$BACKEND_LOG" 2>&1 &
  disown
)

# Start Next.js panel (only if deps are installed)
if [ -d "$ROOT/panel/node_modules" ]; then
  (
    cd "$ROOT/panel" || exit 1
    nohup bun dev --port "$PANEL_PORT" \
      >"$PANEL_LOG" 2>&1 &
    disown
  )
fi

exit 0

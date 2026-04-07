#!/usr/bin/env bash
# Start DJ Music backend (REST API) and panel (Next.js) if not already running.
# Called by SessionStart hook. Must exit quickly — processes backgrounded via nohup.
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

port_busy() {
  lsof -iTCP:"$1" -sTCP:LISTEN -n -P >/dev/null 2>&1
}

# REST API (FastAPI wrapping MCP) — only start if port 8000 is free
if ! port_busy "$BACKEND_PORT"; then
  (
    cd "$ROOT" || exit 1
    set -a; . .env 2>/dev/null || true; set +a
    nohup uv run --extra http uvicorn serve_http:api \
      --host 127.0.0.1 --port "$BACKEND_PORT" \
      >"$BACKEND_LOG" 2>&1 &
    disown
  )
fi

# Next.js panel — only start if port 3000 is free and panel/node_modules exists
if ! port_busy "$PANEL_PORT" && [ -d "$ROOT/panel/node_modules" ]; then
  (
    cd "$ROOT/panel" || exit 1
    nohup bun dev --port "$PANEL_PORT" \
      >"$PANEL_LOG" 2>&1 &
    disown
  )
fi

exit 0

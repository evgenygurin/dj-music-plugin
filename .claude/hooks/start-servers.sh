#!/bin/bash
# SessionStart hook: starts backend + panel dev servers.
# Runs AFTER Claude Code launches, on every new session.
set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── Skip if servers already running ──
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "Backend already running"
  exit 0
fi

# ── Start MCP backend (port 8000) ──
uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── Wait for backend to be ready ──
echo "Waiting for backend..."
READY=false
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    READY=true
    echo "Backend ready (PID $BACKEND_PID)"
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "Backend process died"
    exit 1
  fi
  sleep 1
done

if [ "$READY" != "true" ]; then
  echo "Backend failed to start within 30s"
  kill $BACKEND_PID 2>/dev/null
  exit 1
fi

# ── Start panel (port 3000) ──
(cd panel && bun run dev) &
echo "Panel starting (PID $!)"

echo "Backend: http://localhost:8000  Panel: http://localhost:3000"

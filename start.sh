#!/bin/bash
set -e

cleanup() {
  echo "Shutting down..."
  kill $BACKEND_PID $PANEL_PID 2>/dev/null
  wait $BACKEND_PID $PANEL_PID 2>/dev/null
}
trap cleanup EXIT INT TERM

# ── Install dependencies ──
uv sync --extra http --extra dev &
UV_PID=$!
(cd panel && bun install --frozen-lockfile) &
BUN_PID=$!

wait $UV_PID || { echo "uv sync failed"; exit 1; }
wait $BUN_PID || { echo "bun install failed"; exit 1; }

# ── Ensure panel .env exists ──
if [ ! -f panel/.env ]; then
  cp panel/.env.example panel/.env
  echo "Created panel/.env from .env.example — review and update values"
fi

# ── Start MCP backend (port 8000) ──
uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── Wait for backend to be ready ──
echo "Waiting for backend..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "Backend ready"
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "Backend process died"; exit 1
  fi
  sleep 1
done

# ── Start panel (port 3000) ──
(cd panel && bun run dev) &
PANEL_PID=$!

echo ""
echo "Backend:  http://localhost:8000  (Swagger: /docs, MCP: /mcp)"
echo "Panel:    http://localhost:3000"
echo ""

wait

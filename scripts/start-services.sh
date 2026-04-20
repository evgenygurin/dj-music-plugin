#!/usr/bin/env bash
# Force-restart DJ Music backend (REST API) and panel (Next.js).
#
# Cleanup strategy:
#   1. Kill anything binding ports 8000 / 3000 (uvicorn / next-dev / squatters)
#   2. Reap orphaned `fastmcp run fastmcp.json` stdio servers — these are
#      spawned by Claude Code / Cursor MCP plugin and pile up across sessions
#      because stdio MCPs don't bind a port and are missed by step 1.
#      We only kill processes whose parent is dead (PPID=1) to avoid
#      disconnecting the currently-active MCP client.
#
# Verification:
#   After starting the backend we poll /api/health for up to 15s so the
#   SessionStart hook only returns once the service is actually ready.
#
# Logs:
#   /tmp/dj-music-backend.log  (uvicorn + REST API)
#   /tmp/dj-music-panel.log    (next dev)
#   Rotated to *.1.log on each run; only 1 generation kept.
#
# Called by:
#   - hooks/hooks.json SessionStart hook (matcher: startup|resume)
#   - commands/panel.md /panel slash command

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
# Prefer the working dir (DJ_PLUGIN_DEV_PATH) over the plugin cache so edits
# in the repo take effect even when the hook fires from the cache copy.
ROOT="${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}}"

# bun and uv live in user-local bins that nohup'd children of Claude Code
# don't always inherit. Prepend them before we fork the backend/panel.
export PATH="$HOME/.bun/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"

BACKEND_PORT=8000
PANEL_PORT=3000
BACKEND_LOG=/tmp/dj-music-backend.log
PANEL_LOG=/tmp/dj-music-panel.log
HEALTH_TIMEOUT=15  # seconds to wait for /api/health

# ── Helpers ─────────────────────────────────────────────────────────
log() {
  printf '[start-services %s] %s\n' "$(date +%H:%M:%S)" "$*" >&2
}

rotate_log() {
  local file="$1"
  if [ -f "$file" ]; then
    mv -f "$file" "${file%.log}.1.log" 2>/dev/null || true
  fi
}

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    log "killing PIDs on :$port → $(echo "$pids" | tr '\n' ' ')"
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -KILL 2>/dev/null || true
    fi
  fi
}

reap_orphan_fastmcp() {
  # Kill `fastmcp run fastmcp.json` python processes whose parent is launchd
  # (PID 1) — these are stdio MCP servers left behind by dead Claude Code /
  # Cursor sessions. Live ones still parented to a real Claude Code helper
  # are left alone so this script is safe to run while a session is active.
  local victims=()
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    local pid ppid
    pid=$(awk '{print $1}' <<<"$line")
    ppid=$(awk '{print $2}' <<<"$line")
    if [ "$ppid" = "1" ] || ! kill -0 "$ppid" 2>/dev/null; then
      victims+=("$pid")
    fi
  done < <(pgrep -fl 'fastmcp run fastmcp.json' 2>/dev/null \
    | awk '{print $1}' \
    | xargs -I{} ps -p {} -o pid=,ppid= 2>/dev/null \
    || true)

  if [ "${#victims[@]}" -gt 0 ]; then
    log "reaping orphan fastmcp PIDs → ${victims[*]}"
    kill -TERM "${victims[@]}" 2>/dev/null || true
    sleep 1
    for pid in "${victims[@]}"; do
      kill -KILL "$pid" 2>/dev/null || true
    done
  fi
}

wait_for_health() {
  local deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if curl -sf -o /dev/null "http://127.0.0.1:${BACKEND_PORT}/api/health"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

# ── Pre-flight ──────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  log "ERROR: uv not found in PATH; install via https://docs.astral.sh/uv/"
  exit 127
fi

if [ ! -d "$ROOT" ]; then
  log "ERROR: project root not found: $ROOT"
  exit 1
fi

cd "$ROOT"

# ── Cleanup phase ───────────────────────────────────────────────────
kill_port "$BACKEND_PORT"
kill_port "$PANEL_PORT"
reap_orphan_fastmcp

# ── Log rotation ────────────────────────────────────────────────────
rotate_log "$BACKEND_LOG"
rotate_log "$PANEL_LOG"

# ── Start REST API (FastAPI wrapping MCP) ───────────────────────────
(
  set -a
  # shellcheck disable=SC1091
  . .env 2>/dev/null || true
  set +a
  nohup uv run --extra http uvicorn app.rest.app:api \
    --host 127.0.0.1 --port "$BACKEND_PORT" \
    >"$BACKEND_LOG" 2>&1 &
  disown
)

# ── Start Next.js panel (only if deps + bun are available) ──────────
if ! command -v bun >/dev/null 2>&1; then
  log "bun not on PATH — skipping panel; install https://bun.sh and re-run"
elif [ ! -d "$ROOT/panel/node_modules" ]; then
  log "panel/node_modules missing — skipping panel; run 'cd panel && bun install'"
else
  (
    cd "$ROOT/panel"
    nohup bun dev --port "$PANEL_PORT" \
      >"$PANEL_LOG" 2>&1 &
    disown
  )
fi

# ── Wait for backend to actually be ready ───────────────────────────
if wait_for_health; then
  log "backend ready on :${BACKEND_PORT}"
else
  log "WARNING: backend did not respond to /api/health within ${HEALTH_TIMEOUT}s"
  log "  tail $BACKEND_LOG for diagnostics"
  exit 2
fi

exit 0

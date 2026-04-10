#!/usr/bin/env bash
# Wrapper for Claude Preview MCP — sources .env so that DJ_DATABASE_URL,
# DJ_YM_TOKEN, etc. are available to uvicorn / FastMCP lifespan.
#
# Called from .claude/launch.json (preview_start "rest-api")
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8001 --reload

#!/usr/bin/env bash
# Wrapper for Claude Preview MCP — ensures Homebrew node is in PATH so that
# Next.js/Turbopack child workers can spawn `node` (otherwise Turbopack panics
# with "spawning node pooled process: No such file or directory").
#
# Called from .claude/launch.json (preview_start "panel")
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT/panel"
exec node ./node_modules/next/dist/bin/next dev --port 3000

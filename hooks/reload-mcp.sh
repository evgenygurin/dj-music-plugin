#!/usr/bin/env bash
# dj-music plugin PostToolUse hook.
# On edits inside the plugin:
#   1. Purge Python bytecode + tool caches (so respawn loads fresh source).
#   2. Kill fastmcp stdio process — Claude Code respawns on next tool call.
#   3. If plugin metadata changed (hooks.json / plugin.json / .mcp.json),
#      emit a loud systemMessage — those need a full Claude Code restart.

set -euo pipefail

plugin_root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

input="$(cat)"
tool_name="$(echo "$input" | jq -r '.tool_name // empty')"

case "$tool_name" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

path="$(echo "$input" | jq -r '.tool_input.file_path // empty')"
[[ -z "$path" ]] && exit 0

# Only react to edits inside this plugin.
case "$path" in
  "$plugin_root"/*) ;;
  *) exit 0 ;;
esac

# ── Purge caches ───────────────────────────────────────────────
# Python bytecode
find "$plugin_root" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$plugin_root" -type f -name '*.pyc' -delete 2>/dev/null || true
# Tool caches
for d in .mypy_cache .ruff_cache .pytest_cache; do
  rm -rf "$plugin_root/$d" 2>/dev/null || true
done

# ── Decide whether MCP respawn or full restart is needed ───────
needs_restart=0
case "$path" in
  */hooks/hooks.json|*/.claude-plugin/plugin.json|*/.mcp.json)
    needs_restart=1
    ;;
esac

# Kill fastmcp stdio so next tool call respawns with fresh code.
case "$path" in
  *.py|*/fastmcp.json|*/server.py)
    pkill -f "${plugin_root}/.*(app/server\.py|fastmcp\.json)" 2>/dev/null || true
    ;;
esac

if [[ "$needs_restart" -eq 1 ]]; then
  cat <<'JSON'
{"systemMessage": "⚠️  Plugin metadata changed (hooks.json / plugin.json / .mcp.json). Caches purged, but Claude Code must be restarted (exit + run `claude`) for this change to take effect — hooks and plugin manifests load only at session start."}
JSON
else
  cat <<'JSON'
{"systemMessage": "dj-music plugin caches purged; MCP stdio killed — next tool call will respawn with fresh code."}
JSON
fi

#!/usr/bin/env bash
# dj-music plugin — FileChanged hook handler for dev mode.
#
# Canonical Claude Code mechanism: the `FileChanged` hook event fires each
# time a watched file changes on disk, regardless of whether Claude or an
# external editor (VS Code, vim, …) made the change. See:
#   https://code.claude.com/docs/en/plugins-reference#hooks
#
# Responsibility: on change of a plugin-owned file, kill every dj-music
# fastmcp stdio process so Claude Code respawns it with fresh code on the
# next tool call. Complements the PostToolUse hook (which only fires for
# Claude's own Edit/Write/MultiEdit calls) by covering external editor
# saves.
#
# Input (stdin JSON): { "file_path": "/abs/path/to/changed/file", ... }
# Output (stdout JSON): { "systemMessage": "..." } — shown in the session.

set -euo pipefail

input="$(cat)"
path="$(echo "$input" | jq -r '.file_path // empty')"

[[ -z "$path" ]] && exit 0

# Only act on files inside any dj-music-plugin root (working dir, worktree,
# or ~/.claude/plugins/cache). The "dj-music-plugin" substring is the
# unambiguous marker.
case "$path" in
  *dj-music-plugin/*) ;;
  *) exit 0 ;;
esac

# Ignore VCS / build artefacts so the hook doesn't chain on its own output.
case "$path" in
  */.git/*|*/.venv/*|*/__pycache__/*|*/node_modules/*|*/.next/*|*/.pytest_cache/*|*/.mypy_cache/*|*/.ruff_cache/*)
    exit 0
    ;;
esac

# Kill every dj-music fastmcp MCP stdio proc. Claude Code respawns it on
# the next tool call (stdio child processes auto-restart).
killed_pids=""
for pat in 'dj-music-plugin.*fastmcp run' 'dj-music-plugin.*/(server\.py|app/server/app\.py)'; do
  pids="$(pgrep -f "$pat" 2>/dev/null || true)"
  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
    killed_pids="$killed_pids $pid"
  done
done

if [[ -n "$killed_pids" ]]; then
  sleep 0.2
  for pid in $killed_pids; do
    kill -9 "$pid" 2>/dev/null || true
  done
fi

count=$(echo "$killed_pids" | wc -w | tr -d ' ')
if [[ "$count" -gt 0 ]]; then
  name="$(basename "$path")"
  msg="🔄 FileChanged: ${name} — killed ${count} dj-music MCP proc(s); next tool call respawns with fresh code."
  printf '{"systemMessage":%s}\n' "$(jq -Rn --arg m "$msg" '$m')"
fi

#!/usr/bin/env bash
# dj-music plugin PostToolUse hook — reload MCP on edits.
#
# Codex or Claude Code may load the plugin from distinct roots:
#   1. Codex cache        ~/.codex/plugins/cache/<marketplace>/dj-music/<ver>/
#   2. Claude cache       ~/.claude/plugins/cache/dj-music-plugin/dj-music/<ver>/
#   3. working dir        /Users/$USER/dev/dj-music-plugin/ (via DJ_PLUGIN_DEV_PATH)
#   4. any git worktree   .../dj-music-plugin/.claude/worktrees/<n>/
#
# The previous iteration of this hook anchored everything on a single
# ${plugin_root} derived from CLAUDE_PLUGIN_ROOT — which meant an edit in the
# working dir with MCP running from the cache (or vice-versa) would silently
# no-op: the path match failed, or the pkill regex only matched one root.
#
# This version:
#   1. triggers on edits in ANY dj-music-plugin location
#   2. purges bytecode + tool caches in ALL known roots
#   3. kills every fastmcp stdio proc whose cmdline contains "dj-music-plugin"
#      (entry point is `fastmcp run fastmcp.json`, NOT `server.py` directly —
#       the old regex missed this)
#   4. warns when DJ_PLUGIN_DEV_PATH is unset and edits are happening outside
#      the plugin cache (edits won't be reflected after respawn)

set -euo pipefail

default_root="$(cd "$(dirname "$0")/.." && pwd)"
plugin_root="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$default_root}}"
claude_cache_parent="$HOME/.claude/plugins/cache/dj-music-plugin"
codex_cache_parent="$HOME/.codex/plugins/cache"

input="$(cat)"
tool_name="$(echo "$input" | jq -r '.tool_name // empty')"

case "$tool_name" in
  Edit|Write|MultiEdit|apply_patch) ;;
  *) exit 0 ;;
esac

path="$(echo "$input" | jq -r '
  if (.tool_input | type) == "object"
  then (.tool_input.file_path // .tool_input.path // empty)
  else empty
  end
')"
if [[ -z "$path" && "$tool_name" == "apply_patch" ]]; then
  patch_input="$(echo "$input" | jq -r '
    if (.tool_input | type) == "string"
    then .tool_input
    else (.tool_input.patch // empty)
    end
  ')"
  path="$(printf '%s\n' "$patch_input" \
    | sed -nE 's/^\*\*\* (Add|Update|Delete) File: (.*)$/\2/p' \
    | head -n 1)"
fi
[[ -z "$path" ]] && exit 0
if [[ "$path" != /* ]]; then
  path="$PWD/$path"
fi

# Trigger on any edit whose path sits under one of the plugin roots.
# "dj-music-plugin" is the unambiguous marker — matches working dir, worktrees,
# and cache installs without hard-coding locations.
case "$path" in
  *dj-music-plugin/*) ;;
  "$plugin_root"/*) ;;
  *) exit 0 ;;
esac

# Ignore VCS / build artefacts so the hook doesn't chain on its own output.
case "$path" in
  */.git/*|*/node_modules/*|*/.venv/*|*/__pycache__/*|*/.next/*|*/.import_linter_cache/*)
    exit 0
    ;;
esac

# ── Discover every plugin root that exists on disk ──────────────
roots=()
for candidate in "$plugin_root" "$default_root" "${DJ_PLUGIN_DEV_PATH:-}"; do
  [[ -n "$candidate" && -d "$candidate" ]] && roots+=("$candidate")
done
# Every installed version of the plugin in the marketplace cache.
if [[ -d "$claude_cache_parent" ]]; then
  while IFS= read -r versioned; do
    [[ -d "$versioned" ]] && roots+=("$versioned")
  done < <(find "$claude_cache_parent" -mindepth 2 -maxdepth 2 -type d)
fi
if [[ -d "$codex_cache_parent" ]]; then
  while IFS= read -r versioned; do
    [[ -d "$versioned" ]] && roots+=("$versioned")
  done < <(find "$codex_cache_parent" -mindepth 3 -maxdepth 3 -type d -path '*/dj-music/*')
fi

# De-duplicate while preserving order.
declare -a seen=()
uniq_roots=()
for r in "${roots[@]}"; do
  dup=0
  for s in "${seen[@]:-}"; do
    [[ "$r" == "$s" ]] && { dup=1; break; }
  done
  if [[ "$dup" -eq 0 ]]; then
    seen+=("$r")
    uniq_roots+=("$r")
  fi
done

# ── Purge caches at every discovered root ───────────────────────
for root in "${uniq_roots[@]:-}"; do
  find "$root" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  find "$root" -type f -name '*.pyc' -delete 2>/dev/null || true
  for d in .mypy_cache .ruff_cache .pytest_cache; do
    rm -rf "$root/$d" 2>/dev/null || true
  done
done

# ── Decide whether MCP respawn or full restart is needed ────────
needs_restart=0
case "$path" in
  */hooks/hooks.json|*/.claude-plugin/plugin.json|*/.codex-plugin/plugin.json|*/.mcp.json)
    needs_restart=1
    ;;
esac

# ── Kill every dj-music MCP stdio proc (cache + dev, all versions) ──
# Entry point runs as `fastmcp run fastmcp.json` — the old regex
# `${plugin_root}/.*(app/server\.py|fastmcp\.json)` missed this and ignored
# procs whose $plugin_root differed from the live cmdline.
should_kill=0
case "$path" in
  *.py|*/fastmcp.json|*/server.py|*/plugin.json|*/hooks.json) should_kill=1 ;;
esac

killed_pids=""
if [[ "$should_kill" -eq 1 ]]; then
  # Broad sweep: any Python proc whose cmdline mentions this plugin.
  # The two variants cover `fastmcp run ...` and legacy `server.py` launches.
  # macOS has a case-insensitive FS → some cmdlines show ".Claude" (capital C);
  # pgrep is case-sensitive, so match both spellings.
  patterns=(
    'dj-music-plugin.*fastmcp run'
    'dj-music-plugin.*/(server\.py|app/server/app\.py)'
  )
  for pat in "${patterns[@]}"; do
    pids="$(pgrep -f "$pat" 2>/dev/null || true)"
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
      killed_pids="$killed_pids $pid"
    done
  done
  # Grace period before SIGKILL — give the stdio loop a chance to flush.
  if [[ -n "$killed_pids" ]]; then
    sleep 0.2
    for pid in $killed_pids; do
      kill -9 "$pid" 2>/dev/null || true
    done
  fi
fi

# ── Build user-facing message ───────────────────────────────────
kill_note=""
if [[ -n "$killed_pids" ]]; then
  count=$(echo "$killed_pids" | wc -w | tr -d ' ')
  kill_note=" killed $count fastmcp proc(s)."
fi

dev_warning=""
# Edits happen in the working dir but DJ_PLUGIN_DEV_PATH is unset — MCP will
# respawn from the cache and the edits won't be reflected.
if [[ "$path" != "$claude_cache_parent"/* && "$path" != "$codex_cache_parent"/* ]] \
  && [[ -z "${DJ_PLUGIN_DEV_PATH:-}" ]]; then
  dev_warning="  ⚠ DJ_PLUGIN_DEV_PATH not set — respawn may load from plugin cache, not working dir."
fi

if [[ "$needs_restart" -eq 1 ]]; then
  msg="⚠️  Plugin metadata changed (hooks.json / plugin.json / .mcp.json). Caches purged.${kill_note} Restart Codex or Claude Code to reload plugin metadata."
else
  msg="dj-music plugin caches purged;${kill_note} next tool call will respawn with fresh code.${dev_warning}"
fi

printf '{"systemMessage":%s}\n' "$(jq -Rn --arg m "$msg" '$m')"

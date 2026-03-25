# BUG-001: Hidden tools not accessible in Claude Code after unlock_tools

## Problem

`unlock_tools(category="audio")` successfully unlocks tools on the MCP server side,
but Claude Code's deferred tool list is cached at session start and never refreshed.
Result: `analyze_track`, `analyze_batch`, `separate_stems` and atomic tools remain
inaccessible even after unlock.

## Root Cause

Claude Code calls `tools/list` once at session start and caches the result.
FastMCP sends `notifications/tools/list_changed` when tools are enabled/disabled,
but Claude Code does not re-fetch the tool list in response.

## Impact

- Cannot call hidden tools (`audio`, `atomic` categories) directly from Claude Code
- Workaround: use Python script via Bash tool with `Client(mcp)` — bypasses deferred cache
- Affects E2E pipeline: download → **analyze** → classify → build set

## Affected Tools

| Tool | Category | Status |
|------|----------|--------|
| `analyze_track` | audio | Hidden, not accessible |
| `analyze_batch` | audio | Hidden, not accessible |
| `separate_stems` | audio | Hidden, not accessible |
| `analyze_one_track` | atomic | Hidden, not accessible |
| `classify_one_track` | atomic | Hidden, not accessible |
| `gate_one_track` | atomic | Hidden, not accessible |
| `get_similar_one_track` | atomic | Hidden, not accessible |

## Possible Fixes

1. **Make audio tools visible by default** — simplest, but adds ~3 tools to schema
2. **Move analyze_track to "extended" tier** (not hidden) — unlock still needed but visible after
3. **Wait for Claude Code to support `notifications/tools/list_changed`** — upstream fix
4. **Expose analyze via a visible wrapper tool** — e.g. `manage_audio(action="analyze", track_id=42)`

## Recommendation

Option 4: add a visible composite tool `manage_audio` that wraps analyze/classify/gate
under one tool with `action` parameter, similar to `manage_tracks`/`manage_playlist` pattern.

## Date

2026-03-25

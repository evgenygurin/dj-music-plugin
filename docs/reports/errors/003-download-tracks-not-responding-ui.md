# BUG-003: download_tracks shows "Not responding" in Claude Code UI

## Problem

`download_tracks` with 10 tracks takes 30-60 seconds. During this time,
Claude Code UI shows "Not responding · try stopping" because the tool
blocks the main conversation loop.

## Root Cause

Tool has `task=True` (added in this session), but Claude Code MCP plugin
does not support background task execution — it waits synchronously for
the tool result. Long-running tools block the UI.

## Fix Applied

- Added `task=True` to `download_tracks` decorator
- Added `ctx.report_progress(i, total)` for progress updates
- Added `session: AsyncSession = Depends(get_db_session)` for library linking

## Remaining Issue

`task=True` enables background execution for clients that support it
(FastMCP Client), but Claude Code does not poll tasks. The "Not responding"
is a Claude Code UI limitation, not a server bug.

## Workaround

For large batches, split into smaller calls (5 tracks each) to keep
individual tool calls under 15 seconds.

## Date

2026-03-25

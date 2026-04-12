"""MCP tool — long-running deck/mixer state stream (Phase 14).

Canonical FastMCP 3.x pattern for server push: a long-running tool
that emits `ctx.report_progress` + `ctx.info` notifications in a loop
until the client cancels (asyncio.CancelledError) or the iteration
budget is exhausted.

Throttled in-code at 15 Hz default — FastMCP does not rate-limit
notifications, so we keep the JSON-RPC channel sane ourselves.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Context
from fastmcp.tools import tool

from app.controllers.tools._shared.taxonomy import (
    ICON_MONITORING,
    TOOL_META,
    ToolCategory,
)
from app.engines.mixer.engine import MixerEngine

DEFAULT_HZ = 15
MAX_HZ = 30
DEFAULT_DURATION_S = 60.0
MAX_DURATION_S = 600.0


def _get_mixer(ctx: Context) -> MixerEngine:
    mixer: MixerEngine = ctx.lifespan_context["mixer"]
    return mixer


@tool(
    title="Watch Decks",
    tags={ToolCategory.CORE.value, "monitoring"},
    icons=ICON_MONITORING,
    meta=TOOL_META,
    timeout=None,
)
async def watch_decks(
    ctx: Context,
    hz: int = DEFAULT_HZ,
    duration_s: float = DEFAULT_DURATION_S,
) -> dict[str, Any]:
    """Stream mixer + deck state at `hz` updates/sec for `duration_s` seconds.

    Cancellable via client. Returns final snapshot + tick count.
    """
    hz = max(1, min(int(hz), MAX_HZ))
    duration_s = max(1.0, min(float(duration_s), MAX_DURATION_S))
    interval = 1.0 / hz
    total_ticks = int(duration_s * hz)

    mixer = _get_mixer(ctx)
    tick = 0
    try:
        for tick in range(1, total_ticks + 1):
            snap = mixer.snapshot()
            await ctx.report_progress(progress=tick, total=total_ticks)
            await ctx.info(json.dumps(snap, default=str))
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        await ctx.info(f"watch_decks cancelled after {tick} ticks")
        raise
    return {"ticks": tick, "final": mixer.snapshot()}

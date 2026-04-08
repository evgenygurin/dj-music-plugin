"""MCP tools — mixer control surface (Phase 14).

Reads MixerEngine singleton from `ctx.lifespan_context["mixer"]`.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.tools import tool

from app.controllers.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from app.engines.mixer.engine import MixerEngine
from app.schemas.deck import DeckStateRead
from app.schemas.mixer import MixerStateRead


def _get_mixer(ctx: Context) -> MixerEngine:
    mixer: MixerEngine = ctx.lifespan_context["mixer"]
    return mixer


def _to_read(snapshot: dict[str, Any]) -> MixerStateRead:
    return MixerStateRead.model_validate(
        {
            "crossfader": snapshot["crossfader"],
            "channel_gain": snapshot["channel_gain"],
            "decks": {
                int(k): DeckStateRead.model_validate(v) for k, v in snapshot["decks"].items()
            },
        }
    )


@tool(tags={ToolCategory.CORE.value, "mixer"})
async def mixer_crossfader(target: float, ctx: Context) -> MixerStateRead:
    """Set crossfader position. 0=full A side, 1=full B side."""
    mixer = _get_mixer(ctx)
    mixer.set_crossfader(target)
    return _to_read(mixer.snapshot())


@tool(tags={ToolCategory.CORE.value, "mixer"})
async def mixer_channel_gain(deck_id: int, gain: float, ctx: Context) -> MixerStateRead:
    """Set per-channel gain (0..1.5) for a deck on the mixer."""
    mixer = _get_mixer(ctx)
    mixer.set_channel_gain(deck_id, gain)
    return _to_read(mixer.snapshot())


@tool(tags={ToolCategory.CORE.value, "mixer"}, annotations=ANNOTATIONS_READ_ONLY)
async def mixer_state(ctx: Context) -> MixerStateRead:
    """Snapshot of mixer + all 4 decks (no side effects)."""
    return _to_read(_get_mixer(ctx).snapshot())

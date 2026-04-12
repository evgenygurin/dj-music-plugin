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
            "eq": snapshot.get("eq", {}),
            "filter": snapshot.get("filter", {}),
            "decks": {
                int(k): DeckStateRead.model_validate(v) for k, v in snapshot["decks"].items()
            },
        }
    )


@tool(title="Mixer Crossfader", tags={ToolCategory.CORE.value, "mixer"})
async def mixer_crossfader(target: float, ctx: Context) -> MixerStateRead:
    """Set crossfader position. 0=full A side, 1=full B side."""
    mixer = _get_mixer(ctx)
    mixer.set_crossfader(target)
    return _to_read(mixer.snapshot())


@tool(title="Mixer Channel Gain", tags={ToolCategory.CORE.value, "mixer"})
async def mixer_channel_gain(deck_id: int, gain: float, ctx: Context) -> MixerStateRead:
    """Set per-channel gain (0..1.5) for a deck on the mixer."""
    mixer = _get_mixer(ctx)
    mixer.set_channel_gain(deck_id, gain)
    return _to_read(mixer.snapshot())


@tool(title="Mixer State", tags={ToolCategory.CORE.value, "mixer"}, annotations=ANNOTATIONS_READ_ONLY)
async def mixer_state(ctx: Context) -> MixerStateRead:
    """Snapshot of mixer + all 4 decks (no side effects)."""
    return _to_read(_get_mixer(ctx).snapshot())


@tool(title="Set EQ", tags={ToolCategory.CORE.value, "mixer"})
async def set_eq(
    deck_id: int,
    band: str,
    gain: float,
    ctx: Context,
) -> MixerStateRead:
    """Set EQ gain for a deck band.

    Args:
        deck_id: Deck number (1-4).
        band: EQ band — 'low' (shelf 320 Hz), 'mid' (peak 1 kHz), or 'high' (shelf 3.2 kHz).
        gain: Gain in dB. Range -40 (kill) to +6 (boost). 0 = flat.
    """
    mixer = _get_mixer(ctx)
    mixer.set_eq(deck_id, band, gain)
    return _to_read(mixer.snapshot())


@tool(title="Kill EQ", tags={ToolCategory.CORE.value, "mixer"})
async def kill_eq(
    deck_id: int,
    band: str,
    ctx: Context,
) -> MixerStateRead:
    """Kill an EQ band instantly (-40 dB). Useful for bass drops.

    Args:
        deck_id: Deck number (1-4).
        band: 'low', 'mid', or 'high'.
    """
    mixer = _get_mixer(ctx)
    mixer.kill_eq(deck_id, band)
    return _to_read(mixer.snapshot())


@tool(title="Reset EQ", tags={ToolCategory.CORE.value, "mixer"})
async def reset_eq(
    deck_id: int,
    ctx: Context,
) -> MixerStateRead:
    """Reset all EQ bands to flat (0 dB) for a deck.

    Args:
        deck_id: Deck number (1-4).
    """
    mixer = _get_mixer(ctx)
    mixer.reset_eq(deck_id)
    return _to_read(mixer.snapshot())


@tool(title="Set Filter", tags={ToolCategory.CORE.value, "mixer"})
async def set_filter(
    deck_id: int,
    cutoff_hz: float,
    ctx: Context,
) -> MixerStateRead:
    """Set lowpass filter cutoff for a deck.

    Args:
        deck_id: Deck number (1-4).
        cutoff_hz: Cutoff frequency in Hz. 20 = full cut, 20000 = open (no filter).
    """
    mixer = _get_mixer(ctx)
    mixer.set_filter(deck_id, cutoff_hz)
    return _to_read(mixer.snapshot())

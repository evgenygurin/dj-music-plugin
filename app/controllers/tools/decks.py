"""MCP tools — single-deck control surface (Phase 14).

Each tool reads the singleton DeckEngine from
`ctx.lifespan_context["decks"]`. Engines persist across calls; tool
calls are stateless dispatches into the runtime.

Phase 14 is stub — engines accept commands and update state but the
audio output is not yet wired (Phase 15). Tool surface is final.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.tools import tool

from app.controllers.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from app.core.errors import NotFoundError
from app.engines.deck.engine import DeckEngine
from app.schemas.deck import DeckStateRead


def _get_deck(ctx: Context, deck_id: int) -> DeckEngine:
    decks: dict[int, DeckEngine] = ctx.lifespan_context["decks"]
    deck = decks.get(deck_id)
    if deck is None:
        raise NotFoundError("Deck", deck_id)
    return deck


def _to_read(snapshot: dict[str, Any]) -> DeckStateRead:
    return DeckStateRead.model_validate(snapshot)


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_load(deck_id: int, track_id: int, duration_ms: int, ctx: Context) -> DeckStateRead:
    """Load a track into a deck. Phase 14: state-only, no decode yet."""
    deck = _get_deck(ctx, deck_id)
    deck.load(track_id=track_id, duration_ms=duration_ms)
    await ctx.info(f"deck {deck_id} loaded track {track_id}")
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_play(deck_id: int, ctx: Context) -> DeckStateRead:
    """Start playback on a deck."""
    deck = _get_deck(ctx, deck_id)
    deck.play()
    await ctx.info(f"deck {deck_id} playing")
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_pause(deck_id: int, ctx: Context) -> DeckStateRead:
    """Pause playback on a deck."""
    deck = _get_deck(ctx, deck_id)
    deck.pause()
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_cue(deck_id: int, ctx: Context) -> DeckStateRead:
    """Jump to cue point and pause."""
    deck = _get_deck(ctx, deck_id)
    deck.cue()
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_unload(deck_id: int, ctx: Context) -> DeckStateRead:
    """Release the loaded track."""
    deck = _get_deck(ctx, deck_id)
    deck.unload()
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_set_pitch(deck_id: int, pitch: float, ctx: Context) -> DeckStateRead:
    """Set deck pitch (0.92..1.08 = ±8%, DJ standard)."""
    deck = _get_deck(ctx, deck_id)
    deck.set_pitch(pitch)
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"})
async def deck_set_gain(deck_id: int, gain: float, ctx: Context) -> DeckStateRead:
    """Set deck gain (0..1.5)."""
    deck = _get_deck(ctx, deck_id)
    deck.set_gain(gain)
    return _to_read(deck.snapshot())


@tool(tags={ToolCategory.CORE.value, "decks"}, annotations=ANNOTATIONS_READ_ONLY)
async def deck_state(deck_id: int, ctx: Context) -> DeckStateRead:
    """Read current state of a single deck (no side effects)."""
    deck = _get_deck(ctx, deck_id)
    return _to_read(deck.snapshot())

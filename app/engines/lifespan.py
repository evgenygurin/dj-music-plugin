"""Audio engines lifespan — composes singleton DeckEngines + Mixer (Phase 14).

Wires the runtime engines into FastMCP via the canonical 3.x lifespan
pattern. Will be composed with db / ym / library_index lifespans in
`app/core/lifespan.py:app_lifespan`.

Phase 14: stub engines, no real audio output. Phase 15 will swap in
the sounddevice driver.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastmcp.server.lifespan import lifespan

from app.engines.deck.engine import DeckEngine
from app.engines.mixer.engine import MixerEngine

NUM_DECKS = 4


@lifespan
async def audio_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Construct decks + mixer, start them, yield via lifespan_context."""
    decks = {i: DeckEngine(deck_id=i) for i in range(1, NUM_DECKS + 1)}
    mixer = MixerEngine(decks=decks)

    for d in decks.values():
        await d.start()
    await mixer.start()

    try:
        yield {
            "decks": decks,
            "mixer": mixer,
        }
    finally:
        await mixer.stop()
        for d in decks.values():
            await d.stop()

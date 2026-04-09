"""MixerEngine — singleton mixing 4 decks into a master output (Phase 14 stub).

Phase 15 will actually mix the deck outputs in the sounddevice
callback. This stub holds state (crossfader, channel gains) and
exposes a snapshot for `watch_decks`.
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine
from app.engines.deck.engine import DeckEngine


class MixerEngine(BaseEngine):
    """Mixer state: crossfader, per-channel volume, kill switches."""

    def __init__(self, decks: dict[int, DeckEngine]) -> None:
        self.decks = decks
        self._crossfader: float = 0.5  # 0 = full A, 1 = full B
        self._channel_gain: dict[int, float] = dict.fromkeys(decks, 1.0)

    async def start(self) -> None:
        """No-op for stub. Phase 15 starts the audio output stream."""

    async def stop(self) -> None:
        """No-op for stub. Phase 15 stops the audio output stream."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "crossfader": self._crossfader,
            "channel_gain": dict(self._channel_gain),
            "decks": {i: d.snapshot() for i, d in self.decks.items()},
        }

    def set_crossfader(self, value: float) -> None:
        self._crossfader = max(0.0, min(value, 1.0))

    def set_channel_gain(self, deck_id: int, value: float) -> None:
        if deck_id not in self.decks:
            from app.core.errors import NotFoundError

            raise NotFoundError("Deck", deck_id)
        self._channel_gain[deck_id] = max(0.0, min(value, 1.5))


__all__ = ["MixerEngine"]

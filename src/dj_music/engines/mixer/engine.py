"""MixerEngine — singleton mixing 4 decks into a master output (Phase 14 stub).

Phase 15 will actually mix the deck outputs in the sounddevice
callback. This stub holds state (crossfader, channel gains) and
exposes a snapshot for `watch_decks`.
"""

from __future__ import annotations

from typing import Any

from dj_music.engines.base import BaseEngine
from dj_music.engines.deck.engine import DeckEngine


class MixerEngine(BaseEngine):
    """Mixer state: crossfader, per-channel volume, 3-band EQ, filter."""

    EQ_BANDS: frozenset[str] = frozenset({"low", "mid", "high"})
    EQ_MIN: float = -40.0  # dB (kill)
    EQ_MAX: float = 6.0  # dB (boost)

    def __init__(self, decks: dict[int, DeckEngine]) -> None:
        self.decks = decks
        self._crossfader: float = 0.5  # 0 = full A, 1 = full B
        self._channel_gain: dict[int, float] = dict.fromkeys(decks, 1.0)
        # Per-deck 3-band EQ (dB gain): low(shelf 320Hz), mid(peak 1kHz), high(shelf 3.2kHz)
        self._eq: dict[int, dict[str, float]] = {
            i: {"low": 0.0, "mid": 0.0, "high": 0.0} for i in decks
        }
        # Per-deck filter cutoff (Hz): 20=full cut, 20000=open
        self._filter: dict[int, float] = dict.fromkeys(decks, 20000.0)

    async def start(self) -> None:
        """No-op for stub. Phase 15 starts the audio output stream."""

    async def stop(self) -> None:
        """No-op for stub. Phase 15 stops the audio output stream."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "crossfader": self._crossfader,
            "channel_gain": dict(self._channel_gain),
            "eq": {k: dict(v) for k, v in self._eq.items()},
            "filter": dict(self._filter),
            "decks": {i: d.snapshot() for i, d in self.decks.items()},
        }

    def set_eq(self, deck_id: int, band: str, gain: float) -> None:
        """Set EQ gain for a band. band ∈ {low, mid, high}, gain ∈ [-40, 6] dB."""
        from dj_music.core.errors import NotFoundError, ValidationError

        if deck_id not in self.decks:
            raise NotFoundError("Deck", deck_id)
        if band not in self.EQ_BANDS:
            raise ValidationError(
                f"Invalid EQ band '{band}'. Must be one of: {', '.join(sorted(self.EQ_BANDS))}"
            )
        clamped = max(self.EQ_MIN, min(gain, self.EQ_MAX))
        self._eq[deck_id][band] = clamped

    def kill_eq(self, deck_id: int, band: str) -> None:
        """Instant kill: set band to -40 dB."""
        self.set_eq(deck_id, band, self.EQ_MIN)

    def reset_eq(self, deck_id: int) -> None:
        """Reset all EQ bands to 0 dB (flat)."""
        from dj_music.core.errors import NotFoundError

        if deck_id not in self.decks:
            raise NotFoundError("Deck", deck_id)
        self._eq[deck_id] = {"low": 0.0, "mid": 0.0, "high": 0.0}

    def set_filter(self, deck_id: int, cutoff_hz: float) -> None:
        """Set filter cutoff frequency. 20 Hz = full cut, 20000 Hz = open."""
        from dj_music.core.errors import NotFoundError

        if deck_id not in self.decks:
            raise NotFoundError("Deck", deck_id)
        self._filter[deck_id] = max(20.0, min(cutoff_hz, 20000.0))

    def set_crossfader(self, value: float) -> None:
        self._crossfader = max(0.0, min(value, 1.0))

    def set_channel_gain(self, deck_id: int, value: float) -> None:
        if deck_id not in self.decks:
            from dj_music.core.errors import NotFoundError

            raise NotFoundError("Deck", deck_id)
        self._channel_gain[deck_id] = max(0.0, min(value, 1.5))


__all__ = ["MixerEngine"]

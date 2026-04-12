"""DeckEngine — singleton runtime state per deck (Phase 14 stub).

This is the public façade tools talk to via `state.decks[deck_id]`.
Implementation is a stub: state transitions and snapshot work,
audio rendering / pitch / EQ / FX are TODO for Phase 15.
"""

from __future__ import annotations

from typing import Any

from dj_music.engines.base import BaseEngine
from dj_music.engines.deck.state import DeckState, assert_transition


class DeckEngine(BaseEngine):
    """Single deck — facade over playback / pitch / EQ / FX / cue / loop."""

    def __init__(self, deck_id: int) -> None:
        self.id = deck_id
        self._state = DeckState.EMPTY
        self._track_id: int | None = None
        self._position_ms: int = 0
        self._duration_ms: int = 0
        self._pitch: float = 1.0
        self._gain: float = 1.0

    # ── BaseEngine ─────────────────────────────
    async def start(self) -> None:
        """No-op for stub. Phase 15 will open audio resources."""

    async def stop(self) -> None:
        """No-op for stub. Phase 15 will release audio resources."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "deck_id": self.id,
            "state": self._state.value,
            "track_id": self._track_id,
            "position_ms": self._position_ms,
            "duration_ms": self._duration_ms,
            "pitch": self._pitch,
            "gain": self._gain,
        }

    # ── State transitions (stub) ───────────────
    def load(self, track_id: int, duration_ms: int) -> None:
        assert_transition(self._state, DeckState.LOADING)
        self._state = DeckState.LOADING
        self._track_id = track_id
        self._duration_ms = duration_ms
        self._position_ms = 0
        # Phase 15: actual decode → numpy buffer in background thread
        self._state = DeckState.LOADED

    def play(self) -> None:
        assert_transition(self._state, DeckState.PLAYING)
        self._state = DeckState.PLAYING

    def pause(self) -> None:
        assert_transition(self._state, DeckState.PAUSED)
        self._state = DeckState.PAUSED

    def cue(self) -> None:
        assert_transition(self._state, DeckState.CUEING)
        self._state = DeckState.CUEING
        self._position_ms = 0  # Phase 15: jump to last cue point

    def unload(self) -> None:
        assert_transition(self._state, DeckState.UNLOADING)
        self._state = DeckState.UNLOADING
        self._track_id = None
        self._position_ms = 0
        self._duration_ms = 0
        self._state = DeckState.EMPTY

    def set_pitch(self, value: float) -> None:
        if not 0.92 <= value <= 1.08:  # ±8% DJ standard
            from dj_music.core.errors import ValidationError

            raise ValidationError(f"Pitch out of range: {value} (must be 0.92..1.08)")
        self._pitch = value

    def set_gain(self, value: float) -> None:
        self._gain = max(0.0, min(value, 1.5))


__all__ = ["DeckEngine"]

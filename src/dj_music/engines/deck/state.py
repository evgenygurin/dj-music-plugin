"""DeckState enum + valid state machine transitions.

The deck is a finite state machine. Transitions are explicit and
illegal moves raise a domain error rather than silently no-op.
"""

from __future__ import annotations

from enum import StrEnum

from dj_music.core.errors import ValidationError


class DeckState(StrEnum):
    """Possible states for a single deck."""

    EMPTY = "empty"  # no track loaded
    LOADING = "loading"  # decoding file → numpy buffer
    LOADED = "loaded"  # buffer ready, playhead at 0
    CUEING = "cueing"  # paused at cue point
    PLAYING = "playing"  # audio rendering active
    LOOPING = "looping"  # playing inside an active loop region
    PAUSED = "paused"  # rendering halted, position retained
    UNLOADING = "unloading"  # releasing buffer


# Allowed transitions (from → set of valid to-states)
_TRANSITIONS: dict[DeckState, frozenset[DeckState]] = {
    DeckState.EMPTY: frozenset({DeckState.LOADING}),
    DeckState.LOADING: frozenset({DeckState.LOADED, DeckState.EMPTY}),
    DeckState.LOADED: frozenset({DeckState.CUEING, DeckState.PLAYING, DeckState.UNLOADING}),
    DeckState.CUEING: frozenset({DeckState.PLAYING, DeckState.UNLOADING}),
    DeckState.PLAYING: frozenset({DeckState.PAUSED, DeckState.LOOPING, DeckState.UNLOADING}),
    DeckState.LOOPING: frozenset({DeckState.PLAYING, DeckState.UNLOADING}),
    DeckState.PAUSED: frozenset({DeckState.PLAYING, DeckState.CUEING, DeckState.UNLOADING}),
    DeckState.UNLOADING: frozenset({DeckState.EMPTY}),
}


def can_transition(current: DeckState, target: DeckState) -> bool:
    """Return True if `current → target` is a valid state move."""
    return target in _TRANSITIONS.get(current, frozenset())


def assert_transition(current: DeckState, target: DeckState) -> None:
    """Raise ValidationError if `current → target` is not allowed."""
    if not can_transition(current, target):
        raise ValidationError(f"Illegal deck transition: {current.value} → {target.value}")


__all__ = ["DeckState", "assert_transition", "can_transition"]

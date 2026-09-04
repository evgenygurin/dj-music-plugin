"""Hard set-level constraints independent of audio analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SetConstraints:
    excluded_tracks: frozenset[str] = frozenset()
    max_tracks: int = 256

    def accepts(self, track_id: str, history: tuple[str, ...]) -> bool:
        return (
            track_id not in self.excluded_tracks
            and track_id not in history
            and len(history) < self.max_tracks
        )

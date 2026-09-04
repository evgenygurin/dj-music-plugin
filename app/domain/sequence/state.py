"""Immutable set-level state used by sequence optimization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SetState:
    tracks: tuple[str, ...]
    energy: float = 0.5
    bpm: float = 128.0

    @property
    def current_track(self) -> str:
        if not self.tracks:
            raise ValueError("set state requires at least one track")
        return self.tracks[-1]

    def append(self, track_id: str) -> SetState:
        if track_id in self.tracks:
            raise ValueError("repeated tracks are not allowed")
        return SetState((*self.tracks, track_id), self.energy, self.bpm)

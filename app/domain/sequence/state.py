"""Immutable set-level state used by sequence optimization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SetState:
    tracks: tuple[str, ...]
    energy: float = 0.5
    bpm: float = 128.0
    keys: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()
    recipes: tuple[str, ...] = ()
    artists: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tracks:
            raise ValueError("set state requires at least one track")
        if not 0.0 <= self.energy <= 1.0:
            raise ValueError("energy must be between 0 and 1")
        if self.bpm <= 0:
            raise ValueError("bpm must be positive")

    @property
    def current_track(self) -> str:
        return self.tracks[-1]

    def append(
        self,
        track_id: str,
        *,
        energy: float | None = None,
        bpm: float | None = None,
        key: str | None = None,
        section: str | None = None,
        recipe: str | None = None,
        artist: str | None = None,
        genre: str | None = None,
    ) -> SetState:
        if track_id in self.tracks:
            raise ValueError("repeated tracks are not allowed")
        return SetState(
            (*self.tracks, track_id),
            self.energy if energy is None else energy,
            self.bpm if bpm is None else bpm,
            self.keys if key is None else (*self.keys, key),
            self.sections if section is None else (*self.sections, section),
            self.recipes if recipe is None else (*self.recipes, recipe),
            self.artists if artist is None else (*self.artists, artist),
            self.genres if genre is None else (*self.genres, genre),
        )

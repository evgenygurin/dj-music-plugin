"""Hard set-level constraints independent of audio analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SetConstraints:
    excluded_tracks: frozenset[str] = frozenset()
    mandatory_tracks: frozenset[str] = frozenset()
    fixed_tracks: tuple[str, ...] = ()
    max_tracks: int = 256
    min_bpm: float | None = None
    max_bpm: float | None = None
    min_energy: float | None = None
    max_energy: float | None = None
    max_consecutive_same_artist: int | None = None
    max_consecutive_same_recipe: int | None = None

    def accepts(
        self,
        track_id: str,
        history: tuple[str, ...],
        *,
        bpm: float | None = None,
        energy: float | None = None,
        artist: str | None = None,
        artists: tuple[str, ...] = (),
        recipe: str | None = None,
        recipes: tuple[str, ...] = (),
    ) -> bool:
        if track_id in self.excluded_tracks or track_id in history:
            return False
        if len(history) >= self.max_tracks:
            return False
        if self.min_bpm is not None and (bpm is None or bpm < self.min_bpm):
            return False
        if self.max_bpm is not None and (bpm is None or bpm > self.max_bpm):
            return False
        if self.min_energy is not None and (energy is None or energy < self.min_energy):
            return False
        if self.max_energy is not None and (energy is None or energy > self.max_energy):
            return False
        if self._exceeds(artist, artists, self.max_consecutive_same_artist):
            return False
        return not self._exceeds(recipe, recipes, self.max_consecutive_same_recipe)

    @staticmethod
    def _exceeds(value: str | None, history: tuple[str, ...], limit: int | None) -> bool:
        if value is None or limit is None or limit <= 0:
            return False
        consecutive = 0
        for previous in reversed(history):
            if previous != value:
                break
            consecutive += 1
        return consecutive >= limit

    def mandatory_satisfied(self, tracks: tuple[str, ...]) -> bool:
        return self.mandatory_tracks.issubset(tracks)

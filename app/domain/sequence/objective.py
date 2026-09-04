"""Composable set-level objective helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SequenceObjective:
    continuity_weight: float = 1.0
    novelty_weight: float = 0.25
    repetition_penalty: float = 1.0
    energy_arc_weight: float = 0.25

    def edge_value(
        self,
        transition_score: float,
        *,
        repeated: bool = False,
        artist_repeated: bool = False,
        recipe_repeated: bool = False,
        energy_delta: float = 0.0,
    ) -> float:
        repetition = repeated + artist_repeated * 0.25 + recipe_repeated * 0.15
        return (
            transition_score * self.continuity_weight
            + self.novelty_weight
            - self.repetition_penalty * repetition
            - self.energy_arc_weight * abs(energy_delta)
        )

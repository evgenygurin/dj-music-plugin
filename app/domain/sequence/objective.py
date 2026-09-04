"""Composable set-level objective helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SequenceObjective:
    repetition_penalty: float = 1.0

    def edge_value(self, transition_score: float, *, repeated: bool) -> float:
        return transition_score - self.repetition_penalty if repeated else transition_score

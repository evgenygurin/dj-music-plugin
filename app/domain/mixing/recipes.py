"""Declarative transition recipes; execution belongs to the renderer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecipeKind(StrEnum):
    FADE = "fade"
    EQ_BLEND = "eq_blend"
    FILTER_BLEND = "filter_blend"
    DRUM_SWAP = "drum_swap"
    BASS_SWAP = "bass_swap"
    STEM_BLEND = "stem_blend"
    VOCAL_CUT = "vocal_cut"
    VOCAL_SUSTAIN = "vocal_sustain"
    ECHO_OUT = "echo_out"
    LOOP_ROLL = "loop_roll"
    HARD_CUT = "hard_cut"
    DROP_SWAP = "drop_swap"
    BREAKDOWN_TO_DROP = "breakdown_to_drop"
    DROP_TO_DROP = "drop_to_drop"
    DRUM_CUT = "drum_cut"


@dataclass(frozen=True, slots=True)
class TransitionRecipe:
    kind: RecipeKind
    bars: int
    parameters: tuple[tuple[str, float], ...] = ()


class RecipePlanner:
    def plan(self, kind: RecipeKind, bars: int) -> TransitionRecipe:
        return TransitionRecipe(kind, bars)

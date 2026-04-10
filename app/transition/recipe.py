from __future__ import annotations

import dataclasses
import json
from enum import StrEnum
from typing import Literal


class TransitionType(StrEnum):
    CUT = "cut"
    BASS_SWAP_SHORT = "bass_swap_short"
    BASS_SWAP_LONG = "bass_swap_long"
    EQ_BLEND = "eq_blend"
    FILTER_SWEEP = "filter_sweep"
    ECHO_OUT = "echo_out"
    LONG_BLEND = "long_blend"
    RISER = "riser"
    DROP_SWAP = "drop_swap"
    NEURAL_MIX_BLEND = "neural_mix_blend"
    DISSOLVE = "dissolve"
    STEMS_CREATIVE = "stems_creative"


class DjayTransition(StrEnum):
    NONE = "none"
    FILTER = "filter"
    ECHO = "echo"
    TREMOLO = "tremolo"
    RISER = "riser"
    NEURAL_MIX = "neural_mix"


class StemAction(StrEnum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"


@dataclasses.dataclass(frozen=True)
class RecipeStep:
    bar: int
    deck: Literal["A", "B", "both"]
    action: str
    stem: str | None = None
    stem_action: StemAction | None = None
    eq_band: str | None = None
    eq_value: float | None = None
    effect: str | None = None
    effect_param: float | None = None

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"bar": self.bar, "deck": self.deck, "action": self.action}
        if self.stem is not None:
            d["stem"] = self.stem
        if self.stem_action is not None:
            d["stem_action"] = str(self.stem_action)
        if self.eq_band is not None:
            d["eq_band"] = self.eq_band
        if self.eq_value is not None:
            d["eq_value"] = self.eq_value
        if self.effect is not None:
            d["effect"] = self.effect
        if self.effect_param is not None:
            d["effect_param"] = self.effect_param
        return d


@dataclasses.dataclass(frozen=True)
class EQPlan:
    low: str
    mid: str
    high: str

    def to_dict(self) -> dict[str, object]:
        return {"low": self.low, "mid": self.mid, "high": self.high}


@dataclasses.dataclass(frozen=True)
class TransitionRecipe:
    transition_type: TransitionType
    bars: int
    djay_transition: DjayTransition
    djay_tempo_adjust: str
    steps: tuple[RecipeStep, ...]
    eq_plan: EQPlan
    mix_in_section: str | None
    mix_out_section: str | None
    phrase_align: bool
    warnings: tuple[str, ...]
    confidence: float
    subgenre_modifier: str | None
    rescue_move: str

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "transition_type": str(self.transition_type),
            "bars": self.bars,
            "djay_transition": str(self.djay_transition),
            "djay_tempo_adjust": self.djay_tempo_adjust,
            "steps": [s.to_dict() for s in self.steps],
            "eq_plan": self.eq_plan.to_dict(),
            "phrase_align": self.phrase_align,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "rescue_move": self.rescue_move,
        }
        if self.mix_in_section is not None:
            d["mix_in_section"] = self.mix_in_section
        if self.mix_out_section is not None:
            d["mix_out_section"] = self.mix_out_section
        if self.subgenre_modifier is not None:
            d["subgenre_modifier"] = self.subgenre_modifier
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

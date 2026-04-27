from __future__ import annotations

import dataclasses
import json
from enum import StrEnum
from typing import Any, Literal, cast


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


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else None


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

    @classmethod
    def from_dict(cls, data: object) -> RecipeStep | None:
        if not isinstance(data, dict):
            return None

        bar = _coerce_int(data.get("bar"))
        deck = data.get("deck")
        action = data.get("action")
        if bar is None or not isinstance(deck, str) or deck not in {"A", "B", "both"}:
            return None
        if not isinstance(action, str):
            return None

        stem = _coerce_optional_str(data.get("stem"))
        eq_band = _coerce_optional_str(data.get("eq_band"))
        effect = _coerce_optional_str(data.get("effect"))

        stem_action: StemAction | None = None
        stem_action_raw = data.get("stem_action")
        if stem_action_raw is not None:
            if not isinstance(stem_action_raw, str):
                return None
            try:
                stem_action = StemAction(stem_action_raw)
            except ValueError:
                return None

        eq_value: float | None = None
        if data.get("eq_value") is not None:
            eq_value = _coerce_float(data.get("eq_value"))
            if eq_value is None:
                return None

        effect_param: float | None = None
        if data.get("effect_param") is not None:
            effect_param = _coerce_float(data.get("effect_param"))
            if effect_param is None:
                return None

        return cls(
            bar=bar,
            deck=cast(Literal["A", "B", "both"], deck),
            action=action,
            stem=stem,
            stem_action=stem_action,
            eq_band=eq_band,
            eq_value=eq_value,
            effect=effect,
            effect_param=effect_param,
        )


@dataclasses.dataclass(frozen=True)
class EQPlan:
    low: str
    mid: str
    high: str

    def to_dict(self) -> dict[str, object]:
        return {"low": self.low, "mid": self.mid, "high": self.high}

    @classmethod
    def from_dict(cls, data: object) -> EQPlan | None:
        if not isinstance(data, dict):
            return None
        low = data.get("low", "keep")
        mid = data.get("mid", "keep")
        high = data.get("high", "keep")
        if not isinstance(low, str) or not isinstance(mid, str) or not isinstance(high, str):
            return None
        return cls(low=low, mid=mid, high=high)


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

    @classmethod
    def from_dict(cls, data: object) -> TransitionRecipe | None:
        if not isinstance(data, dict):
            return None

        transition_type_raw = data.get("transition_type")
        if not isinstance(transition_type_raw, str):
            return None
        try:
            transition_type = TransitionType(transition_type_raw)
        except ValueError:
            return None

        bars = _coerce_int(data.get("bars", 0))
        if bars is None:
            return None

        djay_transition_raw = data.get("djay_transition", "none")
        if not isinstance(djay_transition_raw, str):
            return None
        try:
            djay_transition = DjayTransition(djay_transition_raw)
        except ValueError:
            return None

        djay_tempo_adjust = data.get("djay_tempo_adjust", "sync")
        if not isinstance(djay_tempo_adjust, str):
            return None

        steps_raw = data.get("steps", [])
        if not isinstance(steps_raw, list):
            return None
        steps: list[RecipeStep] = []
        for step_raw in steps_raw:
            step = RecipeStep.from_dict(step_raw)
            if step is None:
                return None
            steps.append(step)

        eq_plan = EQPlan.from_dict(data.get("eq_plan", {}))
        if eq_plan is None:
            return None

        phrase_align = data.get("phrase_align", True)
        if not isinstance(phrase_align, bool):
            return None

        warnings_raw = data.get("warnings", [])
        if not isinstance(warnings_raw, list):
            return None

        confidence = _coerce_float(data.get("confidence", 0.5))
        if confidence is None:
            return None

        mix_in_section = _coerce_optional_str(data.get("mix_in_section"))
        if data.get("mix_in_section") is not None and mix_in_section is None:
            return None
        mix_out_section = _coerce_optional_str(data.get("mix_out_section"))
        if data.get("mix_out_section") is not None and mix_out_section is None:
            return None
        subgenre_modifier = _coerce_optional_str(data.get("subgenre_modifier"))
        if data.get("subgenre_modifier") is not None and subgenre_modifier is None:
            return None

        rescue_move = data.get("rescue_move", "filter sweep + hard cut")
        if not isinstance(rescue_move, str):
            return None

        return cls(
            transition_type=transition_type,
            bars=bars,
            djay_transition=djay_transition,
            djay_tempo_adjust=djay_tempo_adjust,
            steps=tuple(steps),
            eq_plan=eq_plan,
            mix_in_section=mix_in_section,
            mix_out_section=mix_out_section,
            phrase_align=phrase_align,
            warnings=tuple(str(w) for w in warnings_raw),
            confidence=confidence,
            subgenre_modifier=subgenre_modifier,
            rescue_move=rescue_move,
        )

    @classmethod
    def from_json(cls, raw: str | None) -> TransitionRecipe | None:
        if not isinstance(raw, str):
            return None
        try:
            data: Any = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return cls.from_dict(data)

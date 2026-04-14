"""Transition recipe dataclasses — result types produced by TransitionSelector.

EQPlan, RecipeStep, and TransitionRecipe are frozen dataclasses. They are
serialised to JSON and stored in transitions.transition_recipe_json.
StemAction lives in types.py to break the forward-reference cycle.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Literal

from app.core.constants import NeuralMixCrossfaderFX
from app.transition.types import StemAction


@dataclasses.dataclass(frozen=True)
class EQPlan:
    """High-level EQ automation strategy for a transition."""

    low: str = "stem"
    mid: str = "stem"
    high: str = "stem"

    def to_dict(self) -> dict[str, str]:
        return {"low": self.low, "mid": self.mid, "high": self.high}

    @classmethod
    def from_dict(cls, data: object) -> EQPlan:
        if not isinstance(data, dict):
            return cls()
        return cls(
            low=data.get("low", "stem") if isinstance(data.get("low"), str) else "stem",
            mid=data.get("mid", "stem") if isinstance(data.get("mid"), str) else "stem",
            high=data.get("high", "stem") if isinstance(data.get("high"), str) else "stem",
        )


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else None


@dataclasses.dataclass(frozen=True)
class RecipeStep:
    """One bar-timed automation event in a transition playbook."""

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
        eq_value = (
            _coerce_float(data.get("eq_value")) if data.get("eq_value") is not None else None
        )
        effect_param = (
            _coerce_float(data.get("effect_param"))
            if data.get("effect_param") is not None
            else None
        )
        return cls(
            bar=bar,
            deck=deck,  # type: ignore[arg-type]
            action=action,
            stem=stem,
            stem_action=stem_action,
            eq_band=eq_band,
            eq_value=eq_value,
            effect=effect,
            effect_param=effect_param,
        )


@dataclasses.dataclass(frozen=True)
class TransitionRecipe:
    """Complete transition playbook returned by TransitionSelector.

    ``fx_type`` is the djay Pro AI Neural Mix Crossfader FX preset.
    ``steps`` is the bar-by-bar stem/EQ automation sequence.
    Serialised to JSON and stored in transitions.transition_recipe_json.
    """

    fx_type: NeuralMixCrossfaderFX | None = None
    bars: int = 16
    steps: tuple[RecipeStep, ...] = ()
    eq_plan: EQPlan = dataclasses.field(default_factory=EQPlan)
    djay_tempo_adjust: str = "none"
    mix_in_section: str | None = None
    mix_out_section: str | None = None
    phrase_align: bool = True
    warnings: tuple[str, ...] = ()
    confidence: float = 0.75
    subgenre_modifier: str | None = None
    rescue_move: str = "adjust blend length to taste"

    def to_json(self) -> str:
        data: dict[str, object] = {
            "fx_type": str(self.fx_type) if self.fx_type else None,
            "bars": self.bars,
            "steps": [s.to_dict() for s in self.steps],
            "eq_plan": self.eq_plan.to_dict(),
            "djay_tempo_adjust": self.djay_tempo_adjust,
            "mix_in_section": self.mix_in_section,
            "mix_out_section": self.mix_out_section,
            "phrase_align": self.phrase_align,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "subgenre_modifier": self.subgenre_modifier,
            "rescue_move": self.rescue_move,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str | None) -> TransitionRecipe | None:
        """Deserialise from DB JSON. Returns None on invalid input."""
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        fx_type: NeuralMixCrossfaderFX | None = None
        fx_raw = data.get("fx_type")
        if isinstance(fx_raw, str):
            try:
                fx_type = NeuralMixCrossfaderFX(fx_raw)
            except ValueError:
                pass  # legacy value — gracefully ignored

        steps_raw = data.get("steps", [])
        steps: tuple[RecipeStep, ...] = ()
        if isinstance(steps_raw, list):
            steps = tuple(
                s for raw_s in steps_raw if (s := RecipeStep.from_dict(raw_s)) is not None
            )

        return cls(
            fx_type=fx_type,
            bars=_coerce_int(data.get("bars")) or 16,
            steps=steps,
            eq_plan=EQPlan.from_dict(data.get("eq_plan")),
            djay_tempo_adjust=data.get("djay_tempo_adjust", "none") or "none",
            mix_in_section=_coerce_optional_str(data.get("mix_in_section")),
            mix_out_section=_coerce_optional_str(data.get("mix_out_section")),
            phrase_align=bool(data.get("phrase_align", True)),
            warnings=tuple(w for w in data.get("warnings", []) if isinstance(w, str)),
            confidence=_coerce_float(data.get("confidence")) or 0.75,
            subgenre_modifier=_coerce_optional_str(data.get("subgenre_modifier")),
            rescue_move=data.get("rescue_move", "adjust blend length to taste")
            or "adjust blend length to taste",
        )

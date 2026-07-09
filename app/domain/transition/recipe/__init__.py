"""Stem-keyframe recipe model for djay Pro 5 Neural Mix transitions.

A ``NeuralMixRecipe`` describes a transition between deck A and deck B
as a deterministic envelope over the four Neural Mix stems
(drums / bass / harmonic / vocals) on each deck. It is the persisted
artefact a DJ tool (or a human DJ) would replay against the two tracks
to reproduce the chosen transition.

Shape:

* ``transition`` — which of the seven Neural Mix presets this recipe
  realises (FADE / ECHO_OUT / VOCAL_SUSTAIN / HARMONIC_SUSTAIN /
  DRUM_SWAP / VOCAL_CUT / DRUM_CUT).
* ``bars`` — total transition length in bars. Default 32.
* ``keyframes`` — ordered tuple of ``StemKeyframe`` entries. Each
  keyframe sets the level (in dB, ``LEVEL_SILENT`` for muted) of one
  stem on one deck at one bar position. Linear interpolation between
  consecutive keyframes for the same (deck, stem) channel.
* ``fx_events`` — Mute FX echo-tail trigger events (1, ¾ or ½ beat
  spacing per Algoriddim's Mute FX engine). Used by ECHO_OUT,
  VOCAL_CUT, DRUM_CUT.
* ``mix_in_section`` / ``mix_out_section`` — optional structural anchor
  labels (``"intro"``, ``"outro"``, ``"breakdown"``...).
* ``confidence`` — picker confidence in [0, 1].
* ``rescue`` — fallback transition if the recipe fails at runtime.
* ``explanation`` — human-readable why-this-preset string.
* ``warnings`` — caveats the picker raised (vocal overlap, key clash...).

JSON serialisation is symmetric (``to_json`` / ``from_json``); the
DB column ``transitions.transition_recipe_json`` stores the round-tripped
form.
"""

from __future__ import annotations

import dataclasses
import json
import math
from enum import StrEnum
from typing import Any, Literal, cast

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition

# Sentinel level value representing full silence. Below this floor a
# stem is treated as muted by any audio engine that consumes the recipe.
# Stored in JSON as a finite number (JSON doesn't support ``-Infinity``);
# in Python we read both ``-inf`` and ``LEVEL_SILENT`` as silent.
LEVEL_SILENT: float = -120.0
LEVEL_UNITY: float = 0.0
DEFAULT_TRANSITION_BARS: int = 32

Deck = Literal["A", "B"]


class MuteFXTrigger(StrEnum):
    """Mute FX echo-tail trigger spacing (per djay's Mute FX engine).

    See https://help.algoriddim.com/user-manual/djay-ios/neural-mix/mute-fx
    """

    ECHO_1 = "echo_1"  # one-beat echo tail
    ECHO_3_4 = "echo_3_4"  # three-quarter beat tail (default for ECHO_OUT)
    ECHO_1_2 = "echo_1_2"  # half-beat tail (stutter feel; VOCAL_CUT, DRUM_CUT)


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else None


def _coerce_level(value: object) -> float | None:
    """Coerce a level_db value, treating non-finite as silence."""
    f = _coerce_float(value)
    if f is None:
        return None
    if not math.isfinite(f) or f <= LEVEL_SILENT:
        return LEVEL_SILENT
    return f


@dataclasses.dataclass(frozen=True)
class StemKeyframe:
    """One level keyframe for one stem channel at one bar position.

    A keyframe declares ``stem`` on ``deck`` should reach ``level_db``
    at musical position ``bar``. The audio engine linearly interpolates
    between consecutive keyframes for the same (deck, stem) channel.
    """

    bar: float
    deck: Deck
    stem: NeuralMixStem
    level_db: float

    def to_dict(self) -> dict[str, object]:
        # Preserve -inf as LEVEL_SILENT so JSON stays finite.
        level = self.level_db
        if not math.isfinite(level) or level <= LEVEL_SILENT:
            level = LEVEL_SILENT
        return {
            "bar": self.bar,
            "deck": self.deck,
            "stem": str(self.stem),
            "level_db": level,
        }

    @classmethod
    def from_dict(cls, data: object) -> StemKeyframe | None:
        if not isinstance(data, dict):
            return None

        bar = _coerce_float(data.get("bar"))
        if bar is None:
            return None

        deck = data.get("deck")
        if not isinstance(deck, str) or deck not in ("A", "B"):
            return None

        stem_raw = data.get("stem")
        if not isinstance(stem_raw, str):
            return None
        try:
            stem = NeuralMixStem(stem_raw)
        except ValueError:
            return None

        level = _coerce_level(data.get("level_db"))
        if level is None:
            return None

        return cls(
            bar=bar,
            deck=cast(Deck, deck),
            stem=stem,
            level_db=level,
        )


@dataclasses.dataclass(frozen=True)
class MuteFXEvent:
    """Mute FX echo-tail trigger on one stem channel at one bar position."""

    bar: float
    deck: Deck
    stem: NeuralMixStem
    trigger: MuteFXTrigger

    def to_dict(self) -> dict[str, object]:
        return {
            "bar": self.bar,
            "deck": self.deck,
            "stem": str(self.stem),
            "trigger": str(self.trigger),
        }

    @classmethod
    def from_dict(cls, data: object) -> MuteFXEvent | None:
        if not isinstance(data, dict):
            return None

        bar = _coerce_float(data.get("bar"))
        if bar is None:
            return None

        deck = data.get("deck")
        if not isinstance(deck, str) or deck not in ("A", "B"):
            return None

        stem_raw = data.get("stem")
        if not isinstance(stem_raw, str):
            return None
        try:
            stem = NeuralMixStem(stem_raw)
        except ValueError:
            return None

        trigger_raw = data.get("trigger")
        if not isinstance(trigger_raw, str):
            return None
        try:
            trigger = MuteFXTrigger(trigger_raw)
        except ValueError:
            return None

        return cls(
            bar=bar,
            deck=cast(Deck, deck),
            stem=stem,
            trigger=trigger,
        )


@dataclasses.dataclass(frozen=True)
class NeuralMixRecipe:
    """A complete Neural Mix transition recipe ready for playback or persistence."""

    transition: NeuralMixTransition
    bars: int
    keyframes: tuple[StemKeyframe, ...]
    fx_events: tuple[MuteFXEvent, ...]
    mix_in_section: str | None
    mix_out_section: str | None
    confidence: float
    rescue: NeuralMixTransition
    explanation: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "transition": str(self.transition),
            "bars": self.bars,
            "keyframes": [k.to_dict() for k in self.keyframes],
            "fx_events": [e.to_dict() for e in self.fx_events],
            "confidence": self.confidence,
            "rescue": str(self.rescue),
            "explanation": self.explanation,
            "warnings": list(self.warnings),
        }
        if self.mix_in_section is not None:
            d["mix_in_section"] = self.mix_in_section
        if self.mix_out_section is not None:
            d["mix_out_section"] = self.mix_out_section
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: object) -> NeuralMixRecipe | None:
        if not isinstance(data, dict):
            return None

        transition_raw = data.get("transition")
        if not isinstance(transition_raw, str):
            return None
        try:
            transition = NeuralMixTransition(transition_raw)
        except ValueError:
            return None

        bars = _coerce_int(data.get("bars", DEFAULT_TRANSITION_BARS))
        if bars is None:
            return None

        keyframes_raw = data.get("keyframes", [])
        if not isinstance(keyframes_raw, list):
            return None
        keyframes: list[StemKeyframe] = []
        for kf_raw in keyframes_raw:
            kf = StemKeyframe.from_dict(kf_raw)
            if kf is None:
                return None
            keyframes.append(kf)

        fx_raw = data.get("fx_events", [])
        if not isinstance(fx_raw, list):
            return None
        fx_events: list[MuteFXEvent] = []
        for ev_raw in fx_raw:
            ev = MuteFXEvent.from_dict(ev_raw)
            if ev is None:
                return None
            fx_events.append(ev)

        confidence = _coerce_float(data.get("confidence", 0.5))
        if confidence is None:
            return None

        rescue_raw = data.get("rescue", "echo_out")
        if not isinstance(rescue_raw, str):
            return None
        try:
            rescue = NeuralMixTransition(rescue_raw)
        except ValueError:
            return None

        explanation = data.get("explanation", "")
        if not isinstance(explanation, str):
            return None

        warnings_raw = data.get("warnings", [])
        if not isinstance(warnings_raw, list):
            return None

        mix_in_section = _coerce_optional_str(data.get("mix_in_section"))
        if data.get("mix_in_section") is not None and mix_in_section is None:
            return None
        mix_out_section = _coerce_optional_str(data.get("mix_out_section"))
        if data.get("mix_out_section") is not None and mix_out_section is None:
            return None

        return cls(
            transition=transition,
            bars=bars,
            keyframes=tuple(keyframes),
            fx_events=tuple(fx_events),
            mix_in_section=mix_in_section,
            mix_out_section=mix_out_section,
            confidence=confidence,
            rescue=rescue,
            explanation=explanation,
            warnings=tuple(str(w) for w in warnings_raw),
        )

    @classmethod
    def from_json(cls, raw: str | None) -> NeuralMixRecipe | None:
        if not isinstance(raw, str):
            return None
        try:
            data: Any = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return cls.from_dict(data)

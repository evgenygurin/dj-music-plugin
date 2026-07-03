"""Tests for the Neural Mix recipe primitives + JSON round-trip."""

from __future__ import annotations

import json

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    MuteFXEvent,
    MuteFXTrigger,
    NeuralMixRecipe,
    StemKeyframe,
)

# ── Public surface guards ───────────────────────────────────────────


def test_seven_neural_mix_transitions_exact() -> None:
    assert len(NeuralMixTransition) == 7
    assert {t.value for t in NeuralMixTransition} == {
        "fade",
        "echo_out",
        "vocal_sustain",
        "harmonic_sustain",
        "drum_swap",
        "vocal_cut",
        "drum_cut",
    }


def test_legacy_recipe_types_removed() -> None:
    import app.domain.transition.recipe as recipe_mod

    for legacy in ("TransitionType", "DjayTransition", "StemAction", "RecipeStep", "EQPlan"):
        assert not hasattr(recipe_mod, legacy), f"{legacy} should be gone post Neural Mix refactor"


def test_default_bars_is_32() -> None:
    assert DEFAULT_TRANSITION_BARS == 32


def test_stem_enum_has_four_values() -> None:
    assert {s.value for s in NeuralMixStem} == {"drums", "bass", "harmonics", "vocals"}


def test_mute_fx_trigger_values() -> None:
    assert {t.value for t in MuteFXTrigger} == {"echo_1", "echo_3_4", "echo_1_2"}


# ── StemKeyframe round-trip ─────────────────────────────────────────


def test_keyframe_to_dict_keeps_finite_level() -> None:
    kf = StemKeyframe(bar=0.0, deck="A", stem=NeuralMixStem.DRUMS, level_db=LEVEL_UNITY)
    d = kf.to_dict()
    assert d == {"bar": 0.0, "deck": "A", "stem": "drums", "level_db": 0.0}


def test_keyframe_to_dict_serialises_silence_as_finite_floor() -> None:
    kf = StemKeyframe(bar=8.0, deck="B", stem=NeuralMixStem.VOCALS, level_db=LEVEL_SILENT)
    d = kf.to_dict()
    assert d["level_db"] == LEVEL_SILENT
    json.dumps(d)  # must remain JSON-safe


def test_keyframe_to_dict_handles_minus_inf_input() -> None:
    kf = StemKeyframe(bar=8.0, deck="A", stem=NeuralMixStem.VOCALS, level_db=float("-inf"))
    d = kf.to_dict()
    assert d["level_db"] == LEVEL_SILENT


def test_keyframe_from_dict_round_trip() -> None:
    kf = StemKeyframe(bar=4.5, deck="A", stem=NeuralMixStem.HARMONICS, level_db=-6.0)
    parsed = StemKeyframe.from_dict(kf.to_dict())
    assert parsed == kf


def test_keyframe_from_dict_rejects_unknown_deck() -> None:
    assert (
        StemKeyframe.from_dict({"bar": 0, "deck": "C", "stem": "drums", "level_db": 0.0}) is None
    )


def test_keyframe_from_dict_rejects_unknown_stem() -> None:
    assert (
        StemKeyframe.from_dict({"bar": 0, "deck": "A", "stem": "synth", "level_db": 0.0}) is None
    )


# ── MuteFXEvent round-trip ──────────────────────────────────────────


def test_mute_fx_event_round_trip() -> None:
    ev = MuteFXEvent(bar=1.0, deck="A", stem=NeuralMixStem.VOCALS, trigger=MuteFXTrigger.ECHO_1_2)
    parsed = MuteFXEvent.from_dict(ev.to_dict())
    assert parsed == ev


def test_mute_fx_event_rejects_unknown_trigger() -> None:
    assert (
        MuteFXEvent.from_dict({"bar": 1.0, "deck": "A", "stem": "vocals", "trigger": "echo_5_8"})
        is None
    )


# ── NeuralMixRecipe ─────────────────────────────────────────────────


def _fade_recipe() -> NeuralMixRecipe:
    keyframes: list[StemKeyframe] = []
    for stem in NeuralMixStem:
        keyframes.append(StemKeyframe(bar=0.0, deck="A", stem=stem, level_db=LEVEL_UNITY))
        keyframes.append(
            StemKeyframe(bar=DEFAULT_TRANSITION_BARS, deck="A", stem=stem, level_db=LEVEL_SILENT)
        )
        keyframes.append(StemKeyframe(bar=0.0, deck="B", stem=stem, level_db=LEVEL_SILENT))
        keyframes.append(
            StemKeyframe(bar=DEFAULT_TRANSITION_BARS, deck="B", stem=stem, level_db=LEVEL_UNITY)
        )
    return NeuralMixRecipe(
        transition=NeuralMixTransition.FADE,
        bars=DEFAULT_TRANSITION_BARS,
        keyframes=tuple(keyframes),
        fx_events=(),
        mix_in_section="intro",
        mix_out_section="outro",
        confidence=0.9,
        rescue=NeuralMixTransition.ECHO_OUT,
        explanation="default linear stem crossfade",
        warnings=(),
    )


def test_recipe_default_bars_is_32() -> None:
    recipe = _fade_recipe()
    assert recipe.bars == 32


def test_recipe_json_round_trip_fade() -> None:
    recipe = _fade_recipe()
    parsed = NeuralMixRecipe.from_json(recipe.to_json())
    assert parsed == recipe


def test_recipe_json_round_trip_with_mute_fx() -> None:
    recipe = NeuralMixRecipe(
        transition=NeuralMixTransition.VOCAL_CUT,
        bars=DEFAULT_TRANSITION_BARS,
        keyframes=(
            StemKeyframe(bar=0.0, deck="A", stem=NeuralMixStem.VOCALS, level_db=LEVEL_UNITY),
            StemKeyframe(bar=1.0, deck="A", stem=NeuralMixStem.VOCALS, level_db=LEVEL_SILENT),
        ),
        fx_events=(
            MuteFXEvent(
                bar=1.0,
                deck="A",
                stem=NeuralMixStem.VOCALS,
                trigger=MuteFXTrigger.ECHO_1_2,
            ),
        ),
        mix_in_section=None,
        mix_out_section=None,
        confidence=0.85,
        rescue=NeuralMixTransition.ECHO_OUT,
        explanation="vocal cut",
        warnings=("vocal overlap risk",),
    )
    parsed = NeuralMixRecipe.from_json(recipe.to_json())
    assert parsed == recipe


def test_recipe_from_json_returns_none_for_array() -> None:
    assert NeuralMixRecipe.from_json("[]") is None


def test_recipe_from_json_returns_none_for_unknown_transition() -> None:
    payload = json.dumps(
        {
            "transition": "completely_unknown_preset",
            "bars": 32,
            "keyframes": [],
            "fx_events": [],
            "confidence": 0.5,
            "rescue": "echo_out",
            "explanation": "",
            "warnings": [],
        }
    )
    assert NeuralMixRecipe.from_json(payload) is None


def test_recipe_from_json_returns_none_for_malformed_keyframe() -> None:
    payload = json.dumps(
        {
            "transition": "fade",
            "bars": 32,
            "keyframes": [{"bar": 0, "deck": "C", "stem": "drums", "level_db": 0.0}],
            "fx_events": [],
            "confidence": 0.5,
            "rescue": "echo_out",
            "explanation": "",
            "warnings": [],
        }
    )
    assert NeuralMixRecipe.from_json(payload) is None

from __future__ import annotations

from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, NeuralMixRecipe

from .builders.base import BaseRecipeBuilder
from .builders.drum_cut import DrumCutRecipeBuilder
from .builders.drum_swap import DrumSwapRecipeBuilder
from .builders.echo_out import EchoOutRecipeBuilder
from .builders.fade import FadeRecipeBuilder
from .builders.filter_sweep import FilterSweepRecipeBuilder
from .builders.harmonic_sustain import HarmonicSustainRecipeBuilder
from .builders.vocal_cut import VocalCutRecipeBuilder
from .builders.vocal_sustain import VocalSustainRecipeBuilder

_BUILDER_BY_TRANSITION: dict[NeuralMixTransition, BaseRecipeBuilder] = {
    NeuralMixTransition.FADE: FadeRecipeBuilder(),
    NeuralMixTransition.ECHO_OUT: EchoOutRecipeBuilder(),
    NeuralMixTransition.VOCAL_SUSTAIN: VocalSustainRecipeBuilder(),
    NeuralMixTransition.HARMONIC_SUSTAIN: HarmonicSustainRecipeBuilder(),
    NeuralMixTransition.DRUM_SWAP: DrumSwapRecipeBuilder(),
    NeuralMixTransition.VOCAL_CUT: VocalCutRecipeBuilder(),
    NeuralMixTransition.DRUM_CUT: DrumCutRecipeBuilder(),
    NeuralMixTransition.FILTER_SWEEP: FilterSweepRecipeBuilder(),
}


def build_recipe(
    transition: NeuralMixTransition,
    *,
    bars: int = DEFAULT_TRANSITION_BARS,
    mix_in_section: str | None = None,
    mix_out_section: str | None = None,
    confidence: float = 0.5,
    rescue: NeuralMixTransition = NeuralMixTransition.ECHO_OUT,
    explanation: str = "",
    warnings: tuple[str, ...] = (),
) -> NeuralMixRecipe:
    if bars <= 0:
        raise ValueError(f"bars must be positive, got {bars}")
    builder = _BUILDER_BY_TRANSITION[transition]
    keyframes, fx_events = builder.build(bars)
    return NeuralMixRecipe(
        transition=transition,
        bars=bars,
        keyframes=keyframes,
        fx_events=fx_events,
        mix_in_section=mix_in_section,
        mix_out_section=mix_out_section,
        confidence=confidence,
        rescue=rescue,
        explanation=explanation,
        warnings=warnings,
    )

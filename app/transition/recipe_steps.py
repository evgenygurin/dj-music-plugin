"""Stem-oriented step templates for each djay Pro Neural Mix Crossfader FX.

Each builder returns ``(steps, EQPlan)`` for automation / human-readable playbooks.
Stems follow djay's Neural Mix lane model: drums, harmonics (bass+mid melodic), vocals.
"""

from __future__ import annotations

from app.core.constants import NeuralMixCrossfaderFX
from app.transition.recipe import EQPlan, RecipeStep
from app.transition.types import StemAction


def _h(len_bars: int) -> int:
    return max(len_bars // 2, 1) if len_bars else 0


def build_steps_for_fx(
    fx: NeuralMixCrossfaderFX,
    bars: int,
) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    """Factory: pick the template matching the active Crossfader FX preset."""
    builders: dict[NeuralMixCrossfaderFX, object] = {
        NeuralMixCrossfaderFX.NEURAL_MIX_FADE: _steps_fade,
        NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT: _steps_echo_out,
        NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_SUSTAIN: _steps_vocal_sustain,
        NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN: _steps_harmonic_sustain,
        NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP: _steps_drum_swap,
        NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_CUT: _steps_vocal_cut,
        NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT: _steps_drum_cut,
    }
    fn = builders[fx]
    return fn(bars)  # type: ignore[operator,misc]


def _steps_fade(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = _h(bars)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Bring in B: Neural Mix Fade — all stems under crossfader AI balance",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=h,
            deck="both",
            action="Mid-crossfader: hand off harmonics and drums per Neural Mix",
            stem="harmonics",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(bar=bars, deck="B", action="Full: A silent, B all stems up"),
    )
    return steps, EQPlan(low="stem", mid="stem", high="stem")


def _steps_echo_out(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = _h(bars)
    steps = (
        RecipeStep(
            bar=0,
            deck="A",
            action="Neural Mix Echo Out — echo engaged on outgoing bus (all stems)",
            effect="echo",
            effect_param=0.45,
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Increase wet; pull A volume while B Neural Mix Fade rises",
            effect="echo",
            effect_param=0.82,
        ),
        RecipeStep(bar=bars, deck="B", action="Release echo; B full"),
    )
    return steps, EQPlan(low="echo_bus", mid="echo_bus", high="echo_bus")


def _steps_vocal_sustain(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = _h(bars)
    steps = (
        RecipeStep(
            bar=0,
            deck="A",
            action="Solo / hold vocal stem on A — Neural Mix Vocal Sustain",
            stem="vocals",
            stem_action=StemAction.SOLO,
        ),
        RecipeStep(
            bar=0,
            deck="B",
            action="Introduce B drums and harmonics under held vocal",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Release vocal hold into B or crossfade vocal to B",
            stem="vocals",
            stem_action=StemAction.FADE_OUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full"),
    )
    return steps, EQPlan(low="stem", mid="stem", high="vocal_hold")


def _steps_harmonic_sustain(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = _h(bars)
    steps = (
        RecipeStep(
            bar=0,
            deck="A",
            action="Hold harmonics / pads from A — Harmonic Sustain",
            stem="harmonics",
            stem_action=StemAction.SOLO,
        ),
        RecipeStep(
            bar=0,
            deck="B",
            action="Bring B rhythm under held harmonic bed",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=h,
            deck="both",
            action="Crossfade harmonics to B; fade A",
            stem="harmonics",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(bar=bars, deck="B", action="B full"),
    )
    return steps, EQPlan(low="stem", mid="pad_glue", high="stem")


def _steps_drum_swap(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Neural Mix Drum Swap — cue B, drums aligned",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=q1,
            deck="B",
            action="Raise B drums in the mix",
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Swap: A drums out, B drums carry the phrase",
            stem="drums",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(
            bar=q3,
            deck="A",
            action="Fade A bass/harmonics",
            stem="bass",
            stem_action=StemAction.FADE_OUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full"),
    )
    return steps, EQPlan(low="stem", mid="stem", high="stem")


def _steps_vocal_cut(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = _h(bars)
    steps = (
        RecipeStep(
            bar=0,
            deck="A",
            action="Neural Mix Vocal Cut — mute A vocals for headroom",
            stem="vocals",
            stem_action=StemAction.MUTE,
        ),
        RecipeStep(
            bar=0,
            deck="B",
            action="Bring B under cleared vocal spectrum",
        ),
        RecipeStep(bar=h, deck="both", action="Complete handoff; B takes melodic lead"),
        RecipeStep(bar=bars, deck="B", action="B full"),
    )
    return steps, EQPlan(low="stem", mid="stem", high="cut_vox")


def _steps_drum_cut(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = max(bars // 2, 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Neural Mix Drum Cut — B drums ready at low level",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Cut A drums on the one — B kick lands clean",
            stem="drums",
            stem_action=StemAction.CUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full"),
    )
    return steps, EQPlan(low="cut", mid="stem", high="stem")

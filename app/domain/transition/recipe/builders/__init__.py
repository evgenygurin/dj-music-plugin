from __future__ import annotations

from .base import BaseRecipeBuilder
from .drum_cut import DrumCutRecipeBuilder
from .drum_swap import DrumSwapRecipeBuilder
from .echo_out import EchoOutRecipeBuilder
from .fade import FadeRecipeBuilder
from .filter_sweep import FilterSweepRecipeBuilder
from .harmonic_sustain import HarmonicSustainRecipeBuilder
from .vocal_cut import VocalCutRecipeBuilder
from .vocal_sustain import VocalSustainRecipeBuilder

DEFAULT_BUILDERS: dict[str, BaseRecipeBuilder] = {
    "fade": FadeRecipeBuilder(),
    "echo_out": EchoOutRecipeBuilder(),
    "vocal_sustain": VocalSustainRecipeBuilder(),
    "harmonic_sustain": HarmonicSustainRecipeBuilder(),
    "drum_swap": DrumSwapRecipeBuilder(),
    "vocal_cut": VocalCutRecipeBuilder(),
    "drum_cut": DrumCutRecipeBuilder(),
    "filter_sweep": FilterSweepRecipeBuilder(),
}

__all__ = [
    "DEFAULT_BUILDERS",
    "BaseRecipeBuilder",
    "DrumCutRecipeBuilder",
    "DrumSwapRecipeBuilder",
    "EchoOutRecipeBuilder",
    "FadeRecipeBuilder",
    "FilterSweepRecipeBuilder",
    "HarmonicSustainRecipeBuilder",
    "VocalCutRecipeBuilder",
    "VocalSustainRecipeBuilder",
]

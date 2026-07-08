"""Pure stem-keyframe builders for the eight Neural Mix transitions.

Delegates to ``recipe/builders/`` (BaseRecipeBuilder subclasses) and
``recipe/factory.py`` (build_recipe dispatch). This file is a backward-
compat thin adapter preserving the public API for all external callers.

The individual ``build_<preset>(bars)`` functions remain as internal
helpers used by tests; new code should use ``BaseRecipeBuilder.build()``
or the ``build_recipe()`` factory.
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.transition.neural_mix import NeuralMixStem, NeuralMixTransition
from app.domain.transition.recipe import (
    DEFAULT_TRANSITION_BARS,
    LEVEL_SILENT,
    LEVEL_UNITY,
    Deck,
    MuteFXEvent,
    MuteFXTrigger,
    NeuralMixRecipe,
    StemKeyframe,
)
from app.domain.transition.recipe.envelopes.enter_ramp import _drum_swap_envelope
from app.domain.transition.recipe.envelopes.hold_then_fade import _sustain
from app.domain.transition.recipe.envelopes.kill_with_echo import _cut
from app.domain.transition.recipe.envelopes.linear_fade import _crossfade_full, _hold, _ramp

KeyframeBundle = tuple[
    tuple[StemKeyframe, ...],
    tuple[MuteFXEvent, ...],
]
_Builder = Callable[[int], KeyframeBundle]

# ── Preset builders (pure functions — kept for compat) ──────────────


def build_fade(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    keyframes = _crossfade_full("A", fade_in=False, bars=bars) + _crossfade_full(
        "B", fade_in=True, bars=bars
    )
    return keyframes, ()


def build_echo_out(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    b = float(bars)
    quarter = b * 0.25
    half = b * 0.50
    three_q = b * 0.75
    seven_eighths = b * 0.875

    kfs: list[StemKeyframe] = []
    kfs += [
        _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, quarter - 0.01),
        _hold("A", NeuralMixStem.VOCALS, LEVEL_SILENT, quarter),
    ]
    kfs += [
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, half - 0.01),
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_SILENT, half),
    ]
    for stem in (NeuralMixStem.DRUMS, NeuralMixStem.BASS):
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, three_q - 0.01),
            _hold("A", stem, LEVEL_SILENT, three_q),
        ]
    for stem in (NeuralMixStem.DRUMS, NeuralMixStem.BASS):
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, half),
            _hold("B", stem, LEVEL_UNITY, three_q),
        ]
    kfs += [
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, 0.0),
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, b * 0.625),
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_UNITY, seven_eighths),
    ]
    kfs += [
        _hold("B", NeuralMixStem.VOCALS, LEVEL_SILENT, 0.0),
        _hold("B", NeuralMixStem.VOCALS, LEVEL_SILENT, seven_eighths),
        _hold("B", NeuralMixStem.VOCALS, LEVEL_UNITY, b),
    ]

    fx = (
        MuteFXEvent(
            bar=quarter, deck="A", stem=NeuralMixStem.VOCALS, trigger=MuteFXTrigger.ECHO_3_4
        ),
        MuteFXEvent(
            bar=half, deck="A", stem=NeuralMixStem.HARMONICS, trigger=MuteFXTrigger.ECHO_3_4
        ),
        MuteFXEvent(
            bar=three_q, deck="A", stem=NeuralMixStem.DRUMS, trigger=MuteFXTrigger.ECHO_3_4
        ),
        MuteFXEvent(
            bar=three_q, deck="A", stem=NeuralMixStem.BASS, trigger=MuteFXTrigger.ECHO_3_4
        ),
    )
    return tuple(kfs), fx


def build_vocal_sustain(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    return _sustain(bars, NeuralMixStem.VOCALS), ()


def build_harmonic_sustain(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    return _sustain(bars, NeuralMixStem.HARMONICS), ()


def build_drum_swap(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    return _drum_swap_envelope(bars), ()


def build_vocal_cut(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    return _cut(bars, NeuralMixStem.VOCALS, slam_back=False)


def build_drum_cut(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    return _cut(bars, NeuralMixStem.DRUMS, slam_back=True)


def build_filter_sweep(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    a_kfs: list[StemKeyframe] = []
    b_kfs: list[StemKeyframe] = []

    for stem in (
        NeuralMixStem.DRUMS,
        NeuralMixStem.BASS,
        NeuralMixStem.HARMONICS,
        NeuralMixStem.VOCALS,
    ):
        a_kfs.append(_hold("A", stem, LEVEL_UNITY, 0))
        a_kfs.extend(_ramp("A", stem, 4, bars, LEVEL_UNITY, LEVEL_SILENT))

        b_kfs.append(_hold("B", stem, LEVEL_SILENT, 0))
        b_kfs.extend(_ramp("B", stem, 4, bars, LEVEL_SILENT, LEVEL_UNITY))

    return tuple(a_kfs + b_kfs), ()


# ── Public dispatcher (via recipe factory) ──────────────────────────

from app.domain.transition.recipe.factory import build_recipe  # noqa: E402, F811


__all__ = [
    "build_drum_cut",
    "build_drum_swap",
    "build_echo_out",
    "build_fade",
    "build_filter_sweep",
    "build_harmonic_sustain",
    "build_recipe",
    "build_vocal_cut",
    "build_vocal_sustain",
]

"""Pure stem-keyframe builders for the seven Neural Mix transitions.

Each ``build_<preset>(bars)`` returns a ``(keyframes, fx_events)`` tuple
describing the per-deck per-stem level envelope and Mute FX echo-tail
events for that preset over ``bars`` bars (default 32).

Linear interpolation is assumed between consecutive keyframes for the
same ``(deck, stem)`` channel; an audio engine consuming the recipe
snaps levels ≤ ``LEVEL_SILENT`` to mute.

Per-preset matrices are derived from Algoriddim's published Neural Mix
behaviour (see ``docs/transition-scoring.md`` and the audit notes in
``docs/research/``). All seven default to bars=32 per the project
constraint that templates scale a uniform base length.
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

KeyframeBundle = tuple[
    tuple[StemKeyframe, ...],
    tuple[MuteFXEvent, ...],
]
_Builder = Callable[[int], KeyframeBundle]

# ── Helpers ─────────────────────────────────────────────────────────


def _hold(deck: Deck, stem: NeuralMixStem, level: float, bar: float) -> StemKeyframe:
    return StemKeyframe(bar=bar, deck=deck, stem=stem, level_db=level)


def _ramp(
    deck: Deck,
    stem: NeuralMixStem,
    start_bar: float,
    end_bar: float,
    start_level: float,
    end_level: float,
) -> tuple[StemKeyframe, StemKeyframe]:
    """Two-keyframe linear ramp on one channel."""
    return (
        StemKeyframe(bar=start_bar, deck=deck, stem=stem, level_db=start_level),
        StemKeyframe(bar=end_bar, deck=deck, stem=stem, level_db=end_level),
    )


def _crossfade_full(deck: Deck, *, fade_in: bool, bars: int) -> tuple[StemKeyframe, ...]:
    """Linear ramp on all four stems for one deck across the full transition."""
    start = LEVEL_SILENT if fade_in else LEVEL_UNITY
    end = LEVEL_UNITY if fade_in else LEVEL_SILENT
    out: list[StemKeyframe] = []
    for stem in NeuralMixStem:
        out.extend(_ramp(deck, stem, 0.0, float(bars), start, end))
    return tuple(out)


# ── Preset builders ─────────────────────────────────────────────────


def build_fade(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """Pairwise linear stem crossfade A → B over ``bars``."""
    keyframes = _crossfade_full("A", fade_in=False, bars=bars) + _crossfade_full(
        "B", fade_in=True, bars=bars
    )
    return keyframes, ()


def build_echo_out(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """Sequential stem-kill on A with echo tails; B fades up underneath.

    A.vocals dies first (bar 0.25 * bars), A.harmonic next (bar 0.50),
    A.{drums,bass} last (bar 0.75). B fades the inverse — drums+bass
    in first, then harmonic, then vocals — so the rhythm bed is
    re-established before the new vocal line lands.
    """
    b = float(bars)
    quarter = b * 0.25
    half = b * 0.50
    three_q = b * 0.75
    seven_eighths = b * 0.875

    kfs: list[StemKeyframe] = []
    # A.vocals — 0 dB until ¼, kill with echo tail at bar=¼.
    kfs += [
        _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.VOCALS, LEVEL_UNITY, quarter - 0.01),
        _hold("A", NeuralMixStem.VOCALS, LEVEL_SILENT, quarter),
    ]
    # A.harmonic — 0 dB until ½, kill at ½.
    kfs += [
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_UNITY, half - 0.01),
        _hold("A", NeuralMixStem.HARMONICS, LEVEL_SILENT, half),
    ]
    # A.drums and A.bass — 0 dB until ¾, kill at ¾.
    for stem in (NeuralMixStem.DRUMS, NeuralMixStem.BASS):
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, three_q - 0.01),
            _hold("A", stem, LEVEL_SILENT, three_q),
        ]
    # B.drums and B.bass — silent until ½, ramp to 0 dB by ¾.
    for stem in (NeuralMixStem.DRUMS, NeuralMixStem.BASS):
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, half),
            _hold("B", stem, LEVEL_UNITY, three_q),
        ]
    # B.harmonic — silent until 0.625*bars, ramp to 0 dB by 0.875*bars.
    kfs += [
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, 0.0),
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_SILENT, b * 0.625),
        _hold("B", NeuralMixStem.HARMONICS, LEVEL_UNITY, seven_eighths),
    ]
    # B.vocals — silent until 0.875*bars, ramp to 0 dB by full length.
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


def _sustain(
    bars: int,
    sustained_stem: NeuralMixStem,
) -> tuple[StemKeyframe, ...]:
    """Shared envelope for VOCAL_SUSTAIN / HARMONIC_SUSTAIN.

    The ``sustained_stem`` from deck A is held through 0.75*bars, then
    ramped down by the end. Other A stems crossfade out by 0.75*bars
    while the same set on B fades in. B's mirror of ``sustained_stem``
    enters last (over the final 1/8 of the transition).
    """
    b = float(bars)
    quarter = b * 0.25
    three_q = b * 0.75
    seven_eighths = b * 0.875
    kfs: list[StemKeyframe] = []

    other_stems = tuple(s for s in NeuralMixStem if s is not sustained_stem)

    # Sustained stem on A: hold until 3/4, fade out to end.
    kfs += [
        _hold("A", sustained_stem, LEVEL_UNITY, 0.0),
        _hold("A", sustained_stem, LEVEL_UNITY, three_q),
        _hold("A", sustained_stem, LEVEL_SILENT, b),
    ]
    # Other A stems: hold until 1/4, ramp to silent by 3/4.
    for stem in other_stems:
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, quarter),
            _hold("A", stem, LEVEL_SILENT, three_q),
        ]
    # B stems mirror: other stems silent until 1/4, ramp to 0 dB by 3/4.
    for stem in other_stems:
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, quarter),
            _hold("B", stem, LEVEL_UNITY, three_q),
        ]
    # Sustained stem on B: silent until 7/8, ramp to 0 dB by end.
    kfs += [
        _hold("B", sustained_stem, LEVEL_SILENT, 0.0),
        _hold("B", sustained_stem, LEVEL_SILENT, seven_eighths),
        _hold("B", sustained_stem, LEVEL_UNITY, b),
    ]
    return tuple(kfs)


def build_vocal_sustain(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """A.vocals carries over B.{drums,bass,harmonic} for the middle of the transition."""
    return _sustain(bars, NeuralMixStem.VOCALS), ()


def build_harmonic_sustain(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """A.harmonic (chords / pads) carries over B.{drums,bass,vocals}."""
    return _sustain(bars, NeuralMixStem.HARMONICS), ()


def build_drum_swap(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """Two-phase: swap drums underneath A, then crossfade the rest.

    Phase 1 (0..½): A.drums ↘ silent, B.drums ↗ 0 dB. Other stems hold.
    Phase 2 (½..1): A.{bass,harmonic,vocals} ↘ silent, B counterparts ↗ 0 dB.
    """
    b = float(bars)
    half = b * 0.5
    kfs: list[StemKeyframe] = []

    # Drums: cross over in phase 1.
    kfs += [
        _hold("A", NeuralMixStem.DRUMS, LEVEL_UNITY, 0.0),
        _hold("A", NeuralMixStem.DRUMS, LEVEL_SILENT, half),
        _hold("A", NeuralMixStem.DRUMS, LEVEL_SILENT, b),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_SILENT, 0.0),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_UNITY, half),
        _hold("B", NeuralMixStem.DRUMS, LEVEL_UNITY, b),
    ]
    # Other stems: hold A through phase 1, cross over in phase 2.
    for stem in (NeuralMixStem.BASS, NeuralMixStem.HARMONICS, NeuralMixStem.VOCALS):
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, half),
            _hold("A", stem, LEVEL_SILENT, b),
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, half),
            _hold("B", stem, LEVEL_UNITY, b),
        ]
    return tuple(kfs), ()


def _cut(
    bars: int,
    cut_stem: NeuralMixStem,
    *,
    slam_back: bool,
) -> KeyframeBundle:
    """Shared envelope for VOCAL_CUT / DRUM_CUT.

    A.``cut_stem`` is killed at bar 1 with an echo_1_2 trigger. The
    remaining three A stems crossfade with their B counterparts over
    ⅛..⅞ of the transition. B's mirror of ``cut_stem`` enters either:

    * over the last ⅛ as a clean ramp (``slam_back=False``, used by
      VOCAL_CUT), or
    * with a half-bar ramp at the very end (``slam_back=True``, used by
      DRUM_CUT — the drumless-window-then-slam effect).
    """
    b = float(bars)
    eighth = b * 0.125
    seven_eighths = b * 0.875
    kfs: list[StemKeyframe] = []

    # Cut stem on A: 0 dB at bar 0, silent by bar ⅛ (≈4 bars on a 32-bar transition).
    kfs += [
        _hold("A", cut_stem, LEVEL_UNITY, 0.0),
        _hold("A", cut_stem, LEVEL_UNITY, max(0.0, b * 0.03125)),  # ~1 bar on 32-bar
        _hold("A", cut_stem, LEVEL_SILENT, eighth),
    ]
    other_stems = tuple(s for s in NeuralMixStem if s is not cut_stem)
    # Other A stems: 0 dB through ⅛, fade to silent by ⅞.
    for stem in other_stems:
        kfs += [
            _hold("A", stem, LEVEL_UNITY, 0.0),
            _hold("A", stem, LEVEL_UNITY, eighth),
            _hold("A", stem, LEVEL_SILENT, seven_eighths),
        ]
    # Other B stems: silent through ⅛, ramp to 0 dB by ⅞.
    for stem in other_stems:
        kfs += [
            _hold("B", stem, LEVEL_SILENT, 0.0),
            _hold("B", stem, LEVEL_SILENT, eighth),
            _hold("B", stem, LEVEL_UNITY, seven_eighths),
        ]
    # B cut-stem entry: ramp or slam.
    if slam_back:
        # Half-bar slam at the end — sharp, preserves the breakdown feel.
        kfs += [
            _hold("B", cut_stem, LEVEL_SILENT, 0.0),
            _hold("B", cut_stem, LEVEL_SILENT, b - 0.5),
            _hold("B", cut_stem, LEVEL_UNITY, b),
        ]
    else:
        kfs += [
            _hold("B", cut_stem, LEVEL_SILENT, 0.0),
            _hold("B", cut_stem, LEVEL_SILENT, seven_eighths),
            _hold("B", cut_stem, LEVEL_UNITY, b),
        ]

    fx = (MuteFXEvent(bar=eighth, deck="A", stem=cut_stem, trigger=MuteFXTrigger.ECHO_1_2),)
    return tuple(kfs), fx


def build_vocal_cut(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """A.vocals killed early, drums+harmonic crossfade, B.vocals enters last."""
    return _cut(bars, NeuralMixStem.VOCALS, slam_back=False)


def build_drum_cut(bars: int = DEFAULT_TRANSITION_BARS) -> KeyframeBundle:
    """A.drums killed early; drumless overlap window; B.drums slam at the end."""
    return _cut(bars, NeuralMixStem.DRUMS, slam_back=True)


# ── Public dispatcher ──────────────────────────────────────────────


_BUILDERS: dict[NeuralMixTransition, _Builder] = {
    NeuralMixTransition.FADE: build_fade,
    NeuralMixTransition.ECHO_OUT: build_echo_out,
    NeuralMixTransition.VOCAL_SUSTAIN: build_vocal_sustain,
    NeuralMixTransition.HARMONIC_SUSTAIN: build_harmonic_sustain,
    NeuralMixTransition.DRUM_SWAP: build_drum_swap,
    NeuralMixTransition.VOCAL_CUT: build_vocal_cut,
    NeuralMixTransition.DRUM_CUT: build_drum_cut,
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
    """Materialise a ``NeuralMixRecipe`` for the given preset and bar length.

    Per-preset builders are pure; this dispatcher just wraps the
    keyframe / FX bundle into a ``NeuralMixRecipe`` with the supplied
    metadata. Callers (the picker in ``picker.py``) populate
    ``confidence`` / ``rescue`` / ``explanation`` / ``warnings``.
    """
    if bars <= 0:
        raise ValueError(f"bars must be positive, got {bars}")
    builder = _BUILDERS[transition]
    keyframes, fx_events = builder(bars)
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


__all__ = [
    "build_drum_cut",
    "build_drum_swap",
    "build_echo_out",
    "build_fade",
    "build_harmonic_sustain",
    "build_recipe",
    "build_vocal_cut",
    "build_vocal_sustain",
]

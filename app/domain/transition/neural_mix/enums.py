from __future__ import annotations

from enum import StrEnum


class NeuralMixStem(StrEnum):
    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"


class NeuralMixTransition(StrEnum):
    FADE = "fade"
    ECHO_OUT = "echo_out"
    VOCAL_SUSTAIN = "vocal_sustain"
    HARMONIC_SUSTAIN = "harmonic_sustain"
    DRUM_SWAP = "drum_swap"
    VOCAL_CUT = "vocal_cut"
    DRUM_CUT = "drum_cut"
    FILTER_SWEEP = "filter_sweep"

from __future__ import annotations

from app.domain.transition.neural_mix.enums import NeuralMixStem, NeuralMixTransition

NEURAL_MIX_STEMS: tuple[NeuralMixStem, ...] = tuple(NeuralMixStem)
TRANSITION_TYPES: tuple[NeuralMixTransition, ...] = tuple(NeuralMixTransition)

TRANSITION_STEM_WEIGHTS: dict[NeuralMixTransition, dict[NeuralMixStem, float]] = {
    NeuralMixTransition.FADE: {
        NeuralMixStem.DRUMS: 0.25,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.25,
        NeuralMixStem.VOCALS: 0.25,
    },
    NeuralMixTransition.ECHO_OUT: {
        NeuralMixStem.DRUMS: 0.40,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.20,
        NeuralMixStem.VOCALS: 0.15,
    },
    NeuralMixTransition.VOCAL_SUSTAIN: {
        NeuralMixStem.DRUMS: 0.20,
        NeuralMixStem.BASS: 0.10,
        NeuralMixStem.HARMONICS: 0.30,
        NeuralMixStem.VOCALS: 0.40,
    },
    NeuralMixTransition.HARMONIC_SUSTAIN: {
        NeuralMixStem.DRUMS: 0.20,
        NeuralMixStem.BASS: 0.15,
        NeuralMixStem.HARMONICS: 0.40,
        NeuralMixStem.VOCALS: 0.25,
    },
    NeuralMixTransition.DRUM_SWAP: {
        NeuralMixStem.DRUMS: 0.40,
        NeuralMixStem.BASS: 0.30,
        NeuralMixStem.HARMONICS: 0.20,
        NeuralMixStem.VOCALS: 0.10,
    },
    NeuralMixTransition.VOCAL_CUT: {
        NeuralMixStem.DRUMS: 0.30,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.30,
        NeuralMixStem.VOCALS: 0.15,
    },
    NeuralMixTransition.DRUM_CUT: {
        NeuralMixStem.DRUMS: 0.15,
        NeuralMixStem.BASS: 0.30,
        NeuralMixStem.HARMONICS: 0.30,
        NeuralMixStem.VOCALS: 0.25,
    },
    NeuralMixTransition.FILTER_SWEEP: {
        NeuralMixStem.DRUMS: 0.25,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.25,
        NeuralMixStem.VOCALS: 0.25,
    },
}

TRANSITION_ENERGY_BIAS: dict[NeuralMixTransition, float] = {
    NeuralMixTransition.FADE: 0.0,
    NeuralMixTransition.ECHO_OUT: -0.2,
    NeuralMixTransition.VOCAL_SUSTAIN: 0.0,
    NeuralMixTransition.HARMONIC_SUSTAIN: -0.1,
    NeuralMixTransition.DRUM_SWAP: 0.0,
    NeuralMixTransition.VOCAL_CUT: 0.1,
    NeuralMixTransition.DRUM_CUT: 0.5,
    NeuralMixTransition.FILTER_SWEEP: 0.0,
}

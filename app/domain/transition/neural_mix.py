"""Neural Mix stem-aware transition scoring (djay Pro 5 paradigm).

djay Pro 5 ships exactly seven Neural Mix transitions in its Automix UI:
``Fade``, ``Echo Out``, ``Vocal Sustain``, ``Harmonic Sustain``,
``Drum Swap``, ``Vocal Cut``, ``Drum Cut``. Each is a stem-routing recipe
between two decks; this module models the same seven presets as a
scoring layer over four stems (drums / bass / harmonic / vocals) using
existing ``TrackFeatures`` proxies — no real-time stem separation is
required at scoring time.

Sources for the per-preset stem behaviour:
- https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix/overview
- https://help.algoriddim.com/user-manual/djay-ios/neural-mix/mute-fx
- https://www.algoriddim.com/press_releases/447-algoriddim-unveils-djay-pro-5
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.camelot.wheel import camelot_distance
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.math_helpers import bpm_distance, cosine_similarity
from app.domain.transition.score import TransitionScore
from app.shared.features import TrackFeatures


class NeuralMixStem(StrEnum):
    """Four stems Neural Mix routes independently between decks."""

    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"


class NeuralMixTransition(StrEnum):
    """The seven djay Pro 5 Neural Mix Automix transitions.

    Ordered roughly from gentlest (linear stem crossfade) to most
    dramatic (drumless drop into B's slam).
    """

    FADE = "fade"
    ECHO_OUT = "echo_out"
    VOCAL_SUSTAIN = "vocal_sustain"
    HARMONIC_SUSTAIN = "harmonic_sustain"
    DRUM_SWAP = "drum_swap"
    VOCAL_CUT = "vocal_cut"
    DRUM_CUT = "drum_cut"


NEURAL_MIX_STEMS: tuple[NeuralMixStem, ...] = tuple(NeuralMixStem)
TRANSITION_TYPES: tuple[NeuralMixTransition, ...] = tuple(NeuralMixTransition)


# ── Per-transition stem weighting ──────────────────────────────────
# Each preset weights the four stem compatibility scores by which
# stems it actively routes during the transition. Weights sum to 1.0.
#
# Intuition (per djay Pro 5 stem-routing behaviour):
#  * FADE — pairwise crossfade of all 4 stems → uniform 0.25
#  * ECHO_OUT — sequential stem-kill, drums hold the rescue groove → drums dominant
#  * VOCAL_SUSTAIN — A.vocals carries over B.{drums,harmonic} → vocals + harmonics dominant
#  * HARMONIC_SUSTAIN — A.harmonic carries over B.{drums,vocals} → harmonics + vocals dominant
#  * DRUM_SWAP — B.drums under A.{harmonic,vocals,bass} continuity → drums + bass dominant
#  * VOCAL_CUT — A.vocals killed early, drums+harmonic crossfade → drums + harmonics dominant
#  * DRUM_CUT — A.drums killed early, drumless window carries → bass + harmonics + vocals

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
}


# ── Energy-flow bias ───────────────────────────────────────────────
# Each preset has a preferred energy direction.
# +1.0 = strongly prefers ramp-up (B louder than A), -1.0 = prefers cool-down,
# 0.0 = neutral. Magnitudes reflect how dramatic the energy assumption is.

TRANSITION_ENERGY_BIAS: dict[NeuralMixTransition, float] = {
    NeuralMixTransition.FADE: 0.0,
    NeuralMixTransition.ECHO_OUT: -0.2,  # echo tail = gentle wind-down
    NeuralMixTransition.VOCAL_SUSTAIN: 0.0,  # neutral, vocal carry-over works either way
    NeuralMixTransition.HARMONIC_SUSTAIN: -0.1,  # slight cool-down (continuity, not impact)
    NeuralMixTransition.DRUM_SWAP: 0.0,  # groove change without energy change
    NeuralMixTransition.VOCAL_CUT: 0.1,  # decisive cut feels slightly aspirational
    NeuralMixTransition.DRUM_CUT: 0.5,  # drop-style breakdown into slam = ramp-up
}


# ── Result dataclass ───────────────────────────────────────────────


@dataclass
class NeuralMixScore:
    """Stem-aware scoring result for a Neural Mix transition.

    Attributes:
        stem_scores: Per-stem compatibility (drums/bass/harmonics/vocals),
            values in ``[0, 1]``.
        transition_scores: Per-transition-style compatibility, values in
            ``[0, 1]`` for each of the seven Neural Mix transitions.
        best_transition: The transition style with the highest score, or
            ``None`` on hard reject.
        overall: The score of ``best_transition``. What optimizers read.
        hard_reject: True if a hard constraint was violated.
        reject_reason: Human-readable explanation for the reject.
    """

    stem_scores: dict[NeuralMixStem, float] = field(default_factory=dict)
    transition_scores: dict[NeuralMixTransition, float] = field(default_factory=dict)
    best_transition: NeuralMixTransition | None = None
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None

    @property
    def drums_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.DRUMS, 0.0)

    @property
    def bass_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.BASS, 0.0)

    @property
    def harmonic_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)

    @property
    def vocal_compat(self) -> float:
        return self.stem_scores.get(NeuralMixStem.VOCALS, 0.0)


# ── Pure stem-compat functions ─────────────────────────────────────
# Each takes two TrackFeatures and returns a compat score in [0, 1].


def score_drums_compat(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Drum stem compatibility — dominated by tempo lock + kick character."""
    components: list[float] = []
    weights: list[float] = []

    if from_t.bpm is not None and to_t.bpm is not None:
        delta = bpm_distance(from_t.bpm, to_t.bpm)
        sigma = 3.0
        score = math.exp(-(delta**2) / (2 * sigma**2))
        if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
            stability = min(from_t.bpm_stability, to_t.bpm_stability)
            score *= max(0.7, stability)
        components.append(score)
        weights.append(0.50)
    else:
        components.append(0.5)
        weights.append(0.50)

    if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
        diff = abs(from_t.kick_prominence - to_t.kick_prominence)
        components.append(max(0.0, 1.0 - diff))
        weights.append(0.25)

    if from_t.onset_rate is not None and to_t.onset_rate is not None:
        max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
        components.append(max(0.0, 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate))
        weights.append(0.15)

    if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
        components.append(
            cosine_similarity(from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio)
        )
        weights.append(0.10)

    return _weighted_average(components, weights)


def score_bass_compat(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Bass stem compatibility — key compatibility dominates (fundamental clash)."""
    components: list[float] = []
    weights: list[float] = []

    if from_t.key_code is not None and to_t.key_code is not None:
        dist = camelot_distance(from_t.key_code, to_t.key_code)
        base_scores = {0: 1.0, 1: 0.85, 2: 0.55, 3: 0.25, 4: 0.05}
        components.append(base_scores.get(dist, 0.0))
        weights.append(0.65)
    else:
        components.append(0.5)
        weights.append(0.65)

    if from_t.energy_bands and to_t.energy_bands:
        # energy_bands = [sub, low, lowmid, mid, highmid, high]
        bass_a = from_t.energy_bands[0] + from_t.energy_bands[1]
        bass_b = to_t.energy_bands[0] + to_t.energy_bands[1]
        max_bass = max(bass_a, bass_b, 1e-6)
        components.append(max(0.0, 1.0 - abs(bass_a - bass_b) / max_bass))
        weights.append(0.20)

    if from_t.bpm is not None and to_t.bpm is not None:
        delta = bpm_distance(from_t.bpm, to_t.bpm)
        components.append(math.exp(-(delta**2) / 18.0))
        weights.append(0.15)

    return _weighted_average(components, weights)


def score_harmonic_compat(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Harmonic (pads / leads) stem compatibility."""
    components: list[float] = []
    weights: list[float] = []

    if from_t.key_code is not None and to_t.key_code is not None:
        dist = camelot_distance(from_t.key_code, to_t.key_code)
        base_scores = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
        base = base_scores.get(dist, 0.0)
        if from_t.hnr_db is not None and to_t.hnr_db is not None:
            avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
            hnr_factor = max(0.5, min(1.0, (avg_hnr + 30) / 30))
            base *= hnr_factor
        components.append(base)
        weights.append(0.40)
    else:
        components.append(0.5)
        weights.append(0.40)

    if from_t.tonnetz_vector and to_t.tonnetz_vector:
        components.append(cosine_similarity(from_t.tonnetz_vector, to_t.tonnetz_vector))
        weights.append(0.20)

    if from_t.mfcc_vector and to_t.mfcc_vector:
        components.append(cosine_similarity(from_t.mfcc_vector, to_t.mfcc_vector))
        weights.append(0.20)

    if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
        diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
        components.append(max(0.0, 1.0 - diff / 15.0))
        weights.append(0.10)

    dissonance_penalty = 0.0
    if (
        from_t.dissonance_mean is not None
        and to_t.dissonance_mean is not None
        and from_t.dissonance_mean > 0.4
        and to_t.dissonance_mean > 0.4
    ):
        dissonance_penalty = 0.15

    base = _weighted_average(components, weights)
    return max(0.0, base - dissonance_penalty)


def score_vocal_compat(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Vocal stem compatibility — proxy from centroid + chroma + pitch salience."""
    components: list[float] = []
    weights: list[float] = []

    if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
        max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
        components.append(
            max(
                0.0,
                1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c,
            )
        )
        weights.append(0.40)
    else:
        components.append(0.5)
        weights.append(0.40)

    if from_t.chroma_entropy is not None and to_t.chroma_entropy is not None:
        diff = abs(from_t.chroma_entropy - to_t.chroma_entropy)
        components.append(max(0.0, 1.0 - diff / 3.0))
        weights.append(0.30)

    if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
        diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
        components.append(max(0.0, 1.0 - diff / 0.5))
        weights.append(0.30)

    return _weighted_average(components, weights)


# ── Scorer ─────────────────────────────────────────────────────────


class NeuralMixScorer:
    """Stem-aware scorer for the seven djay Pro 5 Neural Mix transitions."""

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
    ) -> NeuralMixScore:
        rejection = check_hard_constraints(from_t, to_t)
        return (
            self._from_rejection(rejection)
            if rejection is not None
            else self._compute(from_t, to_t)
        )

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
    ) -> NeuralMixScore:
        rejection = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
        )
        return (
            self._from_rejection(rejection)
            if rejection is not None
            else self._compute(from_t, to_t)
        )

    @staticmethod
    def _from_rejection(rejection: TransitionScore) -> NeuralMixScore:
        return NeuralMixScore(
            hard_reject=True,
            reject_reason=rejection.reject_reason,
        )

    def _compute(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
    ) -> NeuralMixScore:
        stem_scores: dict[NeuralMixStem, float] = {
            NeuralMixStem.DRUMS: score_drums_compat(from_t, to_t),
            NeuralMixStem.BASS: score_bass_compat(from_t, to_t),
            NeuralMixStem.HARMONICS: score_harmonic_compat(from_t, to_t),
            NeuralMixStem.VOCALS: score_vocal_compat(from_t, to_t),
        }

        energy_delta = _energy_delta_lufs(from_t, to_t)

        transition_scores: dict[NeuralMixTransition, float] = {}
        for transition, weights in TRANSITION_STEM_WEIGHTS.items():
            base = sum(stem_scores[stem] * w for stem, w in weights.items())
            bias = _energy_bias_modifier(transition, energy_delta)
            transition_scores[transition] = max(0.0, min(1.0, base * bias))

        best_transition = max(transition_scores, key=lambda t: transition_scores[t])
        overall = transition_scores[best_transition]

        return NeuralMixScore(
            stem_scores=stem_scores,
            transition_scores=transition_scores,
            best_transition=best_transition,
            overall=overall,
        )


# ── Math helpers ───────────────────────────────────────────────────


def _weighted_average(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.5
    total_w = sum(weights)
    if total_w == 0:
        return 0.5
    return sum(v * w for v, w in zip(values, weights, strict=False)) / total_w


def _energy_delta_lufs(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
        return 0.0
    return to_t.integrated_lufs - from_t.integrated_lufs


def _energy_bias_modifier(transition: NeuralMixTransition, energy_delta: float) -> float:
    """Multiplier in ``[0.7, 1.15]`` reflecting the preset's energy preference."""
    bias = TRANSITION_ENERGY_BIAS[transition]
    if bias == 0.0:
        return 1.0
    normalised = max(-1.0, min(1.0, energy_delta / 4.0))
    alignment = normalised * bias
    return 1.0 + 0.15 * max(0.0, alignment) - 0.30 * max(0.0, -alignment)

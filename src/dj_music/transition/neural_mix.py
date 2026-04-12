"""Neural Mix stem-aware scoring — djay Pro-inspired additive layer.

Algoriddim's **Neural Mix™** (djay Pro) is real-time AI stem separation
that splits a track into four independent channels: drums, bass,
harmonics, vocals. djay Pro's Automix engine then applies nine distinct
transition styles (fade, dissolve, filter, EQ, neural_mix, echo,
echo_out, riser, tremolo) by routing those stems between decks.

This module models the same four stems and nine transitions as a
scoring layer on top of the existing 6-component scorer in
``app/transition/scorer.py``. It computes:

1. Four stem compatibility scores (drums/bass/harmonics/vocals), each
   approximated from already-available audio features.
2. Nine per-transition scores, each a weighted mix of the stem scores
   with a transition-specific stem emphasis.
3. The best-matching Neural Mix transition for a given pair.

Important: this module is **additive**. It does not replace the existing
6-component scorer — it gives a second, stem-aware view of the same
pair. Main's ``TransitionScorer`` still drives the overall quality
score; callers that care specifically about the best Neural Mix
transition style can read from ``NeuralMixScorer``.

The enums here overlap intentionally with ``app.transition.recipe``'s
``DjayTransition`` and ``TransitionType``: the recipe engine models a
bar-by-bar plan, while this module gives a continuous compatibility
score for each Neural Mix transition style.

Sources:
- https://www.algoriddim.com/djay-pro-mac
- https://help.algoriddim.com/topic/hardware/using-neural-mix-on-supported-controllers
- https://help.algoriddim.com/user-manual/djay-pro-mac/settings/automix
- https://www.algoriddim.com/press_releases/435-algoriddim-announces-major-update-to-djay-pro-ai
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from dj_music.core.camelot import camelot_distance
from dj_music.schemas.audio import TrackFeatures
from dj_music.transition.hard_constraints import check_hard_constraints
from dj_music.transition.math_helpers import bpm_distance, cosine_similarity
from dj_music.transition.score import TransitionScore


class NeuralMixStem(StrEnum):
    """Four stems Neural Mix separates in real time."""

    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"


class NeuralMixTransition(StrEnum):
    """djay Pro Automix transition styles, all stem-aware via Neural Mix.

    Ordered roughly from gentlest to most dramatic.
    """

    FADE = "fade"
    DISSOLVE = "dissolve"
    FILTER = "filter"
    EQ = "eq"
    NEURAL_MIX = "neural_mix"
    ECHO = "echo"
    ECHO_OUT = "echo_out"
    RISER = "riser"
    TREMOLO = "tremolo"


NEURAL_MIX_STEMS: tuple[NeuralMixStem, ...] = tuple(NeuralMixStem)
TRANSITION_TYPES: tuple[NeuralMixTransition, ...] = tuple(NeuralMixTransition)


# ── Per-transition stem weighting ──────────────────────────────────
# Each transition style weights the four stem compatibility scores
# differently. Weights sum to 1.0 per transition.
#
# Intuition:
#  * FADE — all stems equal (smooth blend)
#  * DISSOLVE — harmonics & vocals dominate (ambient texture)
#  * FILTER — harmonics dominate (sweep kills bass/drums anyway)
#  * EQ — drums anchor the transition while other bands trade
#  * NEURAL_MIX — balanced (flagship, needs all stems)
#  * ECHO — drums + bass (rhythm foundation for the tail)
#  * ECHO_OUT — drums dominant (tight drum lock critical)
#  * RISER — harmonics for the build, bass for impact
#  * TREMOLO — drums + harmonics (rhythmic pulse)

TRANSITION_STEM_WEIGHTS: dict[NeuralMixTransition, dict[NeuralMixStem, float]] = {
    NeuralMixTransition.FADE: {
        NeuralMixStem.DRUMS: 0.25,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.25,
        NeuralMixStem.VOCALS: 0.25,
    },
    NeuralMixTransition.DISSOLVE: {
        NeuralMixStem.DRUMS: 0.10,
        NeuralMixStem.BASS: 0.15,
        NeuralMixStem.HARMONICS: 0.45,
        NeuralMixStem.VOCALS: 0.30,
    },
    NeuralMixTransition.FILTER: {
        NeuralMixStem.DRUMS: 0.15,
        NeuralMixStem.BASS: 0.15,
        NeuralMixStem.HARMONICS: 0.55,
        NeuralMixStem.VOCALS: 0.15,
    },
    NeuralMixTransition.EQ: {
        NeuralMixStem.DRUMS: 0.45,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.20,
        NeuralMixStem.VOCALS: 0.10,
    },
    NeuralMixTransition.NEURAL_MIX: {
        NeuralMixStem.DRUMS: 0.30,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.25,
        NeuralMixStem.VOCALS: 0.20,
    },
    NeuralMixTransition.ECHO: {
        NeuralMixStem.DRUMS: 0.35,
        NeuralMixStem.BASS: 0.30,
        NeuralMixStem.HARMONICS: 0.20,
        NeuralMixStem.VOCALS: 0.15,
    },
    NeuralMixTransition.ECHO_OUT: {
        NeuralMixStem.DRUMS: 0.50,
        NeuralMixStem.BASS: 0.30,
        NeuralMixStem.HARMONICS: 0.10,
        NeuralMixStem.VOCALS: 0.10,
    },
    NeuralMixTransition.RISER: {
        NeuralMixStem.DRUMS: 0.20,
        NeuralMixStem.BASS: 0.25,
        NeuralMixStem.HARMONICS: 0.40,
        NeuralMixStem.VOCALS: 0.15,
    },
    NeuralMixTransition.TREMOLO: {
        NeuralMixStem.DRUMS: 0.40,
        NeuralMixStem.BASS: 0.20,
        NeuralMixStem.HARMONICS: 0.30,
        NeuralMixStem.VOCALS: 0.10,
    },
}


# ── Energy-flow bias ───────────────────────────────────────────────
# Some transitions prefer a specific energy direction. +1 means the
# transition works best when incoming B is louder than outgoing A,
# -1 means the opposite, 0 means neutral.

TRANSITION_ENERGY_BIAS: dict[NeuralMixTransition, float] = {
    NeuralMixTransition.FADE: 0.0,
    NeuralMixTransition.DISSOLVE: -0.5,
    NeuralMixTransition.FILTER: 0.0,
    NeuralMixTransition.EQ: 0.0,
    NeuralMixTransition.NEURAL_MIX: 0.0,
    NeuralMixTransition.ECHO: -0.2,
    NeuralMixTransition.ECHO_OUT: -0.3,
    NeuralMixTransition.RISER: 1.0,
    NeuralMixTransition.TREMOLO: 0.0,
}


# ── Result dataclass ───────────────────────────────────────────────


@dataclass
class NeuralMixScore:
    """Stem-aware scoring result for a Neural Mix transition.

    Attributes:
        stem_scores: Per-stem compatibility (drums/bass/harmonics/vocals),
            values in ``[0, 1]``.
        transition_scores: Per-transition-style compatibility, values in
            ``[0, 1]`` for each of the nine Neural Mix transitions.
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

    # Convenience accessors ────────────────────────────────

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
    """Drum stem compatibility approximation.

    Drums lock to the master BPM, so drum compat is dominated by tempo
    lock and kick/onset character.
    """
    components: list[float] = []
    weights: list[float] = []

    # BPM match — Gaussian around exact tempo with double/half awareness.
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
    """Bass stem compatibility.

    Bass sits on the fundamental of the key — key compatibility
    dominates because a bass clash is the #1 reason Neural Mix
    transitions sound muddy.
    """
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
    """Vocal stem compatibility approximation.

    We don't have real vocal extraction, so we approximate from:
    * spectral centroid proximity (presence band),
    * chroma entropy similarity (vocal phrasing regularity),
    * pitch salience proximity (dominant-pitch presence).
    """
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
    """Stem-aware scorer for the nine djay Pro Neural Mix transitions.

    Complements ``app.transition.scorer.TransitionScorer`` (the
    6-component quality scorer) by giving a per-stem and per-transition
    view of the same pair of tracks. Hard constraints are shared with
    the main scorer via ``check_hard_constraints``.
    """

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
    ) -> NeuralMixScore:
        """Compute the Neural Mix score for a transition A → B."""
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
        """Score reusing pre-computed candidate distances for hard checks."""
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

    # ── Internals ─────────────────────────────────────────

    @staticmethod
    def _from_rejection(rejection: TransitionScore) -> NeuralMixScore:
        """Lift a TransitionScore hard-reject into a NeuralMixScore reject."""
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
    """Weighted average — returns 0.5 if no components available."""
    if not values:
        return 0.5
    total_w = sum(weights)
    if total_w == 0:
        return 0.5
    return sum(v * w for v, w in zip(values, weights, strict=False)) / total_w


def _energy_delta_lufs(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Signed LUFS delta B - A (positive = ramp up)."""
    if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
        return 0.0
    return to_t.integrated_lufs - from_t.integrated_lufs


def _energy_bias_modifier(transition: NeuralMixTransition, energy_delta: float) -> float:
    """Multiplier in ``[0.7, 1.15]`` depending on transition energy bias.

    - RISER prefers positive delta, penalised on negative.
    - DISSOLVE / ECHO / ECHO_OUT prefer cool-down, penalised on ramp-up.
    - FADE / FILTER / EQ / NEURAL_MIX / TREMOLO are neutral.
    """
    bias = TRANSITION_ENERGY_BIAS[transition]
    if bias == 0.0:
        return 1.0
    normalised = max(-1.0, min(1.0, energy_delta / 4.0))
    alignment = normalised * bias
    return 1.0 + 0.15 * max(0.0, alignment) - 0.30 * max(0.0, -alignment)

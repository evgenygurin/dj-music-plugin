from __future__ import annotations

from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.neural_mix.data import (
    TRANSITION_ENERGY_BIAS,
    TRANSITION_STEM_WEIGHTS,
)
from app.domain.transition.neural_mix.enums import NeuralMixStem, NeuralMixTransition
from app.domain.transition.neural_mix.score_dataclass import NeuralMixScore
from app.domain.transition.score import TransitionScore
from app.domain.transition.scoring.components.bass import BassComponent
from app.domain.transition.scoring.components.drums import DrumsComponent
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent
from app.domain.transition.scoring.components.vocals import VocalsComponent
from app.shared.features import TrackFeatures

_COMPONENTS = (
    DrumsComponent(),
    BassComponent(),
    HarmonicsComponent(),
    VocalsComponent(),
)
_NAMES: dict[str, NeuralMixStem] = {
    "drums": NeuralMixStem.DRUMS,
    "bass": NeuralMixStem.BASS,
    "harmonics": NeuralMixStem.HARMONICS,
    "vocals": NeuralMixStem.VOCALS,
}


class NeuralMixScorer:
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
        stem_scores: dict[NeuralMixStem, float] = {}
        for comp in _COMPONENTS:
            nm_stem = _NAMES.get(comp.name)
            if nm_stem is not None:
                stem_scores[nm_stem] = comp.score(from_t, to_t)

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


def _energy_delta_lufs(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
        return 0.0
    return to_t.integrated_lufs - from_t.integrated_lufs


def _energy_bias_modifier(transition: NeuralMixTransition, energy_delta: float) -> float:
    bias = TRANSITION_ENERGY_BIAS[transition]
    if bias == 0.0:
        return 1.0
    normalised = max(-1.0, min(1.0, energy_delta / 4.0))
    alignment = normalised * bias
    return 1.0 + 0.15 * max(0.0, alignment) - 0.30 * max(0.0, -alignment)

"""Adapters connecting the legacy scorer and universal planner contracts."""

from __future__ import annotations

from typing import Any, cast

from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator
from app.domain.mixing.evaluation import FeatureSet
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.selection import SelectionPolicy
from app.domain.mixing.transition import TransitionDecision
from app.domain.transition.neural_mix import NeuralMixTransition
from app.shared.features import TrackFeatures


class LegacyTransitionPlannerAdapter:
    """Plan through the existing production ``TransitionScorer``."""

    def __init__(self, scorer: Any, validator: HardConstraintValidator | None = None) -> None:
        self._scorer = scorer
        self._validator = validator or HardConstraintValidator()

    def plan(
        self,
        candidates: tuple[CandidateTransition, ...],
        features: tuple[TrackFeatures, TrackFeatures],
        policy: SelectionPolicy,
    ) -> TransitionDecision:
        source, target = features
        ranked: list[tuple[CandidateTransition, Any]] = []
        rejected: list[tuple[str, str]] = []
        margins: dict[str, float] = {}
        for candidate in candidates:
            technical = self._validator.validate(candidate)
            if not technical.accepted:
                rejected.append((candidate.candidate_id, technical.reason or "technical"))
                continue
            margins[candidate.candidate_id] = technical.technical_margin
            score = self._scorer.score(source, target)
            if score.hard_reject:
                rejected.append((candidate.candidate_id, score.reject_reason or "hard_reject"))
                continue
            ranked.append((candidate, score))
        if not ranked:
            raise ValueError("no technically acceptable transition candidates")
        ranked.sort(key=lambda item: (-_legacy_rank_value(item[1], policy), item[0].candidate_id))
        chosen, score = ranked[0]
        bars = max(1, round(chosen.duration_s * chosen.source_tempo.bpm / 60 / 4))
        recipe = _legacy_recipe(score.best_transition, bars)
        diagnostics = (
            f"selected:{chosen.candidate_id}",
            f"policy:{policy}",
            f"legacy_score:{float(score.overall):.6f}",
            *tuple(f"rejected:{reason}" for _, reason in rejected),
        )
        plan = TransitionPlan.create(
            chosen.source_hash,
            chosen.target_hash,
            recipe.bars,
            chosen.source_tempo.bpm,
            recipe,
            source_analysis_identity=chosen.source_hash,
            target_analysis_identity=chosen.target_hash,
            diagnostics=diagnostics,
        )
        return TransitionDecision(
            plan,
            tuple(item[0].candidate_id for item in ranked[1:]),
            tuple(rejected),
            policy,
            diagnostics,
            float(score.overall),
            margins[chosen.candidate_id],
            _legacy_dimensions(score),
        )

    __call__ = plan


class UniversalTransitionPlannerAdapter:
    """Adapt persisted ``TrackFeatures`` into the universal FeatureSet contract."""

    def __init__(self, planner: Any) -> None:
        self._planner = planner

    def plan(
        self,
        candidates: tuple[CandidateTransition, ...],
        features: tuple[TrackFeatures, TrackFeatures],
        policy: SelectionPolicy,
    ) -> TransitionDecision:
        return cast(
            TransitionDecision,
            self._planner.plan(
                candidates,
                (_to_feature_set(features[0]), _to_feature_set(features[1])),
                policy,
            ),
        )

    __call__ = plan


def _legacy_recipe(kind: NeuralMixTransition | None, bars: int) -> Any:
    from app.domain.mixing.recipes import RecipeKind, RecipePlanner

    mapping = {
        NeuralMixTransition.FADE: RecipeKind.FADE,
        NeuralMixTransition.ECHO_OUT: RecipeKind.ECHO_OUT,
        NeuralMixTransition.VOCAL_SUSTAIN: RecipeKind.VOCAL_SUSTAIN,
        NeuralMixTransition.HARMONIC_SUSTAIN: RecipeKind.STEM_BLEND,
        NeuralMixTransition.DRUM_SWAP: RecipeKind.DRUM_SWAP,
        NeuralMixTransition.VOCAL_CUT: RecipeKind.VOCAL_CUT,
        NeuralMixTransition.DRUM_CUT: RecipeKind.DRUM_CUT,
        NeuralMixTransition.FILTER_SWEEP: RecipeKind.FILTER_BLEND,
    }
    recipe_kind = RecipeKind.EQ_BLEND if kind is None else mapping.get(kind, RecipeKind.EQ_BLEND)
    return RecipePlanner().plan(recipe_kind, bars)


def _legacy_dimensions(score: Any) -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (
                ("bpm", float(score.bpm)),
                ("energy", float(score.energy)),
                ("drums", float(score.drums)),
                ("bass", float(score.bass)),
                ("harmonics", float(score.harmonics)),
                ("vocals", float(score.vocals)),
            )
        )
    )


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _norm(value: float | None, low: float, high: float, default: float = 0.5) -> float:
    if value is None:
        return default
    return _clip((float(value) - low) / (high - low))


def _to_feature_set(track: TrackFeatures) -> FeatureSet:
    """Map scalar repository features into normalized universal dimensions."""
    bands = track.energy_bands or []
    low_end = sum(bands[:2]) / len(bands[:2]) if bands[:2] else None
    stem_signal = None
    if track.kick_prominence is not None or track.onset_rate is not None:
        stem_signal = (float(track.kick_prominence or 0.0) + _norm(track.onset_rate, 0.0, 8.0)) / 2
    groove = stem_signal if stem_signal is not None else _norm(track.danceability, 0.0, 1.0)
    vocals = _clip(float(track.voicing_ratio or 0.0))
    timbre = _norm(track.spectral_contrast, 0.0, 40.0)
    spectrum = _norm(track.spectral_centroid_hz, 0.0, 12000.0)
    energy = _norm(track.integrated_lufs, -24.0, -4.0)
    harmony = 0.5
    if track.key_code is not None and track.atonality is not True:
        harmony = _clip(float(track.key_confidence if track.key_confidence is not None else 0.5))
    return FeatureSet(
        harmony=harmony,
        energy=energy,
        low_end=_norm(low_end, 0.0, 1.0),
        spectrum=spectrum,
        groove=_clip(groove),
        timbre=timbre,
        vocals=vocals,
        stems=_clip(stem_signal if stem_signal is not None else 0.5),
    )


def _legacy_rank_value(score: Any, policy: SelectionPolicy) -> float:
    field = {
        SelectionPolicy.MOST_HARMONIC: "harmonics",
        SelectionPolicy.MOST_ENERGETIC: "energy",
        SelectionPolicy.MOST_GROOVY: "drums",
        SelectionPolicy.MOST_SMOOTH: "harmonics",
    }.get(policy)
    return float(getattr(score, field, score.overall)) if field else float(score.overall)

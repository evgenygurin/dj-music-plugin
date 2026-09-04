"""Application orchestration for the universal transition planner."""

from __future__ import annotations

from app.domain.configuration.resolver import ResolvedTransitionConfig
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator
from app.domain.mixing.evaluation import FeatureSet, MusicalEvaluator
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipe_validation import RecipeValidator
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.mixing.scores import DimensionScore, MusicalScore
from app.domain.mixing.selection import SelectionPolicy, select
from app.domain.mixing.transition import TransitionDecision


class TransitionPlanner:
    def __init__(
        self,
        validator: HardConstraintValidator | None = None,
        *,
        config_resolver: object | None = None,
        resolved_config: ResolvedTransitionConfig | None = None,
    ) -> None:
        self._config_resolver = config_resolver
        self._config = resolved_config
        self._validator = validator or HardConstraintValidator()
        if resolved_config is not None:
            max_ratio = resolved_config.values.get("tempo.max_ratio")
            if max_ratio is not None:
                self._validator = HardConstraintValidator(max_tempo_ratio=max_ratio)
        self._evaluator = MusicalEvaluator()
        self._recipes = RecipePlanner()
        self._recipe_validator = RecipeValidator()

    def plan(
        self,
        candidates: tuple[CandidateTransition, ...],
        features: tuple[FeatureSet, FeatureSet],
        policy: SelectionPolicy,
        *,
        config_identity: str = "",
    ) -> TransitionDecision:
        if self._config is not None:
            config_identity = self._config.config_hash
        scores: list[tuple[str, MusicalScore]] = []
        rejected: list[tuple[str, str]] = []
        source_features, target_features = features
        for candidate in candidates:
            technical = self._validator.validate(candidate)
            if not technical.accepted:
                rejected.append((candidate.candidate_id, technical.reason or "technical"))
                continue
            musical = self._evaluator.evaluate(source_features, target_features)
            alignment_penalty = min(
                1.0,
                abs(candidate.downbeat_offset_beats) / 4.0
                + abs(candidate.phrase_offset_bars) / 16.0,
            )
            musical = MusicalScore(
                (*musical.dimensions, DimensionScore("alignment", 1.0 - alignment_penalty)),
            )
            scores.append((candidate.candidate_id, musical))
        if not scores:
            raise ValueError("no technically acceptable transition candidates")
        selection = select(tuple(scores), policy)
        chosen = next(c for c in candidates if c.candidate_id == selection.selected)
        bars = max(1, round(chosen.duration_s * chosen.source_tempo.bpm / 60 / 4))
        recipe = self._recipes.plan(RecipeKind.EQ_BLEND, bars)
        if not self._recipe_validator.validate(recipe).accepted:
            raise ValueError("generated recipe failed validation")
        diagnostics = [
            f"selected:{selection.selected}",
            f"policy:{policy}",
            f"alignment:downbeat={chosen.downbeat_offset_beats:g}",
            f"alignment:phrase_bars={chosen.phrase_offset_bars}",
        ]
        diagnostics.extend(f"rejected:{reason}" for _, reason in rejected)
        plan = TransitionPlan.create(
            chosen.source_hash,
            chosen.target_hash,
            recipe.bars,
            chosen.source_tempo.bpm,
            recipe,
            config_identity=config_identity,
            source_analysis_identity=chosen.source_hash,
            target_analysis_identity=chosen.target_hash,
            diagnostics=tuple(diagnostics),
        )
        return TransitionDecision(plan, selection.alternatives, tuple(rejected), policy)

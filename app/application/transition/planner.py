"""Application orchestration for the universal transition planner."""

from __future__ import annotations

from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator
from app.domain.mixing.evaluation import FeatureSet, MusicalEvaluator
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipe_validation import RecipeValidator
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.mixing.scores import MusicalScore
from app.domain.mixing.selection import SelectionPolicy, select
from app.domain.mixing.transition import TransitionDecision


class TransitionPlanner:
    def __init__(self, validator: HardConstraintValidator | None = None) -> None:
        self._validator = validator or HardConstraintValidator()
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
        scores: list[tuple[str, MusicalScore]] = []
        rejected: list[tuple[str, str]] = []
        source_features, target_features = features
        for candidate in candidates:
            technical = self._validator.validate(candidate)
            if not technical.accepted:
                rejected.append((candidate.candidate_id, technical.reason or "technical"))
                continue
            musical = self._evaluator.evaluate(source_features, target_features)
            scores.append((candidate.candidate_id, musical))
        if not scores:
            raise ValueError("no technically acceptable transition candidates")
        selection = select(tuple(scores), policy)
        chosen = next(c for c in candidates if c.candidate_id == selection.selected)
        bars = max(1, round(chosen.duration_s * chosen.source_tempo.bpm / 60 / 4))
        recipe = self._recipes.plan(RecipeKind.EQ_BLEND, bars)
        if not self._recipe_validator.validate(recipe).accepted:
            raise ValueError("generated recipe failed validation")
        plan = TransitionPlan.create(
            chosen.source_hash,
            chosen.target_hash,
            recipe.bars,
            chosen.source_tempo.bpm,
            recipe,
            config_identity=config_identity,
            source_analysis_identity=chosen.source_hash,
            target_analysis_identity=chosen.target_hash,
            diagnostics=tuple(
                [f"selected:{selection.selected}", f"policy:{policy}"]
                + [f"rejected:{reason}" for _, reason in rejected]
            ),
        )
        return TransitionDecision(plan, selection.alternatives, tuple(rejected), policy)

"""Independent validation of renderer-facing transition recipes."""

from __future__ import annotations

from dataclasses import dataclass

from .recipes import RecipeKind, TransitionRecipe


@dataclass(frozen=True, slots=True)
class RecipeValidation:
    accepted: bool
    reason: str | None = None


class RecipeValidator:
    def validate(self, recipe: TransitionRecipe) -> RecipeValidation:
        if recipe.bars <= 0:
            return RecipeValidation(False, "bars_positive")
        if recipe.kind not in tuple(RecipeKind):
            return RecipeValidation(False, "unsupported_recipe")
        if any(not name.strip() for name, _ in recipe.parameters):
            return RecipeValidation(False, "parameter_name")
        return RecipeValidation(True)

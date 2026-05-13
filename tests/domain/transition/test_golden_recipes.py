"""Level 2 golden tests — recipe envelope snapshots.

For every NeuralMixTransition x bars in {16, 32, 64}, build the recipe
and snapshot the full keyframes + fx_events shape. Tolerance: 1e-9 on
bar positions and level_db; strings/enums exact.

Used to guarantee that splitting builders into BaseRecipeBuilder +
Template Method subclasses (Phase 5) keeps every keyframe byte-identical.
"""

from __future__ import annotations

import pytest

from app.domain.transition.builders import build_recipe
from app.domain.transition.neural_mix import NeuralMixTransition

from ._golden_harness import assert_recipe_equal, load_or_write

_PRESETS = list(NeuralMixTransition)
_BAR_LENGTHS = (16, 32, 64)


@pytest.mark.parametrize("preset", _PRESETS, ids=[p.value for p in _PRESETS])
@pytest.mark.parametrize("bars", _BAR_LENGTHS)
def test_recipe_envelope_golden(preset: NeuralMixTransition, bars: int) -> None:
    recipe = build_recipe(
        preset,
        bars=bars,
        mix_in_section="intro",
        mix_out_section="outro",
        confidence=0.85,
        explanation="golden",
    )
    actual = recipe.to_dict()
    expected = load_or_write(f"recipe_{preset.value}_{bars}", actual)
    assert_recipe_equal(actual, expected)

"""Freeze test for app.domain.transition.__all__.

Any edit to the public API must update FROZEN_NAMES below. The whole
v1.5.0 refactor preserves these 21 names; additions are allowed (new
Protocols, registries) but removals are breaking changes.
"""

from __future__ import annotations

import app.domain.transition as transition_pkg

FROZEN_NAMES: frozenset[str] = frozenset(
    {
        "DEFAULT_TRANSITION_BARS",
        "LEVEL_SILENT",
        "LEVEL_UNITY",
        "MuteFXEvent",
        "MuteFXTrigger",
        "NeuralMixRecipe",
        "NeuralMixScore",
        "NeuralMixScorer",
        "NeuralMixStem",
        "NeuralMixTransition",
        "PickerDecision",
        "SectionContext",
        "StemKeyframe",
        "TransitionScore",
        "TransitionScorer",
        "bpm_distance",
        "build_recipe",
        "build_recipe_for_pair",
        "correlation",
        "cosine_similarity",
        "pick_neural_mix",
    }
)


def test_public_api_is_superset_of_frozen() -> None:
    current = set(transition_pkg.__all__)
    missing = FROZEN_NAMES - current
    assert not missing, f"removed from public API: {sorted(missing)}"


def test_frozen_names_are_importable() -> None:
    for name in FROZEN_NAMES:
        obj = getattr(transition_pkg, name, None)
        assert obj is not None, f"{name} not importable from app.domain.transition"


def test_no_unexpected_additions_silently_drift() -> None:
    """Document any additions vs v1.4.0 frozen set without failing.

    Additions are allowed during refactor (new Protocols, registries).
    Removals are caught by the superset test above.
    """
    current = set(transition_pkg.__all__)
    additions = current - FROZEN_NAMES
    if additions:
        print(f"[INFO] public-API additions vs v1.4.0 frozen set: {sorted(additions)}")

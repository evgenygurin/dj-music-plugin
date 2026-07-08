"""Neural Mix transition picker — context-aware decision tree.

Delegates to ``picker/pipeline.py`` (Chain-of-Responsibility PickerPipeline),
``picker/proxies/`` (vocal activity, harmonic motif, Camelot helpers),
and ``recipe/orchestrator.py`` (build_recipe_for_pair).

This file is a backward-compat thin adapter preserving the public API.
"""

from __future__ import annotations

from app.domain.transition.picker.api import PickerDecision  # noqa: F401
from app.domain.transition.picker.pipeline import PickerPipeline, pick_neural_mix  # noqa: F401
from app.domain.transition.picker.proxies.camelot_compatibility import (  # noqa: F401
    _camelot_compatible,
    _energy_delta_lufs,
)
from app.domain.transition.picker.proxies.harmonic_motif import _harmonic_motif  # noqa: F401
from app.domain.transition.picker.proxies.vocal_activity import (  # noqa: F401
    _vocal_active,
    _vocal_data_missing,
    _vocal_low,
)
from app.domain.transition.recipe.orchestrator import build_recipe_for_pair  # noqa: F401

__all__ = [
    "PickerDecision",
    "PickerPipeline",
    "_camelot_compatible",
    "_energy_delta_lufs",
    "_harmonic_motif",
    "_vocal_active",
    "_vocal_data_missing",
    "_vocal_low",
    "build_recipe_for_pair",
    "pick_neural_mix",
]

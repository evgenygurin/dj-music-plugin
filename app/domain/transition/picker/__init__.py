"""Neural Mix transition picker — context-aware decision tree.

Delegates to ``picker/pipeline.py`` (Chain-of-Responsibility PickerPipeline),
``picker/proxies/`` (vocal activity, harmonic motif, Camelot helpers),
and ``recipe/orchestrator.py`` (build_recipe_for_pair).

This file is a backward-compat thin adapter preserving the public API.
"""

from __future__ import annotations

from app.domain.transition.picker.api import PickerDecision
from app.domain.transition.picker.pipeline import PickerPipeline, pick_neural_mix
from app.domain.transition.picker.proxies.camelot_compatibility import (
    _camelot_compatible,
    _energy_delta_lufs,
)
from app.domain.transition.picker.proxies.harmonic_motif import _harmonic_motif
from app.domain.transition.picker.proxies.vocal_activity import (
    _vocal_active,
    _vocal_data_missing,
    _vocal_low,
)
from app.domain.transition.recipe.orchestrator import build_recipe_for_pair

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

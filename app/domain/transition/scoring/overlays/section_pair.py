from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from app.domain.transition.weights import SECTION_PAIR_OVERLAY

if TYPE_CHECKING:
    from app.domain.transition.section_context import SectionContext


class SectionPairOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: Any = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        if section_context is None:
            return dict(weights)

        pair_class = section_context.section_pair_class
        overlay = SECTION_PAIR_OVERLAY.get(pair_class.value)
        if overlay is None:
            return dict(weights)

        raw: dict[str, float] = {}
        for key in ("bpm", "energy", "drums", "bass", "harmonics", "vocals"):
            raw[key] = weights.get(key, 0.0) * overlay.get(key, 1.0)

        total = sum(raw.values())
        if total <= 0.0:
            return dict(weights)

        return {key: value / total for key, value in raw.items()}

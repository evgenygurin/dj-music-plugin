from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from app.domain.transition.intent import INTENT_WEIGHT_MODIFIERS

if TYPE_CHECKING:
    from app.domain.transition.intent import TransitionIntent
    from app.domain.transition.section_context import SectionContext


class IntentOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> dict[str, float]:
        if intent is None:
            return dict(weights)
        modifiers = INTENT_WEIGHT_MODIFIERS.get(intent)
        if modifiers is None:
            return dict(weights)
        return dict(modifiers)

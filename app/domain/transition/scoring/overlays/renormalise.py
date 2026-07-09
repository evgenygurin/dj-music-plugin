from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RenormaliseOverlay:
    def apply(
        self,
        weights: Mapping[str, float],
        *,
        intent: Any = None,
        section_context: Any = None,
    ) -> dict[str, float]:
        total = sum(weights.values())
        if total <= 0.0:
            return dict(weights)
        return {key: value / total for key, value in weights.items()}

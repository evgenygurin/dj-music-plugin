"""OptimizerStrategy Protocol — Strategy pattern for set optimization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.optimization.result import OptimizationResult
    from app.domain.template.models import SetTemplateDefinition
    from app.shared.features import TrackFeatures


class OptimizerStrategy(Protocol):
    """Strategy interface for set optimization algorithms.

    GreedyChainBuilder, GeneticAlgorithm and ConstructiveSlotBuilder
    implement this protocol.
    """

    def optimize(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
        excluded: set[int] | None = None,
        template: SetTemplateDefinition | None = None,
        moods: dict[int, str | None] | None = None,
        on_progress: Callable[[int, float], None] | None = None,
    ) -> OptimizationResult: ...

"""Application use case for pairwise transition scoring."""

from __future__ import annotations

from typing import Any, Protocol


class PairScoreCatalog(Protocol):
    async def features(self, track_ids: list[int]) -> dict[int, Any]: ...


class PairScorer(Protocol):
    def score(self, source: Any, target: Any, *, weights: Any = None) -> Any: ...


class ScoreTransition:
    """Load pair inputs and delegate scoring to the configured scorer."""

    def __init__(self, catalog: PairScoreCatalog, scorer: PairScorer) -> None:
        self._catalog = catalog
        self._scorer = scorer

    async def execute(self, source_id: int, target_id: int, *, weights: Any = None) -> Any:
        features = await self._catalog.features([source_id, target_id])
        missing = [track_id for track_id in (source_id, target_id) if track_id not in features]
        if missing:
            raise ValueError(f"missing scoring features for track_ids={missing}")
        return self._scorer.score(
            features[source_id], features[target_id], weights=weights
        )

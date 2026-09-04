"""Application use case for pairwise transition scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ScoredPair:
    source_id: int
    target_id: int
    overall: float
    bpm: float = 0.0
    harmonics: float = 0.0
    energy: float = 0.0
    bass: float = 0.0
    drums: float = 0.0
    vocals: float = 0.0


@dataclass(frozen=True, slots=True)
class ScorePoolSummary:
    pairs: tuple[ScoredPair, ...]
    hard_rejects: int
    missing_track_ids: tuple[int, ...]
    total_scored_pairs: int


class ScorePoolCatalog(Protocol):
    async def features(self, track_ids: list[int]) -> dict[int, Any]: ...


class PoolScorer(Protocol):
    def score(self, source: Any, target: Any, *, intent: Any = None) -> Any: ...


class ScoreTransitionPool:
    """Score a transition matrix without exposing persistence to the tool layer."""

    def __init__(self, catalog: ScorePoolCatalog, scorer: PoolScorer) -> None:
        self._catalog = catalog
        self._scorer = scorer

    async def execute(
        self,
        track_ids: list[int],
        *,
        intent: Any = None,
        top_k: int | None = None,
        components: bool = True,
    ) -> ScorePoolSummary:
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("track_ids contains duplicate id(s)")
        if not track_ids:
            return ScorePoolSummary((), 0, (), 0)

        features = await self._catalog.features(track_ids)
        missing = tuple(track_id for track_id in track_ids if track_id not in features)
        if not features and len(track_ids) >= 2:
            raise ValueError(
                f"none of the {len(track_ids)} track_ids have scoring features"
            )

        pairs: list[ScoredPair] = []
        hard_rejects = 0
        for source_id in track_ids:
            source = features.get(source_id)
            if source is None:
                continue
            for target_id in track_ids:
                if source_id == target_id:
                    continue
                target = features.get(target_id)
                if target is None:
                    continue
                score = self._scorer.score(source, target, intent=intent)
                if score.hard_reject:
                    hard_rejects += 1
                pairs.append(
                    ScoredPair(
                        source_id,
                        target_id,
                        float(score.overall),
                        float(getattr(score, "bpm", 0.0)) if components else 0.0,
                        float(getattr(score, "harmonics", 0.0)) if components else 0.0,
                        float(getattr(score, "energy", 0.0)) if components else 0.0,
                        float(getattr(score, "bass", 0.0)) if components else 0.0,
                        float(getattr(score, "drums", 0.0)) if components else 0.0,
                        float(getattr(score, "vocals", 0.0)) if components else 0.0,
                    )
                )

        total = len(pairs)
        if top_k is not None:
            selected: list[ScoredPair] = []
            for source_id in track_ids:
                outgoing = [pair for pair in pairs if pair.source_id == source_id]
                selected.extend(
                    sorted(outgoing, key=lambda pair: (-pair.overall, pair.target_id))[:top_k]
                )
            pairs = selected

        return ScorePoolSummary(tuple(pairs), hard_rejects, missing, total)

"""Application use case for transition candidate discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class CandidateSummary:
    track_id: int
    overall: float
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None
    mood: str | None = None
    best_transition: str | None = None
    title: str = ""


class CandidateCatalog(Protocol):
    async def features(self, track_ids: list[int]) -> dict[int, Any]: ...

    async def track_ids(self) -> list[int]: ...


class CandidateScorer(Protocol):
    def score(self, source: Any, target: Any) -> Any: ...


class GenerateTransitionCandidates:
    """Discover and rank candidates without exposing repositories to MCP."""

    def __init__(self, catalog: CandidateCatalog, scorer: CandidateScorer) -> None:
        self._catalog = catalog
        self._scorer = scorer

    async def execute(
        self, track_id: int, *, top_k: int = 20, min_score: float = 0.0
    ) -> tuple[CandidateSummary, ...]:
        source_features = await self._catalog.features([track_id])
        source = source_features.get(track_id)
        if source is None:
            return ()
        candidate_ids = [tid for tid in await self._catalog.track_ids() if tid != track_id]
        features = await self._catalog.features(candidate_ids)
        scored: list[CandidateSummary] = []
        for candidate_id in candidate_ids:
            target = features.get(candidate_id)
            if target is None:
                continue
            score = self._scorer.score(source, target)
            if score.hard_reject or score.overall < min_score:
                continue
            best = score.best_transition.name if score.best_transition else None
            scored.append(
                CandidateSummary(
                    track_id=candidate_id,
                    overall=float(score.overall),
                    bpm=getattr(target, "bpm", None),
                    key=getattr(target, "key_code", None),
                    energy=getattr(target, "energy_mean", None),
                    mood=getattr(target, "mood", None),
                    best_transition=best,
                )
            )
        scored.sort(key=lambda item: (-item.overall, item.track_id))
        return tuple(scored[:top_k])

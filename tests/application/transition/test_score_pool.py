from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.transition.score_pool import ScoreTransitionPool


@dataclass(frozen=True)
class Score:
    overall: float
    hard_reject: bool = False
    bpm: float = 0.1
    harmonics: float = 0.2
    energy: float = 0.3
    bass: float = 0.4
    drums: float = 0.5
    vocals: float = 0.6


class Catalog:
    async def features(self, track_ids: list[int]) -> dict[int, object]:
        return {track_id: object() for track_id in track_ids if track_id != 3}


class Scorer:
    def score(self, source: object, target: object, *, intent=None) -> Score:
        del source, target
        return Score(0.7 if intent == "ramp_up" else 0.5)


@pytest.mark.asyncio
async def test_pool_use_case_scores_pairs_and_applies_top_k() -> None:
    result = await ScoreTransitionPool(Catalog(), Scorer()).execute(
        [1, 2, 3], top_k=1, intent="ramp_up"
    )

    assert [(pair.source_id, pair.target_id) for pair in result.pairs] == [(1, 2), (2, 1)]
    assert result.hard_rejects == 0
    assert result.total_scored_pairs == 2
    assert result.missing_track_ids == (3,)


@pytest.mark.asyncio
async def test_pool_use_case_rejects_duplicates_before_catalog_access() -> None:
    class ExplodingCatalog(Catalog):
        async def features(self, track_ids: list[int]) -> dict[int, object]:
            raise AssertionError("catalog must not be called")

    with pytest.raises(ValueError, match="duplicate"):
        await ScoreTransitionPool(ExplodingCatalog(), Scorer()).execute([1, 1])

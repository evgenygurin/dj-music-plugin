from dataclasses import dataclass

import pytest

from app.application.transition.candidates import GenerateTransitionCandidates


@dataclass(frozen=True)
class FakeFeature:
    bpm: float = 128.0
    key_code: str = "8A"
    energy_mean: float = 0.6
    mood: str | None = None


class FakeCatalog:
    async def features(self, track_ids: list[int]):
        return {tid: FakeFeature() for tid in track_ids if tid != 99}

    async def track_ids(self) -> list[int]:
        return [1, 2, 3, 99]


class FakeScorer:
    def score(self, source, target):
        return type(
            "Score",
            (),
            {
                "hard_reject": False,
                "overall": 0.8,
                "best_transition": type("Transition", (), {"name": "eq_blend"})(),
            },
        )()


@pytest.mark.asyncio
async def test_generate_candidates_uses_application_ports_and_returns_top_k() -> None:
    service = GenerateTransitionCandidates(FakeCatalog(), FakeScorer())

    result = await service.execute(1, top_k=2, min_score=0.0)

    assert [item.track_id for item in result] == [2, 3]
    assert all(item.best_transition == "eq_blend" for item in result)

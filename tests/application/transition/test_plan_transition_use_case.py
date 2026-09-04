from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.transition.plan_request import PlanTransitionRequest, PlanTransitionService
from app.domain.analysis import AnalysisSnapshot, TempoHypothesis
from app.domain.mixing.selection import SelectionPolicy


def _snapshot(name: str, bpm: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(name, "1", tempo_hypotheses=(TempoHypothesis(bpm, 1.0),))


@pytest.mark.asyncio
async def test_service_loads_persisted_snapshots_and_plans_without_fabricating_analysis() -> None:
    source = _snapshot("source", 128)
    target = _snapshot("target", 128)
    store = MagicMock()
    store.get_analysis_snapshot = AsyncMock(
        side_effect=[
            {
                "source_hash": source.source_hash,
                "schema_version": source.schema_version,
                "analyzer_versions": {},
                "model_versions": {},
                "payload": {"tempo_hypotheses": [{"bpm": 128, "confidence": 1.0, "source": "audio"}]},
            },
            {
                "source_hash": target.source_hash,
                "schema_version": target.schema_version,
                "analyzer_versions": {},
                "model_versions": {},
                "payload": {"tempo_hypotheses": [{"bpm": 128, "confidence": 1.0, "source": "audio"}]},
            },
        ]
    )
    features = (MagicMock(bpm=128), MagicMock(bpm=128))
    catalog = MagicMock()
    catalog.features = AsyncMock(return_value={1: features[0], 2: features[1]})
    planner = MagicMock()
    planner.execute_async = AsyncMock(return_value=MagicMock(value="planned", comparison=None))
    candidate_generator = MagicMock()
    candidate_generator.generate = MagicMock(return_value=("candidate",))

    service = PlanTransitionService(store, catalog, candidate_generator, planner)
    result = await service.execute(
        PlanTransitionRequest(
            source_track_id=1,
            target_track_id=2,
            source_analysis_identity=source.identity_hash,
            target_analysis_identity=target.identity_hash,
            bars=8,
            policy=SelectionPolicy.BEST,
        )
    )

    assert result.value == "planned"
    planner.execute_async.assert_awaited_once()
    candidate_generator.generate.assert_called_once()
    store.get_analysis_snapshot.assert_awaited()


@pytest.mark.asyncio
async def test_service_fails_when_persisted_analysis_is_missing() -> None:
    store = MagicMock()
    store.get_analysis_snapshot = AsyncMock(return_value=None)
    service = PlanTransitionService(store, MagicMock(), MagicMock(), MagicMock())

    with pytest.raises(ValueError, match="analysis snapshot not found"):
        await service.execute(
            PlanTransitionRequest(1, 2, "missing", "missing", 8, SelectionPolicy.BEST)
        )

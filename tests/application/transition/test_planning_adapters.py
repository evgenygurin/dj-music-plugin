from unittest.mock import MagicMock

import pytest

from app.application.transition.adapters import (
    LegacyTransitionPlannerAdapter,
    UniversalTransitionPlannerAdapter,
)
from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.evaluation import FeatureSet
from app.domain.mixing.selection import SelectionPolicy
from app.shared.features import TrackFeatures


def _candidate(target: str, bpm: float = 128.0) -> CandidateTransition:
    source = AnalysisSnapshot("source", "1", tempo_hypotheses=(TempoHypothesis(128, 1),))
    target_snapshot = AnalysisSnapshot(target, "1", tempo_hypotheses=(TempoHypothesis(bpm, 1),))
    return CandidateTransition.from_values(source, target_snapshot, 128, bpm, 30)


def test_legacy_adapter_selects_from_real_scorer() -> None:
    scorer = MagicMock()
    first = MagicMock(overall=0.4, hard_reject=False)
    second = MagicMock(overall=0.9, hard_reject=False)
    scorer.score.side_effect = [first, second]
    adapter = LegacyTransitionPlannerAdapter(scorer)
    features = (TrackFeatures(bpm=128), TrackFeatures(bpm=128))

    result = adapter.plan((_candidate("a"), _candidate("b")), features, SelectionPolicy.BEST)

    assert result.selected.target_id == _candidate("b").target_hash
    assert scorer.score.call_count == 2


@pytest.mark.parametrize("mode", [SelectionPolicy.BEST, SelectionPolicy.MOST_HARMONIC])
def test_universal_adapter_maps_track_features(mode: SelectionPolicy) -> None:
    planner = MagicMock()
    expected = object()
    planner.plan.return_value = expected
    adapter = UniversalTransitionPlannerAdapter(planner)

    result = adapter.plan(
        (_candidate("a"),), (TrackFeatures(bpm=128), TrackFeatures(bpm=128)), mode
    )

    assert result is expected
    planner.plan.assert_called_once()
    mapped = planner.plan.call_args.args[1]
    assert isinstance(mapped[0], FeatureSet)
    assert isinstance(mapped[1], FeatureSet)

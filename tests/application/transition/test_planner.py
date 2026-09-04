from app.application.transition.planner import TransitionPlanner
from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.evaluation import FeatureSet
from app.domain.mixing.selection import SelectionPolicy


def test_planner_selects_only_technically_acceptable_candidate() -> None:
    source = _snapshot("a", 128)
    rejected_target = _snapshot("b", 128.2)
    accepted_target = _snapshot("c", 128)
    candidates = (
        CandidateTransition.from_values(source, rejected_target, 128, 128.2, 400),
        CandidateTransition.from_values(source, accepted_target, 128, 128, 30),
    )
    decision = TransitionPlanner().plan(
        candidates, (FeatureSet(), FeatureSet()), SelectionPolicy.BEST
    )
    assert decision.selected.target_id == accepted_target.identity_hash
    assert decision.rejected


def _snapshot(name: str, bpm: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(name, "1", tempo_hypotheses=(TempoHypothesis(bpm, 1),))

from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.constraints import HardConstraintValidator


def candidate(a: float, b: float, seconds: float = 300) -> CandidateTransition:
    return CandidateTransition.from_values(
        AnalysisSnapshot("a", "1", tempo_hypotheses=(TempoHypothesis(a, 1),)),
        AnalysisSnapshot("b", "1", tempo_hypotheses=(TempoHypothesis(b, 1),)),
        a,
        b,
        seconds,
    )


def test_long_transition_rejects_128_vs_128_2_when_configured_drift_is_exceeded() -> None:
    result = HardConstraintValidator(max_drift_beats=0.4).validate(candidate(128, 128.2))
    assert not result.accepted
    assert result.reason == "tempo_drift"
    assert result.drift_beats > 0.4


def test_small_tempo_difference_can_pass() -> None:
    result = HardConstraintValidator(max_drift_beats=2).validate(candidate(128, 128.01))
    assert result.accepted

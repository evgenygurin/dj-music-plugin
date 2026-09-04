from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.alignment import AlignmentRequest
from app.domain.mixing.candidate import CandidateGenerator


def snapshot(name: str, bpm: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(name, "1", tempo_hypotheses=(TempoHypothesis(bpm, 1.0),))


def test_generator_emits_half_one_and_double_tempo_hypotheses_when_valid() -> None:
    source, target = snapshot("a", 128), snapshot("b", 64)
    candidates = CandidateGenerator().generate(source, target, AlignmentRequest(8))
    assert {round(c.target_tempo.bpm, 3) for c in candidates} >= {32.0, 64.0, 128.0}


def test_candidate_id_is_deterministic() -> None:
    request = AlignmentRequest(16)
    left = CandidateGenerator().generate(snapshot("a", 128), snapshot("b", 128), request)
    right = CandidateGenerator().generate(snapshot("a", 128), snapshot("b", 128), request)
    assert [c.candidate_id for c in left] == [c.candidate_id for c in right]

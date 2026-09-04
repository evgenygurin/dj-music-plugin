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


def test_generator_carries_beat_and_phrase_alignment_metadata() -> None:
    from app.domain.analysis.beatgrid import BeatGrid
    from app.domain.analysis.phrase import Phrase

    source = AnalysisSnapshot(
        "a",
        "1",
        tempo_hypotheses=(TempoHypothesis(120, 1.0),),
        beatgrid=BeatGrid(120, (), phase_s=0.0),
        phrases=(Phrase(4.0, 8.0, 8, 12),),
    )
    target = AnalysisSnapshot(
        "b",
        "1",
        tempo_hypotheses=(TempoHypothesis(120, 1.0),),
        beatgrid=BeatGrid(120, (), phase_s=0.02),
        phrases=(Phrase(6.0, 10.0, 12, 16),),
    )

    candidate = next(
        c
        for c in CandidateGenerator().generate(source, target, AlignmentRequest(8))
        if c.source_variant == "1x" and c.target_variant == "1x"
    )

    assert candidate.phase_offset_s == 0.02
    assert candidate.downbeat_offset_beats == 0.04
    assert candidate.phrase_offset_bars == 4

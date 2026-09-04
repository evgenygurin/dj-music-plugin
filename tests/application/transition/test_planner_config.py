from app.application.transition.planner import TransitionPlanner
from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.configuration.profile import TransitionProfile
from app.domain.configuration.resolver import ConfigResolver
from app.domain.configuration.schema import ParameterClass, ParameterDefinition, TransitionSchema
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.evaluation import FeatureSet
from app.domain.mixing.selection import SelectionPolicy


def _snapshot(name: str, bpm: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(name, "1", tempo_hypotheses=(TempoHypothesis(bpm, 1),))


def _schema() -> TransitionSchema:
    return TransitionSchema(
        (
            ParameterDefinition(
                "tempo.max_ratio",
                "ratio",
                1.0,
                2.0,
                1.06,
                ParameterClass.HARD,
            ),
        )
    )


def test_planner_resolves_config_and_records_hash() -> None:
    source = _snapshot("a", 128)
    target = _snapshot("b", 128)
    candidate = CandidateTransition.from_values(source, target, 128, 128, 30)
    resolver = ConfigResolver(_schema())
    config = resolver.resolve(genre_profile=TransitionProfile("techno", {"tempo.max_ratio": 1.04}))

    decision = TransitionPlanner(config_resolver=resolver, resolved_config=config).plan(
        (candidate,),
        (FeatureSet(), FeatureSet()),
        SelectionPolicy.BEST,
    )

    assert decision.selected.config_identity == config.config_hash


def test_planner_uses_candidate_specific_alignment_metadata() -> None:
    source = _snapshot("a", 128)
    target = _snapshot("b", 128)
    aligned = CandidateTransition.from_values(
        source,
        target,
        128,
        128,
        30,
        downbeat_offset_beats=0.0,
        phrase_offset_bars=0,
    )
    misaligned = CandidateTransition.from_values(
        source,
        target,
        128,
        128,
        30,
        downbeat_offset_beats=1.0,
        phrase_offset_bars=2,
    )

    decision = TransitionPlanner().plan(
        (misaligned, aligned),
        (FeatureSet(), FeatureSet()),
        SelectionPolicy.BEST,
    )

    assert decision.selected.source_analysis_identity == source.identity_hash
    assert decision.selected.diagnostics
    assert any("alignment" in item for item in decision.selected.diagnostics)

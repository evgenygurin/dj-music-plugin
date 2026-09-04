from app.application.engine.mode import EngineMode, EngineSelection
from app.application.transition.adapters import (
    LegacyTransitionPlannerAdapter,
    UniversalTransitionPlannerAdapter,
)
from app.application.transition.planner import TransitionPlanner
from app.application.transition.planning import PlanTransition
from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis
from app.domain.mixing.candidate import CandidateTransition
from app.domain.mixing.selection import SelectionPolicy
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures


def _request() -> tuple[tuple[CandidateTransition, ...], tuple[TrackFeatures, TrackFeatures]]:
    source = AnalysisSnapshot("source", "1", tempo_hypotheses=(TempoHypothesis(128, 1),))
    target = AnalysisSnapshot("target", "1", tempo_hypotheses=(TempoHypothesis(128, 1),))
    candidate = CandidateTransition.from_values(source, target, 128, 128, 30)
    return (candidate,), (TrackFeatures(bpm=128), TrackFeatures(bpm=128))


def _use_case(mode: EngineMode) -> PlanTransition:
    return PlanTransition(
        EngineSelection(mode, "legacy"),
        legacy_planner=LegacyTransitionPlannerAdapter(TransitionScorer()),
        new_planner=UniversalTransitionPlannerAdapter(TransitionPlanner()),
    )


def test_new_mode_uses_real_universal_planner() -> None:
    candidates, features = _request()
    result = _use_case(EngineMode.NEW).execute(candidates, features, SelectionPolicy.BEST)
    assert result.value.selected.source_id == candidates[0].source_hash
    assert result.value.score >= 0.0


def test_legacy_mode_uses_real_legacy_scorer() -> None:
    candidates, features = _request()
    result = _use_case(EngineMode.LEGACY).execute(candidates, features, SelectionPolicy.BEST)
    assert result.value.selected.target_id == candidates[0].target_hash
    assert result.comparison is None


def test_shadow_mode_returns_universal_decision_and_compares_real_paths() -> None:
    candidates, features = _request()
    result = _use_case(EngineMode.SHADOW).execute(candidates, features, SelectionPolicy.BEST)

    assert result.value.selected.source_id == candidates[0].source_hash
    assert result.comparison is not None
    assert isinstance(result.comparison.recipe_parity, bool)
    assert isinstance(result.comparison.score_delta, float)
    assert isinstance(result.comparison.technical_margin_delta, float)


async def test_shadow_planning_persists_comparison_only_in_shadow_mode() -> None:
    from app.application.transition.shadow import ShadowComparisonRecord

    class Store:
        def __init__(self) -> None:
            self.records: list[ShadowComparisonRecord] = []

        async def save_shadow_comparison(
            self, identity: str, execution_identity: str, comparison: dict
        ) -> None:
            self.records.append((identity, execution_identity, comparison))

    candidates, features = _request()
    store = Store()
    use_case = PlanTransition(
        EngineSelection(EngineMode.SHADOW, "legacy"),
        legacy_planner=LegacyTransitionPlannerAdapter(TransitionScorer()),
        new_planner=UniversalTransitionPlannerAdapter(TransitionPlanner()),
        shadow_store=store,
    )

    result = await use_case.execute_async(candidates, features, SelectionPolicy.BEST)

    assert result.comparison is not None
    assert len(store.records) == 1
    assert store.records[0][1] == result.value.selected.execution_identity

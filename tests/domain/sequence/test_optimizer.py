from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.sequence.graph import CandidateGraph, TransitionEdge
from app.domain.sequence.optimizer import BeamSearchOptimizer
from app.domain.sequence.state import SetState


def plan(source: str, target: str) -> TransitionPlan:
    return TransitionPlan.create(
        source, target, 8, 128, RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
    )


def test_beam_search_finds_best_bounded_path() -> None:
    graph = CandidateGraph(
        (
            TransitionEdge("a", "b", plan("a", "b"), 0.8),
            TransitionEdge("a", "c", plan("a", "c"), 0.6),
            TransitionEdge("b", "d", plan("b", "d"), 0.9),
            TransitionEdge("c", "d", plan("c", "d"), 0.1),
        )
    )
    result = BeamSearchOptimizer(beam_width=2).optimize(graph, SetState(("a",)), "d")
    assert result.tracks == ("a", "b", "d")


def test_graph_reports_missing_edges() -> None:
    graph = CandidateGraph(())
    assert graph.outgoing("a") == ()
    assert graph.has_edge("a", "b") is False

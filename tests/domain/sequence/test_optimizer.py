from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.sequence.constraints import SetConstraints
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


def test_beam_search_applies_target_bpm_constraint_from_transition_plan() -> None:
    graph = CandidateGraph(
        (
            TransitionEdge("a", "b", plan("a", "b"), 1.0),
            TransitionEdge("a", "c", TransitionPlan.create(
                "a", "c", 8, 100, RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
            ), 0.9),
        )
    )
    constraints = SetConstraints(min_bpm=120)
    result = BeamSearchOptimizer(beam_width=2).optimize(
        graph, SetState(("a",)), "b", constraints=constraints
    )
    assert result.tracks == ("a", "b")


def test_beam_search_passes_edge_energy_artist_and_recipe_metadata_to_constraints() -> None:
    graph = CandidateGraph(
        (
            TransitionEdge(
                "a", "b", plan("a", "b"), 1.0,
                target_energy=0.8, target_artist="same", target_recipe="EQ_BLEND",
            ),
            TransitionEdge(
                "a", "c", plan("a", "c"), 0.9,
                target_energy=0.8, target_artist="other", target_recipe="FADE",
            ),
        )
    )
    constraints = SetConstraints(
        min_energy=0.5,
        max_consecutive_same_artist=1,
        max_consecutive_same_recipe=1,
    )
    initial = SetState(("a",), artists=("same",), recipes=("EQ_BLEND",))
    result = BeamSearchOptimizer(beam_width=2).optimize(
        graph, initial, "c", constraints=constraints
    )
    assert result.tracks == ("a", "c")

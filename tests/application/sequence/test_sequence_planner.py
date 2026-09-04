from app.application.sequence.planner import SequencePlanner
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.sequence.graph import CandidateGraph, TransitionEdge


def test_sequence_application_service_delegates_to_bounded_optimizer() -> None:
    plan = TransitionPlan.create("a", "b", 8, 128, RecipePlanner().plan(RecipeKind.FADE, 8))
    graph = CandidateGraph((TransitionEdge("a", "b", plan, 1.0),))
    result = SequencePlanner(beam_width=1).plan(graph, "a", "b")
    assert result.tracks == ("a", "b")

from app.application.transition.cache import InMemoryTransitionCache
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_cache_round_trip_is_keyed_by_execution_identity() -> None:
    plan = TransitionPlan.create("a", "b", 8, 128, RecipePlanner().plan(RecipeKind.FADE, 8))
    cache = InMemoryTransitionCache()
    cache.put(plan)
    assert cache.get(plan.execution_identity) == plan
    assert cache.get("missing") is None

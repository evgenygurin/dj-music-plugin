from unittest.mock import MagicMock

import pytest

from app.application.transition.render_rollout import RenderTransition
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.render.models import RenderPlan


def _transition() -> TransitionPlan:
    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
    return TransitionPlan.create("a", "b", 8, 128.0, recipe)


def test_legacy_renderer_receives_adapted_render_plan() -> None:
    legacy = MagicMock(return_value="adapted")
    adapter = MagicMock()
    adapter.adapt.return_value = "adapted"
    render_plan = MagicMock(spec=RenderPlan)
    use_case = RenderTransition("legacy", legacy_renderer=legacy, adapter=adapter)

    result = use_case.execute(_transition(), render_plan)

    adapter.adapt.assert_called_once_with(_transition(), render_plan)
    legacy.assert_called_once_with("adapted")
    assert result == "adapted"


def test_new_renderer_receives_immutable_transition_plan_without_legacy() -> None:
    new = MagicMock(return_value="new-output")
    legacy = MagicMock()
    use_case = RenderTransition("new", legacy_renderer=legacy, new_renderer=new)

    result = use_case.execute(_transition(), MagicMock(spec=RenderPlan))

    new.assert_called_once_with(_transition())
    legacy.assert_not_called()
    assert result == "new-output"


def test_new_renderer_is_required_for_new_mode() -> None:
    with pytest.raises(RuntimeError, match="new renderer is required"):
        RenderTransition("new", legacy_renderer=MagicMock()).execute(
            _transition(), MagicMock(spec=RenderPlan)
        )

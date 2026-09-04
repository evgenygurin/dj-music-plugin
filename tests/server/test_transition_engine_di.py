from unittest.mock import MagicMock

import pytest

from app.application.transition.adapters import (
    LegacyTransitionPlannerAdapter,
    UniversalTransitionPlannerAdapter,
)
from app.server import di

from .conftest import make_di_ctx


@pytest.mark.asyncio
async def test_legacy_transition_planner_factory_uses_lifespan_scorer() -> None:
    scorer = MagicMock()
    ctx = make_di_ctx(lifespan={"transition_scorer": scorer})

    planner = await di.get_legacy_transition_planner(ctx)

    assert isinstance(planner, LegacyTransitionPlannerAdapter)


@pytest.mark.asyncio
async def test_universal_transition_planner_factory_builds_universal_planner() -> None:
    ctx = make_di_ctx()

    planner = await di.get_universal_transition_planner(ctx)

    assert isinstance(planner, UniversalTransitionPlannerAdapter)
    assert planner._planner.__class__.__name__ == "TransitionPlanner"


@pytest.mark.asyncio
async def test_plan_transition_factory_wires_real_rollout_components() -> None:
    from app.application.transition.planning import PlanTransition

    ctx = make_di_ctx(lifespan={"transition_scorer": MagicMock()})
    planner = await di.get_plan_transition(ctx)

    assert isinstance(planner, PlanTransition)
    assert planner._legacy.__class__.__name__ == "LegacyTransitionPlannerAdapter"
    assert planner._new.__class__.__name__ == "UniversalTransitionPlannerAdapter"


@pytest.mark.asyncio
async def test_plan_transition_factory_wires_shadow_store_for_shadow_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.engine.mode import EngineMode, EngineSelection
    from app.repositories.unit_of_work import UnitOfWork

    ctx = make_di_ctx(lifespan={"transition_scorer": MagicMock()})
    uow = MagicMock(spec=UnitOfWork)
    uow.session = MagicMock()
    ctx.fastmcp_context.state["uow"] = uow

    async def shadow_selection(_ctx: object) -> EngineSelection:
        return EngineSelection(EngineMode.SHADOW, "legacy")

    monkeypatch.setattr(di, "get_engine_selection", shadow_selection)

    planner = await di.get_plan_transition(ctx)

    assert planner._shadow_store.__class__.__name__ == "EngineContractStore"

"""Feature-flagged transition render execution boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.application.transition.render_adapter import TransitionRenderAdapter
from app.domain.mixing.plan import TransitionPlan
from app.domain.render.models import RenderPlan
from app.domain.render.plan_validator import RenderPlanValidator


class RenderTransition:
    """Execute an immutable transition plan through the selected renderer."""

    def __init__(
        self,
        renderer: str,
        *,
        legacy_renderer: Callable[[RenderPlan], Any],
        new_renderer: Callable[[TransitionPlan], Any] | None = None,
        adapter: TransitionRenderAdapter | None = None,
    ) -> None:
        if renderer not in {"legacy", "new"}:
            raise ValueError(f"unsupported renderer: {renderer}")
        self._renderer = renderer
        self._legacy = legacy_renderer
        self._new = new_renderer
        self._adapter = adapter if adapter is not None else TransitionRenderAdapter()
        self._validator = RenderPlanValidator()

    def execute(self, transition: TransitionPlan, render_plan: RenderPlan) -> Any:
        validation = self._validator.validate(transition)
        if not validation.accepted:
            raise ValueError(f"invalid transition plan: {validation.reason}")
        if self._renderer == "legacy":
            return self._legacy(self._adapter.adapt(transition, render_plan))
        if self._new is None:
            raise RuntimeError("new renderer is required for new mode")
        return self._new(transition)

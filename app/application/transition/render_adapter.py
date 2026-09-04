"""Adapt an already assembled legacy render plan for a selected transition.

This boundary deliberately translates execution data; it never invokes a
planner, scores candidates, or changes the selected musical decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.domain.mixing.plan import TransitionPlan
from app.domain.render.models import RenderPlan


class TransitionRenderAdapter:
    """Project a selected :class:`TransitionPlan` onto render geometry."""

    def __init__(self, replanner: Callable[..., Any] | None = None) -> None:
        # Kept only as a guard/injection point for migration tests. It must
        # never be called by ``adapt``.
        self._replanner = replanner

    def adapt(self, transition: TransitionPlan, render_plan: RenderPlan) -> RenderPlan:
        """Return render data driven by ``transition`` without re-planning."""
        track_ids = {str(segment.track_id) for segment in self._segments(render_plan)}
        if str(transition.source_id) not in track_ids:
            raise ValueError(f"source track {transition.source_id} is absent from render plan")
        if str(transition.target_id) not in track_ids:
            raise ValueError(f"target track {transition.target_id} is absent from render plan")
        if transition.duration_bars <= 0:
            raise ValueError("transition duration must be positive")
        if transition.effective_bpm <= 0:
            raise ValueError("effective BPM must be positive")
        if transition.recipe.bars != transition.duration_bars:
            raise ValueError("transition recipe bars must match transition duration")

        # The legacy geometry, DSP constants and file paths remain untouched.
        # Only the selected plan's effective BPM is projected into execution.
        return replace(render_plan, target_bpm=transition.effective_bpm)

    @staticmethod
    def _segments(render_plan: RenderPlan) -> list[Any]:
        return list(render_plan.stem_segments or render_plan.segments)

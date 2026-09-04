from dataclasses import replace

import pytest

from app.application.transition.render_adapter import TransitionRenderAdapter
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, TransitionRecipe
from app.domain.render.models import RenderMode, RenderPlan, TrackSegment


def _transition_plan() -> TransitionPlan:
    return TransitionPlan.create(
        "1",
        "2",
        8,
        126.0,
        TransitionRecipe(RecipeKind.FADE, 8, ("curve", "linear")),
    )


def _render_plan() -> RenderPlan:
    return RenderPlan(
        target_bpm=120.0,
        xsplit_low_hz=120,
        xsplit_high_hz=2500,
        eq_phase_1_ratio=0.4,
        eq_phase_2_ratio=0.7,
        low_swap_beats=1.0,
        outro_fade_bars=8,
        limiter_ceiling=-1.0,
        mode=RenderMode.CLASSIC,
        segments=[
            TrackSegment(0, 1, "/a.mp3", 1.0, 0.0, 0.0, 8, 1.0, 1.0, 32.0, 0.0),
            TrackSegment(1, 2, "/b.mp3", 1.0, 0.0, 0.0, 8, 1.0, 1.0, 32.0, 28.0),
        ],
    )


def test_adapter_projects_selected_transition_plan_without_replanning():
    planner_calls = 0

    def forbidden_planner(*_args, **_kwargs):
        nonlocal planner_calls
        planner_calls += 1
        raise AssertionError("RenderPlanner must not run during execution")

    adapter = TransitionRenderAdapter(replanner=forbidden_planner)
    adapted = adapter.adapt(_transition_plan(), _render_plan())

    assert planner_calls == 0
    assert adapted.target_bpm == 126.0
    assert adapted.segments == _render_plan().segments


def test_adapter_rejects_template_with_wrong_transition_tracks():
    template = _render_plan()
    bad = replace(
        template, segments=[replace(template.segments[0], track_id=99), template.segments[1]]
    )

    with pytest.raises(ValueError, match="source track"):
        TransitionRenderAdapter().adapt(_transition_plan(), bad)


def test_adapter_preserves_render_dsp_settings_and_recipe_identity():
    template = _render_plan()
    adapted = TransitionRenderAdapter().adapt(_transition_plan(), template)

    assert adapted.xsplit_low_hz == template.xsplit_low_hz
    assert adapted.limiter_ceiling == template.limiter_ceiling
    assert adapted.target_bpm == 126.0

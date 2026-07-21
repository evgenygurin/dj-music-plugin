from types import SimpleNamespace

from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan, BarPlanner
from app.domain.render.models import BeatgridEntry


def _inputs(n: int, *, duration_ms: int | None = None) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            track_id=i,
            mood="hypnotic_techno",
            bpm=130.0,
            duration_ms=duration_ms,
            tempo_ratio=lambda t: t / 130.0,
        )
        for i in range(n)
    ]


def _grid(n: int) -> dict[int, BeatgridEntry]:
    return {
        i: BeatgridEntry(
            track_id=i,
            trim_start_s=0.5,
            refined_trim_s=0.5,
            gain_db=0.0,
            phase_ms=0.0,
        )
        for i in range(n)
    }


def test_bar_plan_holds_transition_and_body() -> None:
    plan = BarPlan(transition_bars=(16, 32), body_bars=[24, 32, 24])

    assert plan.transition_for(0) == 16
    assert plan.transition_for(1) == 32
    assert plan.body_for(0) == 24
    assert plan.body_for(2) == 24
    assert len(plan) == 3


def test_bar_plan_iter_unpacks_to_tuple_for_backcompat() -> None:
    plan = BarPlan(transition_bars=(16,), body_bars=[24, 24])

    per_t, per_b = plan

    assert per_t == (16,)
    assert per_b == [24, 24]


def test_compute_single_pass_returns_bar_plan() -> None:
    plan = BarPlanner(RenderSettings()).compute(_inputs(1), _grid(1))

    assert isinstance(plan, BarPlan)
    assert plan.transition_bars == ()
    assert plan.body_bars == [64]


def test_compute_transition_bars_per_pair() -> None:
    plan = BarPlanner(RenderSettings()).compute(_inputs(3), _grid(3))

    assert len(plan.transition_bars) == 2


def test_compute_overrides_apply_to_all() -> None:
    plan = BarPlanner(RenderSettings()).compute(
        _inputs(3), _grid(3), transition_bars_override=8, body_bars_override=16
    )

    assert plan.transition_bars == (8, 8)
    assert plan.body_bars == [16, 16, 16]


def test_compute_accepts_brief_override_aliases() -> None:
    plan = BarPlanner(RenderSettings()).compute(
        _inputs(3), _grid(3), transition_override=8, body_override=16
    )

    assert plan.transition_bars == (8, 8)
    assert plan.body_bars == [16, 16, 16]

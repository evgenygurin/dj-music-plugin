import json

from app.domain.render.models import RenderMode, RenderPlan
from app.handlers._orchestrator.render_executor import RenderExecutor


def _plan(phrase_align_count: int) -> RenderPlan:
    return RenderPlan(
        target_bpm=130.0,
        xsplit_low_hz=260,
        xsplit_high_hz=4200,
        eq_phase_1_ratio=0.4,
        eq_phase_2_ratio=0.7,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=-1.0,
        mode=RenderMode.CLASSIC,
        phrase_align_count=phrase_align_count,
    )


def test_persist_plan_reports_phrase_align_true(tmp_path):
    executor = RenderExecutor()
    executor._persist_plan(_plan(2), object(), tmp_path)
    payload = json.loads((tmp_path / "render_plan.json").read_text())
    assert payload["phrase_align"] is True
    assert payload["phrase_align_count"] == 2


def test_persist_plan_reports_phrase_align_false(tmp_path):
    executor = RenderExecutor()
    executor._persist_plan(_plan(0), object(), tmp_path)
    payload = json.loads((tmp_path / "render_plan.json").read_text())
    assert payload["phrase_align"] is False
    assert payload["phrase_align_count"] == 0

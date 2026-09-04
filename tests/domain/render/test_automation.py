from app.domain.render.automation import AutomationCurve


def test_automation_curve_clamps_to_safety_bounds() -> None:
    curve = AutomationCurve("gain_db", 0, 10, 0, 1, minimum=-1, maximum=1)
    assert curve.value_at(5) == 0.5
    assert curve.value_at(20) == 1

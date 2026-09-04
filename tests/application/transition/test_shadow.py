from app.application.transition.shadow import ShadowComparison


def test_shadow_comparison_reports_matching_contracts() -> None:
    result = ShadowComparison.compare("a", "a", 0.9, 0.9)
    assert result.technical_parity
    assert result.score_delta == 0

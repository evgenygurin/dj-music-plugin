from app.application.transition.shadow import ShadowComparison


def test_shadow_comparison_reports_selection_recipe_rejections_and_dimension_deltas() -> None:
    result = ShadowComparison.compare(
        legacy_candidate="legacy",
        new_candidate="new",
        legacy_score=0.7,
        new_score=0.8,
        legacy_recipe="EQ_BLEND",
        new_recipe="FADE",
        legacy_rejected=("x",),
        new_rejected=("y",),
        legacy_accepted=True,
        new_accepted=False,
        legacy_technical_margin=0.2,
        new_technical_margin=0.3,
        legacy_dimensions={"harmony": 0.8, "energy": 0.6},
        new_dimensions={"harmony": 0.9, "energy": 0.5},
    )

    assert not result.technical_parity
    assert result.score_delta == 0.1
    assert not result.recipe_parity
    assert result.rejection_parity is False
    assert result.technical_margin_delta == 0.1
    assert result.dimension_deltas == (("energy", -0.1), ("harmony", 0.1))

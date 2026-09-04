from app.application.analysis.tiers import AnalysisTier, ResourceBudget


def test_tiers_have_explicit_escalation_order() -> None:
    assert AnalysisTier.BASIC < AnalysisTier.MIX_READY < AnalysisTier.DEEP


def test_resource_budget_rejects_oversubscription() -> None:
    budget = ResourceBudget(max_parallel_analysis=1, max_stem_jobs=1, max_deep_candidates=2)
    assert budget.allows_analysis(1)
    assert not budget.allows_analysis(2)
    assert budget.allows_deep_candidates(2)
    assert not budget.allows_deep_candidates(3)

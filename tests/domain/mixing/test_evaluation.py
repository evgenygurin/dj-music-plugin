from app.domain.mixing.evaluation import FeatureSet, MusicalEvaluator
from app.domain.mixing.scores import rank_scores


def test_spectral_group_avoids_double_counting() -> None:
    score = MusicalEvaluator().evaluate(
        FeatureSet(low_end=0.0, spectrum=0.0), FeatureSet(low_end=1.0, spectrum=1.0)
    )
    assert score.grouped_value("spectral") == 0.0
    assert score.spectral_contribution() == 0.0


def test_hard_rejected_score_never_ranks() -> None:
    good = MusicalEvaluator().evaluate(FeatureSet(), FeatureSet())
    rejected = good.__class__(good.dimensions, hard_rejected=True)
    assert rank_scores((("bad", rejected), ("good", good))) == ("good",)

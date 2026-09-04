from app.domain.mixing.evaluation import FeatureSet, MusicalEvaluator
from app.domain.mixing.scores import MusicalScore


def test_evaluator_returns_decomposable_dimensions() -> None:
    features = FeatureSet(
        harmony=0.9,
        energy=0.8,
        low_end=0.7,
        spectrum=0.6,
        groove=0.5,
        timbre=0.4,
        vocals=0.2,
        stems=0.3,
    )
    score = MusicalEvaluator().evaluate(features, features)
    assert isinstance(score, MusicalScore)
    assert {item.name for item in score.dimensions} == {
        "harmony",
        "energy",
        "low_end",
        "spectrum",
        "groove",
        "timbre",
        "vocals",
        "stems",
    }


def test_vocal_overlap_is_penalized() -> None:
    source = FeatureSet(vocals=1.0)
    target = FeatureSet(vocals=1.0)
    score = MusicalEvaluator().evaluate(source, target)
    assert score.dimension("vocals").value < 1.0

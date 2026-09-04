from app.domain.mixing.scores import DimensionScore, MusicalScore
from app.domain.mixing.selection import SelectionPolicy, select


def score(harmony: float, energy: float, groove: float, *, rejected: bool = False) -> MusicalScore:
    return MusicalScore(
        (DimensionScore("harmony", harmony), DimensionScore("energy", energy), DimensionScore("groove", groove)),
        hard_rejected=rejected,
    )


def test_policies_choose_expected_dimension() -> None:
    scores = (("a", score(.9, .2, .2)), ("b", score(.2, .9, .8)))
    assert select(scores, SelectionPolicy.MOST_HARMONIC).selected == "a"
    assert select(scores, SelectionPolicy.MOST_ENERGETIC).selected == "b"
    assert select(scores, SelectionPolicy.MOST_GROOVY).selected == "b"


def test_no_policy_can_select_hard_rejected_candidate() -> None:
    scores = (("bad", score(1, 1, 1, rejected=True)), ("good", score(.1, .1, .1)))
    for policy in SelectionPolicy:
        assert select(scores, policy).selected == "good"

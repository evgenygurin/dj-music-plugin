from app.domain.mixing.scores import DimensionScore, MusicalScore
from app.domain.mixing.selection import SelectionPolicy, select


def scores() -> tuple[tuple[str, MusicalScore], ...]:
    names = ("harmony", "energy", "groove", "timbre")
    safe = tuple(DimensionScore(name, 0.9 if name == "harmony" else 0.4) for name in names)
    creative = tuple(DimensionScore(name, 0.9 if name == "energy" else 0.4) for name in names)
    rejected = (DimensionScore("harmony", 1.0),)
    return (
        ("safe", MusicalScore(safe)),
        ("creative", MusicalScore(creative)),
        ("rejected", MusicalScore(rejected, True)),
    )


def test_selection_policies_never_select_hard_rejection() -> None:
    for policy in SelectionPolicy:
        assert select(scores(), policy).selected != "rejected"


def test_policy_can_prefer_harmony_or_energy() -> None:
    assert select(scores(), SelectionPolicy.MOST_HARMONIC).selected == "safe"
    assert select(scores(), SelectionPolicy.MOST_ENERGETIC).selected == "creative"

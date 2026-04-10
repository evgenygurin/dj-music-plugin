from app.core.constants import TechnoSubgenre
from app.transition.recipe import TransitionType
from app.transition.subgenre_rules import (
    SubgenrePairType,
    clamp_bars,
    classify_pair,
    preferred_type_for_pair,
)


def test_classify_ambient_pair():
    assert (
        classify_pair(TechnoSubgenre.DUB_TECHNO, TechnoSubgenre.AMBIENT_DUB)
        == SubgenrePairType.AMBIENT_PAIR
    )


def test_classify_hard_pair():
    assert (
        classify_pair(TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO)
        == SubgenrePairType.HARD_PAIR
    )


def test_classify_acid_pair():
    assert classify_pair(TechnoSubgenre.ACID, TechnoSubgenre.DRIVING) == SubgenrePairType.ACID_PAIR


def test_classify_melodic_pair():
    assert (
        classify_pair(TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE)
        == SubgenrePairType.MELODIC_PAIR
    )


def test_classify_hypnotic_pair():
    assert (
        classify_pair(TechnoSubgenre.MINIMAL, TechnoSubgenre.HYPNOTIC)
        == SubgenrePairType.HYPNOTIC_PAIR
    )


def test_classify_mixed_pair():
    assert (
        classify_pair(TechnoSubgenre.PEAK_TIME, TechnoSubgenre.DUB_TECHNO)
        == SubgenrePairType.MIXED_PAIR
    )


def test_classify_none_mood():
    assert classify_pair(None, TechnoSubgenre.DRIVING) == SubgenrePairType.MIXED_PAIR


def test_classify_string_mood():
    assert classify_pair("industrial", "hard_techno") == SubgenrePairType.HARD_PAIR


def test_clamp_bars_ambient():
    assert clamp_bars(16, SubgenrePairType.AMBIENT_PAIR) == 32


def test_clamp_bars_hard():
    assert clamp_bars(32, SubgenrePairType.HARD_PAIR) == 8


def test_clamp_bars_hypnotic():
    assert clamp_bars(8, SubgenrePairType.HYPNOTIC_PAIR) == 16


def test_clamp_bars_mixed_no_change():
    assert clamp_bars(16, SubgenrePairType.MIXED_PAIR) == 16


def test_preferred_type_ambient():
    tt = preferred_type_for_pair(SubgenrePairType.AMBIENT_PAIR)
    assert TransitionType.DISSOLVE in tt
    assert TransitionType.LONG_BLEND in tt


def test_preferred_type_hard():
    tt = preferred_type_for_pair(SubgenrePairType.HARD_PAIR)
    assert TransitionType.CUT in tt
    assert TransitionType.DROP_SWAP in tt

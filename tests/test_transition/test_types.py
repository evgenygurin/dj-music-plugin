from app.transition.types import Stem, StemAction, SubgenrePairType, TransitionIntent


def test_stem_values():
    assert Stem.DRUMS == "drums"
    assert Stem.BASS == "bass"
    assert Stem.HARMONICS == "harmonics"
    assert Stem.VOCALS == "vocals"


def test_stem_action_values():
    assert StemAction.FADE_IN == "fade_in"
    assert StemAction.FADE_OUT == "fade_out"
    assert StemAction.CUT == "cut"
    assert StemAction.SWAP == "swap"
    assert StemAction.MUTE == "mute"
    assert StemAction.SOLO == "solo"


def test_subgenre_pair_type_values():
    assert SubgenrePairType.AMBIENT_PAIR == "ambient_pair"
    assert SubgenrePairType.HARD_PAIR == "hard_pair"
    assert SubgenrePairType.ACID_PAIR == "acid_pair"
    assert SubgenrePairType.MELODIC_PAIR == "melodic_pair"
    assert SubgenrePairType.HYPNOTIC_PAIR == "hypnotic_pair"
    assert SubgenrePairType.MIXED_PAIR == "mixed_pair"


def test_transition_intent_ordering():
    assert TransitionIntent.MAINTAIN < TransitionIntent.RAMP_UP
    assert TransitionIntent.RAMP_UP < TransitionIntent.COOL_DOWN


def test_transition_intent_as_dict_key():
    from app.transition.intent import INTENT_WEIGHT_MODIFIERS

    for intent in TransitionIntent:
        assert intent in INTENT_WEIGHT_MODIFIERS, f"{intent} missing from INTENT_WEIGHT_MODIFIERS"
        weights = INTENT_WEIGHT_MODIFIERS[intent]
        assert "bpm" in weights

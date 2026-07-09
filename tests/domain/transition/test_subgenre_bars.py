from app.domain.transition.subgenre_rules import (
    SubgenrePairType,
    body_bars_for_pair,
    transition_bars_for_pair,
)


class TestTransitionBarsForPair:
    def test_hypnotic_gets_64_bars(self):
        assert transition_bars_for_pair(SubgenrePairType.HYPNOTIC_PAIR) == 64

    def test_hard_gets_24_bars(self):
        assert transition_bars_for_pair(SubgenrePairType.HARD_PAIR) == 24

    def test_mixed_gets_32_bars(self):
        assert transition_bars_for_pair(SubgenrePairType.MIXED_PAIR) == 32

    def test_unknown_falls_back_to_default(self, monkeypatch):
        import app.domain.transition.subgenre_rules as _mod

        monkeypatch.setattr(_mod, "_TRANSITION_BARS", {}, raising=True)
        assert (
            transition_bars_for_pair(SubgenrePairType.MIXED_PAIR) == _mod._DEFAULT_TRANSITION_BARS
        )


class TestBodyBarsForPair:
    def test_hypnotic_gets_96_bars(self):
        assert body_bars_for_pair(SubgenrePairType.HYPNOTIC_PAIR) == 96

    def test_hard_gets_48_bars(self):
        assert body_bars_for_pair(SubgenrePairType.HARD_PAIR) == 48

    def test_mixed_gets_64_bars(self):
        assert body_bars_for_pair(SubgenrePairType.MIXED_PAIR) == 64

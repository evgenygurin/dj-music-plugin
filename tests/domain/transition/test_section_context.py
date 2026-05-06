"""SectionContext data invariants.

Section-aware logic (drum-only relaxation, weight overrides) was the
job of the old 6-perceptual-component scorer. Post Neural Mix refactor
the picker (``app/domain/transition/picker.py``) consumes
``SectionContext`` directly when it lands; the scorer itself stays
context-free. These tests therefore exercise only the dataclass shape.
"""

from __future__ import annotations

from app.domain.transition import SectionContext
from app.shared.constants import SectionType


class TestSectionContext:
    def test_drum_only_pair_outro_to_intro(self) -> None:
        ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is True

    def test_drum_only_pair_sustain_to_ambient(self) -> None:
        ctx = SectionContext(from_section=SectionType.SUSTAIN, to_section=SectionType.AMBIENT)
        assert ctx.is_drum_only_pair is True

    def test_drop_to_intro_is_not_drum_only(self) -> None:
        ctx = SectionContext(from_section=SectionType.DROP, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is False

    def test_intro_to_drop_is_not_drum_only(self) -> None:
        ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.DROP)
        assert ctx.is_drum_only_pair is False

    def test_none_section_means_no_information(self) -> None:
        ctx = SectionContext(from_section=None, to_section=SectionType.INTRO)
        assert ctx.is_drum_only_pair is False
        ctx2 = SectionContext(from_section=SectionType.OUTRO, to_section=None)
        assert ctx2.is_drum_only_pair is False
        ctx3 = SectionContext(from_section=None, to_section=None)
        assert ctx3.is_drum_only_pair is False

    def test_frozen_dataclass(self) -> None:
        from dataclasses import FrozenInstanceError

        import pytest

        ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.OUTRO)
        with pytest.raises(FrozenInstanceError):
            ctx.from_section = SectionType.DROP  # type: ignore[misc]

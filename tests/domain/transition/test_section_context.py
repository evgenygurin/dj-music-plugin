"""SectionContext data invariants.

Section-aware logic (drum-only relaxation, weight overrides) was the
job of the old 6-perceptual-component scorer. Post Neural Mix refactor
the picker (``app/domain/transition/picker.py``) consumes
``SectionContext`` directly when it lands; the scorer itself stays
context-free. These tests therefore exercise only the dataclass shape.
"""

from __future__ import annotations

import pytest

from app.domain.transition import SectionContext
from app.domain.transition.section_context import SectionPairClass
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

        ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.OUTRO)
        with pytest.raises(FrozenInstanceError):
            ctx.from_section = SectionType.DROP  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Phase 1 Task A (v2 refactor) — SectionPairClass typology
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_section", "to_section", "expected"),
    [
        # DRUM_ONLY: both sides in INTRO/OUTRO/SUSTAIN/AMBIENT
        (SectionType.OUTRO, SectionType.INTRO, SectionPairClass.DRUM_ONLY),
        (SectionType.INTRO, SectionType.OUTRO, SectionPairClass.DRUM_ONLY),
        (SectionType.SUSTAIN, SectionType.SUSTAIN, SectionPairClass.DRUM_ONLY),
        (SectionType.AMBIENT, SectionType.OUTRO, SectionPairClass.DRUM_ONLY),
        # DROP_TO_DROP: both sides DROP/PEAK
        (SectionType.DROP, SectionType.DROP, SectionPairClass.DROP_TO_DROP),
        (SectionType.PEAK, SectionType.DROP, SectionPairClass.DROP_TO_DROP),
        (SectionType.DROP, SectionType.PEAK, SectionPairClass.DROP_TO_DROP),
        # BREAKDOWN_OUT: A=BREAKDOWN/VALLEY, B=INTRO/RISE
        (SectionType.BREAKDOWN, SectionType.INTRO, SectionPairClass.BREAKDOWN_OUT),
        (SectionType.VALLEY, SectionType.RISE, SectionPairClass.BREAKDOWN_OUT),
        # BUILDUP_IN: A=BUILD/RISE, B=DROP/PEAK
        (SectionType.BUILD, SectionType.DROP, SectionPairClass.BUILDUP_IN),
        (SectionType.RISE, SectionType.PEAK, SectionPairClass.BUILDUP_IN),
        # GENERIC: anything else
        (SectionType.BUILD, SectionType.BREAKDOWN, SectionPairClass.GENERIC),
        (SectionType.ATTACK, SectionType.OUTRO, SectionPairClass.GENERIC),
        (SectionType.PRE_DROP, SectionType.SUSTAIN, SectionPairClass.GENERIC),
    ],
)
def test_section_pair_class_classification(
    from_section: SectionType,
    to_section: SectionType,
    expected: SectionPairClass,
) -> None:
    ctx = SectionContext(from_section=from_section, to_section=to_section)
    assert ctx.section_pair_class == expected


def test_section_pair_class_none_from_section_returns_generic() -> None:
    ctx = SectionContext(from_section=None, to_section=SectionType.INTRO)
    assert ctx.section_pair_class == SectionPairClass.GENERIC


def test_section_pair_class_none_to_section_returns_generic() -> None:
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=None)
    assert ctx.section_pair_class == SectionPairClass.GENERIC


def test_section_pair_class_both_none_returns_generic() -> None:
    ctx = SectionContext(from_section=None, to_section=None)
    assert ctx.section_pair_class == SectionPairClass.GENERIC


def test_is_drum_only_pair_legacy_alias() -> None:
    """Legacy property still works and matches new classification."""
    drum_only = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    assert drum_only.is_drum_only_pair is True
    assert drum_only.section_pair_class == SectionPairClass.DRUM_ONLY

    not_drum_only = SectionContext(from_section=SectionType.DROP, to_section=SectionType.DROP)
    assert not_drum_only.is_drum_only_pair is False
    assert not_drum_only.section_pair_class == SectionPairClass.DROP_TO_DROP


def test_section_pair_class_is_cached() -> None:
    """cached_property: same SectionContext instance returns same enum object."""
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    first = ctx.section_pair_class
    second = ctx.section_pair_class
    assert first is second

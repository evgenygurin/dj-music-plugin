from __future__ import annotations

from app.domain.template.registry import get_template
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.pair_context import build_pair_context
from app.domain.transition.section_context import SectionPairClass
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures


def test_build_pair_context_uses_intent_and_preferred_sections() -> None:
    outgoing = TrackFeatures(
        integrated_lufs=-12.0,
        mix_out_section_type=int(SectionType.OUTRO),
        mix_out_section_id=41,
        mix_out_point_ms=240_000,
    )
    incoming = TrackFeatures(
        integrated_lufs=-10.5,
        mix_in_section_type=int(SectionType.INTRO),
        mix_in_section_id=52,
        mix_in_point_ms=0,
    )

    context = build_pair_context(
        outgoing,
        incoming,
        position=0.05,
        template=get_template("peak_hour_60"),
    )

    assert context.intent == TransitionIntent.RAMP_UP
    assert context.section_context is not None
    assert context.section_context.section_pair_class == SectionPairClass.DRUM_ONLY
    assert context.from_section_id == 41
    assert context.to_section_id == 52
    assert context.mix_out_point_ms == 240_000
    assert context.mix_in_point_ms == 0


def test_build_pair_context_falls_back_when_sections_are_missing() -> None:
    context = build_pair_context(
        TrackFeatures(integrated_lufs=-10.0),
        TrackFeatures(integrated_lufs=-11.0),
        position=0.95,
    )

    assert context.intent == TransitionIntent.COOL_DOWN
    assert context.section_context is None
    assert context.from_section_id is None
    assert context.to_section_id is None

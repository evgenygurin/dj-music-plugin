"""ConstructiveSlotBuilder regression tests."""

from __future__ import annotations

from app.domain.optimization import ConstructiveSlotBuilder
from app.domain.template.models import SetTemplateDefinition, TemplateSlot
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures


def _template() -> SetTemplateDefinition:
    return SetTemplateDefinition(
        name="test_slots",
        duration_min=30,
        description="test",
        slots=(
            TemplateSlot(0.0, "minimal", -10.0, 128.0, 132.0, 180_000, 0.2),
            TemplateSlot(0.5, "hypnotic", -8.0, 132.0, 136.0, 180_000, 0.2),
            TemplateSlot(1.0, "driving", -7.0, 136.0, 140.0, 180_000, 0.2),
        ),
    )


def test_constructive_selects_subset_that_matches_slots() -> None:
    feats = [
        TrackFeatures(bpm=130.0, integrated_lufs=-10.2, mood="minimal"),
        TrackFeatures(bpm=134.0, integrated_lufs=-8.0, mood="hypnotic"),
        TrackFeatures(bpm=138.0, integrated_lufs=-7.1, mood="driving"),
        TrackFeatures(bpm=145.0, integrated_lufs=-5.5, mood="raw"),
    ]
    ids = [1, 2, 3, 4]

    result = ConstructiveSlotBuilder(scorer=TransitionScorer()).optimize(
        feats,
        ids,
        template=_template(),
        moods={1: "minimal", 2: "hypnotic", 3: "driving", 4: "raw"},
    )

    assert result.track_order == [1, 2, 3]
    assert result.algorithm == "constructive"


def test_constructive_keeps_pinned_track_in_selected_subset() -> None:
    feats = [
        TrackFeatures(bpm=130.0, integrated_lufs=-10.2, mood="minimal"),
        TrackFeatures(bpm=134.0, integrated_lufs=-8.0, mood="hypnotic"),
        TrackFeatures(bpm=138.0, integrated_lufs=-7.1, mood="driving"),
        TrackFeatures(bpm=139.0, integrated_lufs=-7.0, mood="driving"),
    ]
    ids = [1, 2, 3, 4]

    result = ConstructiveSlotBuilder(scorer=TransitionScorer()).optimize(
        feats,
        ids,
        template=_template(),
        pinned={4},
        moods={1: "minimal", 2: "hypnotic", 3: "driving", 4: "driving"},
    )

    assert 4 in result.track_order

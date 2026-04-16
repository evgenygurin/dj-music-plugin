"""Tests for ArcCritique Pydantic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.arc_critique import ArcCritique


def test_arc_critique_validates_required_fields():
    critique = ArcCritique(
        crowd_journey="Opens hypnotic → industrial peak at 10 → release",
        weak_transitions=["Track 8→9: same energy, no shift"],
        strongest_moment="Track 10 — peak crowd response",
        recommendation="Swap track 5 earlier for contrast",
    )
    assert critique.crowd_journey.startswith("Opens")
    assert len(critique.weak_transitions) == 1
    assert "10" in critique.strongest_moment
    assert "Swap" in critique.recommendation


def test_arc_critique_accepts_empty_weak_transitions():
    critique = ArcCritique(
        crowd_journey="Smooth linear build",
        weak_transitions=[],
        strongest_moment="Track 7",
        recommendation="No changes needed",
    )
    assert critique.weak_transitions == []


def test_arc_critique_requires_all_fields():
    with pytest.raises(ValidationError):
        ArcCritique(
            crowd_journey="journey",
            weak_transitions=[],
            # missing strongest_moment and recommendation
        )


def test_arc_critique_model_dump():
    critique = ArcCritique(
        crowd_journey="Journey",
        weak_transitions=["t1→t2"],
        strongest_moment="t5",
        recommendation="Swap t3",
    )
    data = critique.model_dump()
    assert "crowd_journey" in data
    assert "weak_transitions" in data
    assert "strongest_moment" in data
    assert "recommendation" in data
    assert isinstance(data["weak_transitions"], list)

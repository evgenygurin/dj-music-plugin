"""Template registry tests (v2)."""

from __future__ import annotations

import pytest

from app.domain.template import TEMPLATES, get_template, list_template_names
from app.domain.template.models import SetTemplateDefinition, TemplateSlot


def test_has_eight_templates() -> None:
    assert len(list_template_names()) == 8


def test_expected_template_names() -> None:
    expected = {
        "warm_up_30",
        "classic_60",
        "peak_hour_60",
        "roller_90",
        "progressive_120",
        "wave_120",
        "closing_60",
        "full_library",
    }
    assert set(list_template_names()) == expected


def test_get_template_returns_definition() -> None:
    t = get_template("classic_60")
    assert isinstance(t, SetTemplateDefinition)
    assert t.name == "classic_60"
    assert t.duration_min == 60
    assert len(t.slots) > 0
    assert all(isinstance(s, TemplateSlot) for s in t.slots)


def test_get_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_template("does_not_exist")


def test_templates_mapping_exposes_all_names() -> None:
    assert set(TEMPLATES.keys()) == set(list_template_names())


def test_all_templates_have_valid_slots() -> None:
    for name, tpl in TEMPLATES.items():
        assert tpl.name == name
        for slot in tpl.slots:
            assert 0.0 <= slot.position <= 1.0
            assert slot.bpm_min <= slot.bpm_max
            assert 0.0 <= slot.flexibility <= 1.0

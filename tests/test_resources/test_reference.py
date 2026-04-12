"""Tests for reference resources (reference://camelot, reference://templates, reference://subgenres)."""

import json

import pytest

from dj_music.resources.reference import (
    camelot_reference,
    subgenres_reference,
    templates_reference,
)
from dj_music.core.constants import CAMELOT_KEYS, SetTemplate, TechnoSubgenre


@pytest.mark.asyncio
async def test_camelot_reference_structure():
    """Test Camelot reference returns all 24 keys."""
    result = await camelot_reference()
    data = json.loads(result)

    assert data["total_keys"] == 24
    assert len(data["keys"]) == 24
    assert "compatibility_rules" in data
    assert "distance_explanation" in data
    assert "wheel_structure" in data


@pytest.mark.asyncio
async def test_camelot_reference_keys():
    """Test Camelot reference key data correctness."""
    result = await camelot_reference()
    data = json.loads(result)

    # Verify all keys are present
    camelot_notations = {k["camelot"] for k in data["keys"]}
    expected_notations = {notation for notation, _ in CAMELOT_KEYS.values()}
    assert camelot_notations == expected_notations

    # Verify first key (1A)
    first_key = next(k for k in data["keys"] if k["camelot"] == "1A")
    assert first_key["code"] == 0
    assert "minor" in first_key["name"].lower()

    # Verify 8A (commonly used reference)
    key_8a = next(k for k in data["keys"] if k["camelot"] == "8A")
    assert "A minor" in key_8a["name"] or "A♭ minor" in key_8a["name"]


@pytest.mark.asyncio
async def test_camelot_reference_compatibility_rules():
    """Test Camelot reference includes compatibility rules."""
    result = await camelot_reference()
    data = json.loads(result)

    rules = data["compatibility_rules"]
    assert "perfect_match" in rules
    assert "energy_boost" in rules
    assert "adjacent_keys" in rules
    assert "hard_conflict" in rules

    # Check distance explanation is meaningful
    assert "0" in data["distance_explanation"]
    assert "5" in data["distance_explanation"]


@pytest.mark.asyncio
async def test_templates_reference_structure():
    """Test templates reference returns all 8 templates."""
    result = await templates_reference()
    data = json.loads(result)

    assert data["total_templates"] == 8
    assert len(data["templates"]) == 8
    assert "note" in data


@pytest.mark.asyncio
async def test_templates_reference_templates():
    """Test templates reference template data correctness."""
    result = await templates_reference()
    data = json.loads(result)

    # Verify all template names are present
    template_names = {t["name"] for t in data["templates"]}
    expected_names = {template.value for template in SetTemplate}
    assert template_names == expected_names

    # Verify warm_up_30 template
    warm_up = next(t for t in data["templates"] if t["name"] == "warm_up_30")
    assert warm_up["duration_min"] == 30
    assert "low" in warm_up["description"].lower()
    assert "opener" in warm_up["description"].lower()
    assert "energy_arc" in warm_up
    assert "typical_bpm_range" in warm_up
    assert "typical_moods" in warm_up
    assert "use_case" in warm_up

    # Verify peak_hour_60 template
    peak_hour = next(t for t in data["templates"] if t["name"] == "peak_hour_60")
    assert peak_hour["duration_min"] == 60
    assert "high" in peak_hour["description"].lower()
    assert "peak" in peak_hour["description"].lower()

    # Verify full_library template
    full_lib = next(t for t in data["templates"] if t["name"] == "full_library")
    assert full_lib["duration_min"] is None  # variable duration
    assert "all" in full_lib["use_case"].lower()


@pytest.mark.asyncio
async def test_subgenres_reference_structure():
    """Test subgenres reference returns all 15 subgenres."""
    result = await subgenres_reference()
    data = json.loads(result)

    assert data["total_subgenres"] == 15
    assert len(data["subgenres"]) == 15
    assert "energy_order" in data
    assert "classifier_note" in data


@pytest.mark.asyncio
async def test_subgenres_reference_order():
    """Test subgenres are ordered by energy intensity."""
    result = await subgenres_reference()
    data = json.loads(result)

    # Verify energy levels are sequential 1-15
    energy_levels = [s["energy_level"] for s in data["subgenres"]]
    assert energy_levels == list(range(1, 16))

    # Verify first (lowest energy) is ambient_dub
    assert data["subgenres"][0]["name"] == TechnoSubgenre.AMBIENT_DUB.value
    assert data["subgenres"][0]["energy_level"] == 1

    # Verify last (highest energy) is hard_techno
    assert data["subgenres"][-1]["name"] == TechnoSubgenre.HARD_TECHNO.value
    assert data["subgenres"][-1]["energy_level"] == 15


@pytest.mark.asyncio
async def test_subgenres_reference_details():
    """Test subgenre details are complete."""
    result = await subgenres_reference()
    data = json.loads(result)

    for subgenre in data["subgenres"]:
        assert "name" in subgenre
        assert "energy_level" in subgenre
        assert "description" in subgenre
        assert "typical_bpm_range" in subgenre
        assert "key_features" in subgenre
        assert isinstance(subgenre["key_features"], list)
        assert len(subgenre["key_features"]) >= 3  # At least 3 key features

    # Verify specific subgenre: peak_time
    peak_time = next(s for s in data["subgenres"] if s["name"] == TechnoSubgenre.PEAK_TIME.value)
    assert "high" in peak_time["description"].lower()
    assert "main floor" in peak_time["description"].lower()
    # BPM range should be string like "130-138"
    assert "-" in peak_time["typical_bpm_range"]


@pytest.mark.asyncio
async def test_subgenres_reference_classifier_note():
    """Test classifier note about catch-all categories."""
    result = await subgenres_reference()
    data = json.loads(result)

    # Should mention driving and hypnotic as catch-all
    note = data["classifier_note"]
    assert "driving" in note.lower()
    assert "hypnotic" in note.lower()
    assert "penalized" in note.lower() or "penalty" in note.lower()

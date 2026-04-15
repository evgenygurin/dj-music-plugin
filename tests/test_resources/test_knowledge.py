"""Tests for knowledge:// static resources."""

from __future__ import annotations

import json

import pytest

from app.controllers.resources.knowledge import (
    dancefloor_psychology,
    set_dynamics,
    subgenre_culture,
    vocabulary,
)
from app.core.constants import TechnoSubgenre


@pytest.mark.asyncio
async def test_vocabulary_covers_all_15_subgenres():
    result = await vocabulary()
    data = json.loads(result)
    # Every TechnoSubgenre.value must appear in at least one entry's subgenres list
    all_subgenres_in_vocab: set[str] = set()
    for entry in data["vocabulary"]:
        all_subgenres_in_vocab.update(entry["subgenres"])
    for sg in TechnoSubgenre:
        assert sg.value in all_subgenres_in_vocab, f"{sg.value} missing from vocabulary"


@pytest.mark.asyncio
async def test_vocabulary_has_required_fields():
    result = await vocabulary()
    data = json.loads(result)
    assert "vocabulary" in data
    assert "time_of_night" in data
    for entry in data["vocabulary"]:
        assert "term" in entry
        assert "subgenres" in entry
        assert "bpm_range" in entry
        assert "key_features" in entry


@pytest.mark.asyncio
async def test_subgenre_culture_covers_all_15():
    result = await subgenre_culture()
    data = json.loads(result)
    names = {entry["name"] for entry in data["subgenres"]}
    for sg in TechnoSubgenre:
        assert sg.value in names, f"{sg.value} missing from subgenre_culture"


@pytest.mark.asyncio
async def test_subgenre_culture_entry_fields():
    result = await subgenre_culture()
    data = json.loads(result)
    for entry in data["subgenres"]:
        assert "name" in entry
        assert "artists" in entry
        assert "set_position" in entry
        assert "flows_from" in entry
        assert "flows_into" in entry


@pytest.mark.asyncio
async def test_set_dynamics_has_required_sections():
    result = await set_dynamics()
    data = json.loads(result)
    assert "twenty_minute_rule" in data
    assert "energy_arc" in data
    assert "tension_release_cycles" in data
    assert "hard_rules" in data
    assert "phrase_awareness" in data


@pytest.mark.asyncio
async def test_dancefloor_psychology_has_required_sections():
    result = await dancefloor_psychology()
    data = json.loads(result)
    assert "crowd_states" in data
    assert "energy_recovery" in data
    assert "harmonic_mixing_perception" in data

"""Static reference resource tests.

These resources are pure static blobs — no DB, no DI, no Phase 5 wiring.
Tests exercise the underlying functions directly and validate JSON shape.
"""

from __future__ import annotations

import json

import pytest

# ── Task 14: Camelot wheel ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_camelot_shape_and_content() -> None:
    from app.v2.resources.reference.camelot import reference_camelot

    payload = json.loads(await reference_camelot())

    assert payload["total"] == 24
    assert payload["wheel_size"] == 12
    assert len(payload["keys"]) == 24

    # Spot check: key_code 14 = 8A / A minor
    k14 = next(k for k in payload["keys"] if k["code"] == 14)
    assert k14["notation"] == "8A"
    assert k14["name"] == "A minor"
    assert k14["position"] == 8
    assert k14["mode"] == "A"

    # Spot check: key_code 15 = 8B / C major
    k15 = next(k for k in payload["keys"] if k["code"] == 15)
    assert k15["notation"] == "8B"
    assert k15["mode"] == "B"

    # Every key has compat edges with self-distance omitted
    for k in payload["keys"]:
        for edge in k["compat_edges"]:
            assert edge["target_code"] != k["code"]
            assert 0 < edge["distance"] <= 2


@pytest.mark.asyncio
async def test_camelot_adjacent_is_distance_one() -> None:
    from app.v2.resources.reference.camelot import reference_camelot

    payload = json.loads(await reference_camelot())
    k_8a = next(k for k in payload["keys"] if k["notation"] == "8A")
    # 8A -> 8B (relative mode), 7A, 9A are distance 1
    dist_to_8b = next(e for e in k_8a["compat_edges"] if e["target_notation"] == "8B")
    assert dist_to_8b["distance"] == 1


# ── Task 15: Subgenre profiles ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_subgenres_shape_and_content() -> None:
    from app.v2.resources.reference.subgenres import reference_subgenres

    payload = json.loads(await reference_subgenres())
    assert payload["total"] == 15
    assert len(payload["profiles"]) == 15

    names = [p["subgenre"] for p in payload["profiles"]]
    # Low-to-high energy ordering
    assert names[0] == "ambient_dub"
    assert names[-1] == "hard_techno"

    # All 15 required subgenres present
    expected = {
        "ambient_dub",
        "dub_techno",
        "minimal",
        "detroit",
        "melodic_deep",
        "progressive",
        "hypnotic",
        "driving",
        "tribal",
        "breakbeat",
        "peak_time",
        "acid",
        "raw",
        "industrial",
        "hard_techno",
    }
    assert set(names) == expected

    # Catch-all penalty flag matches catch_all list
    catch_all = set(payload["catch_all"])
    assert catch_all == {"driving", "hypnotic"}
    for p in payload["profiles"]:
        expected_flag = p["subgenre"] in catch_all
        assert p["is_catch_all"] == expected_flag
        if expected_flag:
            assert p["catch_all_penalty"] > 0


@pytest.mark.asyncio
async def test_subgenres_feature_shape() -> None:
    from app.v2.resources.reference.subgenres import reference_subgenres

    payload = json.loads(await reference_subgenres())
    ambient = next(p for p in payload["profiles"] if p["subgenre"] == "ambient_dub")
    assert len(ambient["features"]) > 0
    for feat in ambient["features"]:
        assert set(feat.keys()) == {"name", "weight", "ideal", "tolerance"}
        assert feat["weight"] > 0

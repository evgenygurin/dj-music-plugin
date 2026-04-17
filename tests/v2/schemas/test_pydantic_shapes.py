"""Smoke test that every entity's 4 DTOs exist and validate."""

from __future__ import annotations

import pytest

ENTITIES = [
    "track",
    "playlist",
    "set",
    "audio_file",
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
    "scoring_profile",
]


@pytest.mark.parametrize("entity", ENTITIES)
def test_four_dtos_importable(entity: str) -> None:
    mod = __import__(f"app.v2.schemas.{entity}", fromlist=["*"])
    camel = "".join(p.capitalize() for p in entity.split("_"))
    for suffix in ("View", "Filter", "Create", "Update"):
        assert hasattr(mod, f"{camel}{suffix}"), f"{entity} missing {camel}{suffix}"

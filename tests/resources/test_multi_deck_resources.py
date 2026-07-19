from __future__ import annotations

import json

from app.resources.multi_deck import section_types, stem_features_catalog


def test_stem_features_catalog() -> None:
    result = json.loads(stem_features_catalog())
    assert result["entity"] == "stem_features"
    assert result["total_fields"] > 10
    assert any(f["name"] == "kick_prominence" for f in result["fields"])


def test_section_types() -> None:
    result = json.loads(section_types())
    assert len(result["types"]) == 12
    names = {t["name"] for t in result["types"]}
    assert "intro" in names
    assert "drop" in names

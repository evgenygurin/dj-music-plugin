import json
import pathlib


def test_constants_load():
    path = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "config" / "subgenre_constants.json"
    )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert "presets" in data
    assert len(data["presets"]) == 18
    assert "subgenre_profiles" in data
    assert len(data["subgenre_profiles"]) == 19  # 15 techno + 4 house profiles
    assert "audit_thresholds" in data
    assert "descriptions" in data
    assert "groups" in data["descriptions"]
    assert data["defaults"]["target_bpm"] == 130.0

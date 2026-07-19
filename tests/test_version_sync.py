from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app import __version__

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"Версия:\s*([0-9]+\.[0-9]+\.[0-9]+)")


def _json_field(data: dict, field: str) -> str:
    value = data
    for part in field.split("."):
        value = value[int(part)] if part.isdigit() else value[part]
    assert isinstance(value, str)
    return value


def test_project_versions_are_synchronized() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    expected = pyproject["project"]["version"]

    docs_versions = {
        path.name: match.group(1)
        for path in (ROOT / "AGENTS.md", ROOT / "GEMINI.md", ROOT / "DJ-MUSIC.md")
        if (match := VERSION_RE.search(path.read_text()))
    }

    assert __version__ == expected
    assert docs_versions == {
        "AGENTS.md": expected,
        "GEMINI.md": expected,
        "DJ-MUSIC.md": expected,
    }

    package = json.loads((ROOT / "package.json").read_text())
    assert package["version"] == expected

    bump_config = json.loads((ROOT / ".version-bump.json").read_text())
    for entry in bump_config["files"]:
        path = ROOT / entry["path"]
        data = json.loads(path.read_text())
        assert _json_field(data, entry["field"]) == expected, path.as_posix()

    factory_policy = (ROOT / ".factory/policy.toml").read_text()
    assert f'version = "{expected}"' in factory_policy

    worker = json.loads((ROOT / ".workers/dj-music-001.json").read_text())
    assert worker["version"] == expected

"""Single source of truth for the project version.

Reads from ``pyproject.toml`` at import time. All other code
(taxonomy.py, telemetry.py, api/openapi.py, etc.) should import
``__version__`` from here instead of hardcoding strings.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _read_version() -> str:
    with _PYPROJECT.open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


__version__: str = _read_version()

"""Shared resource constants.

All resources share these annotations and meta so the MCP client sees a
uniform surface. Using constants prevents drift between files.
"""

from __future__ import annotations

import json
from typing import Any

from app.v2 import __version__

ANNOTATIONS_READ_ONLY: dict[str, bool] = {
    "readOnlyHint": True,
    "idempotentHint": True,
}
"""Standard read-only annotation set.

Resources are by definition read-only (MCP spec). The hints repeat this so
clients that rely on annotations without checking the resource kind still
make the right decision.
"""

RESOURCE_META: dict[str, str] = {
    "version": __version__,
    "layer": "resource",
}
"""Static meta attached to every resource for observability."""


# Shared tag groups (import-convenient constants).
TAGS_CORE: frozenset[str] = frozenset({"core"})
TAGS_ADMIN: frozenset[str] = frozenset({"admin"})


# Icon placeholders — Phase 5 may wire real SVG sets. For now these are stable
# string handles so resources can declare them without a circular import.
ICON_TRACK: str = "icon:track"
ICON_PLAYLIST: str = "icon:playlist"
ICON_SET: str = "icon:set"
ICON_TRANSITION: str = "icon:transition"
ICON_SESSION: str = "icon:session"
ICON_SCHEMA: str = "icon:schema"
ICON_REFERENCE: str = "icon:reference"


def json_dump(payload: Any) -> str:
    """Serialize a payload to JSON with stable settings.

    - ``ensure_ascii=False``  — keep non-ASCII (subgenre names in Russian, etc.)
    - ``separators=(",",":")`` — compact output, no whitespace padding
    - ``sort_keys=False`` — preserve caller-defined ordering (field presets matter)
    """
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

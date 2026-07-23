"""Render DSP preset resources — per-subgenre override profiles.

Resources:
- ``reference://render/presets`` — list all preset names + metadata
- ``reference://render/presets/{name}`` — specific preset override dict
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.domain.render.presets import PRESET_METADATA, PRESETS
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META

# Note: templated resource names with hyphens work fine in FastMCP v3
# as long as the path segment matches {name} extraction rules.
_PRESET_NAMES = sorted(PRESETS.keys())


@resource(
    "reference://render/presets",
    mime_type="application/json",
    tags={"namespace:reference"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_presets_list_resource() -> str:
    """List all available render DSP presets with metadata."""
    return json.dumps(
        {
            "presets": _PRESET_NAMES,
            "details": {
                name: {
                    "label": PRESET_METADATA[name]["label"],
                    "bpm_range": PRESET_METADATA[name]["bpm_range"],
                    "dr_target_db": PRESET_METADATA[name]["dr_target_db"],
                    "lufs_target": PRESET_METADATA[name]["lufs_target"],
                    "description": PRESET_METADATA[name]["description"],
                    "compression": PRESET_METADATA[name]["compression"],
                    "eq_profile": PRESET_METADATA[name]["eq_profile"],
                    "limiter": PRESET_METADATA[name]["limiter"],
                    "transition": PRESET_METADATA[name]["transition"],
                }
                for name in _PRESET_NAMES
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


@resource(
    "reference://render/presets/{name}",
    mime_type="application/json",
    tags={"namespace:reference"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_preset_resource(name: str) -> str:
    """Get a specific render DSP preset with full override dict."""
    if name not in PRESETS:
        return json.dumps({"error": f"Preset '{name}' not found", "available": _PRESET_NAMES})
    return json.dumps(
        {
            "name": name,
            "label": PRESET_METADATA[name]["label"],
            "overrides": PRESETS[name],
            "metadata": PRESET_METADATA[name],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

"""Read-only exposure of DJ set templates for clients."""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from app.controllers.tools._shared import ANNOTATIONS_READ_ONLY, ICON_SETS, TOOL_META, ToolCategory
from app.templates.registry import TEMPLATES


@tool(
    title="Get Set Templates",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
async def get_set_templates() -> dict[str, Any]:
    """Return all DJ set templates with slot definitions (mood, energy, BPM, position).

    Static per release — clients should cache for the session.
    """
    return {
        "templates": [
            {
                "name": tpl.name,
                "duration_min": tpl.duration_min,
                "description": tpl.description,
                "slots": [
                    {
                        "position": slot.position,
                        "target_mood": slot.target_mood,
                        "energy_lufs": slot.energy_lufs,
                        "bpm_min": slot.bpm_min,
                        "bpm_max": slot.bpm_max,
                        "duration_ms": slot.duration_ms,
                        "flexibility": slot.flexibility,
                    }
                    for slot in tpl.slots
                ],
            }
            for tpl in TEMPLATES.values()
        ]
    }

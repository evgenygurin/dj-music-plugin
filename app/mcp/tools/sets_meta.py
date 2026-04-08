"""Read-only exposure of DJ set templates for clients."""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from app.domain.templates.registry import TEMPLATES
from app.mcp.tools._shared import ANNOTATIONS_READ_ONLY, ToolCategory


@tool(
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
)
async def get_set_templates() -> dict[str, Any]:
    """Return all DJ set templates with full slot definitions.

    Each template describes an energy arc as an ordered list of slots
    (warm-up → build → peak → release). Clients use the slot metadata
    (target mood, energy LUFS, BPM range, position, flexibility) to
    score candidate tracks during adaptive set playback.

    This tool is read-only, has no parameters, and returns a single
    payload containing all templates. The result is static per release
    so clients should cache it for the session.
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

"""Reference resources — static domain knowledge and configuration.

Resources:
- reference://camelot — 24 Camelot keys with compatibility rules
- reference://templates — 8 DJ set templates with slot definitions
- reference://subgenres — 15 techno subgenres with descriptions and energy order
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.core.constants import SetTemplate


@resource(
    uri="reference://templates",
    name="DJ Set Templates",
    title="DJ Set Templates",
    description="8 pre-defined DJ set templates with energy arcs and slot definitions",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
)
async def templates_reference() -> str:
    """Get DJ set template reference data.

    Returns JSON with all 8 templates:
    - name, duration_min, description
    - energy_arc: textual description
    - typical_use_case
    """
    templates = [
        {
            "name": SetTemplate.WARM_UP_30.value,
            "duration_min": 30,
            "description": "Low-energy opener for gradually building atmosphere",
            "energy_arc": "Gentle rise from ambient/dub to minimal/melodic",
            "typical_bpm_range": "120-128",
            "typical_moods": ["ambient_dub", "dub_techno", "minimal", "melodic_deep"],
            "use_case": "Opening set at club or festival",
        },
        {
            "name": SetTemplate.CLASSIC_60.value,
            "duration_min": 60,
            "description": "Standard build-peak-release arc over 1 hour",
            "energy_arc": "Build → Peak → Gentle release",
            "typical_bpm_range": "128-135",
            "typical_moods": [
                "progressive",
                "hypnotic",
                "driving",
                "peak_time",
                "melodic_deep",
            ],
            "use_case": "Mid-set slot, versatile",
        },
        {
            "name": SetTemplate.PEAK_HOUR_60.value,
            "duration_min": 60,
            "description": "High-energy throughout for peak-time slot",
            "energy_arc": "High intensity sustained with micro peaks",
            "typical_bpm_range": "132-140",
            "typical_moods": ["peak_time", "driving", "acid", "tribal"],
            "use_case": "Peak-time main floor",
        },
        {
            "name": SetTemplate.ROLLER_90.value,
            "duration_min": 90,
            "description": "Sustained driving energy for extended peak slot",
            "energy_arc": "Consistent high energy with rhythmic variation",
            "typical_bpm_range": "130-138",
            "typical_moods": ["driving", "hypnotic", "peak_time", "tribal"],
            "use_case": "Extended peak-time slot",
        },
        {
            "name": SetTemplate.PROGRESSIVE_120.value,
            "duration_min": 120,
            "description": "Gradual build over 2 hours from deep to peak",
            "energy_arc": "Slow ascent through all energy levels",
            "typical_bpm_range": "125-138",
            "typical_moods": [
                "minimal",
                "melodic_deep",
                "progressive",
                "driving",
                "peak_time",
            ],
            "use_case": "Opening to peak transition, storytelling set",
        },
        {
            "name": SetTemplate.WAVE_120.value,
            "duration_min": 120,
            "description": "Multiple energy waves with peaks and valleys",
            "energy_arc": "Build → Peak → Valley → Build → Peak (repeat)",
            "typical_bpm_range": "126-136",
            "typical_moods": ["progressive", "hypnotic", "driving", "melodic_deep"],
            "use_case": "Dynamic journey set",
        },
        {
            "name": SetTemplate.CLOSING_60.value,
            "duration_min": 60,
            "description": "Energy wind-down from peak to ambient",
            "energy_arc": "Gradual descent to atmospheric close",
            "typical_bpm_range": "122-130",
            "typical_moods": [
                "melodic_deep",
                "progressive",
                "dub_techno",
                "ambient_dub",
            ],
            "use_case": "Closing set, after-hours",
        },
        {
            "name": SetTemplate.FULL_LIBRARY.value,
            "duration_min": None,  # variable
            "description": "Use all available tracks, no template constraints",
            "energy_arc": "Dynamic, algorithm-optimized",
            "typical_bpm_range": "120-155 (full techno range)",
            "typical_moods": "All 15 subgenres",
            "use_case": "Exploration, playlist review, all-nighter",
        },
    ]

    data = {
        "total_templates": len(templates),
        "templates": templates,
        "note": (
            "Each template defines target slots with mood, energy (LUFS), "
            "BPM range, and duration. GA optimizer matches tracks to slots "
            "when template is active."
        ),
    }

    return json.dumps(data, indent=2)

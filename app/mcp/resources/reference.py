"""Reference resources — static domain knowledge and configuration.

Resources:
- reference://camelot — 24 Camelot keys with compatibility rules
- reference://templates — 8 DJ set templates with slot definitions
- reference://subgenres — 15 techno subgenres with descriptions and energy order
"""

from __future__ import annotations

import json

from app.core.constants import CAMELOT_KEYS, SetTemplate, TechnoSubgenre
from app.server import mcp


@mcp.resource(
    uri="reference://camelot",
    name="Camelot Wheel Reference",
    description="24 musical keys in Camelot notation with harmonic compatibility rules",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def camelot_reference() -> str:
    """Get Camelot wheel reference data.

    Returns JSON with:
    - keys: list of all 24 keys with code, notation, name
    - compatibility_rules: description of harmonic mixing rules
    - distance_chart: explanation of Camelot distance (0-6)
    """
    keys = []
    for code, (notation, name) in CAMELOT_KEYS.items():
        keys.append(
            {
                "code": code,
                "camelot": notation,
                "name": name,
            }
        )

    # Sort by Camelot notation (1A, 1B, 2A, 2B, ...)
    keys.sort(key=lambda k: (int(k["camelot"][:-1]), k["camelot"][-1]))

    compatibility_rules = {
        "perfect_match": "Same Camelot code (e.g., 8A → 8A) — distance = 0",
        "energy_boost": "Move from A to B of same number (e.g., 8A → 8B) — distance = 1",
        "adjacent_keys": "±1 on the wheel (e.g., 8A → 7A or 9A) — distance = 1",
        "safe_transition": "Distance ≤ 2 — generally safe for DJ mixing",
        "risky_transition": "Distance 3-4 — possible but requires skill",
        "hard_conflict": "Distance ≥ 5 — avoid in DJ sets (scoring system rejects)",
    }

    distance_explanation = (
        "Camelot distance measures harmonic compatibility:\n"
        "- 0: Perfect (same key)\n"
        "- 1: Excellent (adjacent or relative major/minor)\n"
        "- 2: Good (one step away)\n"
        "- 3: Acceptable (requires careful mixing)\n"
        "- 4: Risky (noticeable clash)\n"
        "- 5+: Bad (hard reject in transition scoring)\n"
    )

    data = {
        "total_keys": len(keys),
        "keys": keys,
        "compatibility_rules": compatibility_rules,
        "distance_explanation": distance_explanation,
        "wheel_structure": {
            "inner_circle": "Minor keys (A)",
            "outer_circle": "Major keys (B)",
            "positions": "1-12 (like a clock)",
        },
    }

    return json.dumps(data, indent=2)


@mcp.resource(
    uri="reference://templates",
    name="DJ Set Templates",
    description="8 pre-defined DJ set templates with energy arcs and slot definitions",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
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


@mcp.resource(
    uri="reference://subgenres",
    name="Techno Subgenres",
    description="15 techno subgenres ordered by energy intensity with descriptions",
    mime_type="application/json",
    tags={"core"},
    annotations={"readOnlyHint": True},
)
async def subgenres_reference() -> str:
    """Get techno subgenre reference data.

    Returns JSON with all 15 subgenres:
    - name, energy_level (1-15, low to high)
    - description, typical_bpm_range
    - key_features: list of audio characteristic descriptors
    """
    # All subgenres in energy order (enum is already ordered)
    subgenres = []
    energy_level = 1

    subgenre_details = {
        TechnoSubgenre.AMBIENT_DUB: {
            "description": "Atmospheric, spacious, minimal percussion",
            "bpm_range": "120-125",
            "key_features": [
                "High harmonic-to-percussive ratio",
                "Wide loudness range",
                "Low kick prominence",
                "Low spectral centroid",
            ],
        },
        TechnoSubgenre.DUB_TECHNO: {
            "description": "Deep bass, reverb-heavy, hypnotic chords",
            "bpm_range": "122-128",
            "key_features": [
                "Wide loudness range",
                "Low spectral centroid",
                "Moderate kick prominence",
                "High spectral flux variation",
            ],
        },
        TechnoSubgenre.MINIMAL: {
            "description": "Stripped-down, precise, micro-details",
            "bpm_range": "125-130",
            "key_features": [
                "Low kick prominence",
                "High spectral flatness",
                "Low energy mean",
                "Low onset rate",
            ],
        },
        TechnoSubgenre.DETROIT: {
            "description": "Soulful, melodic, machine funk",
            "bpm_range": "125-132",
            "key_features": [
                "High harmonic-to-percussive ratio",
                "Moderate spectral centroid",
                "Moderate energy",
                "Melodic content",
            ],
        },
        TechnoSubgenre.MELODIC_DEEP: {
            "description": "Emotive melodies, deep grooves",
            "bpm_range": "122-128",
            "key_features": [
                "High harmonic-to-percussive ratio",
                "Low spectral centroid",
                "Moderate energy",
                "Strong harmonic content",
            ],
        },
        TechnoSubgenre.PROGRESSIVE: {
            "description": "Evolving structures, gradual builds",
            "bpm_range": "126-132",
            "key_features": [
                "Moderate spectral centroid",
                "Positive energy slope",
                "Moderate kick prominence",
                "Structured sections",
            ],
        },
        TechnoSubgenre.HYPNOTIC: {
            "description": "Repetitive, trance-inducing, loop-based",
            "bpm_range": "128-134",
            "key_features": [
                "Low spectral flux std (repetitive)",
                "High pulse clarity",
                "Moderate energy",
                "Catch-all (penalized in classifier)",
            ],
        },
        TechnoSubgenre.DRIVING: {
            "description": "Propulsive groove, main floor energy",
            "bpm_range": "128-135",
            "key_features": [
                "High kick prominence",
                "High pulse clarity",
                "Moderate-high energy",
                "Catch-all (penalized in classifier)",
            ],
        },
        TechnoSubgenre.TRIBAL: {
            "description": "Percussive focus, ethnic rhythms",
            "bpm_range": "126-133",
            "key_features": [
                "Low harmonic-to-percussive ratio",
                "High onset rate",
                "Moderate spectral centroid",
                "Complex rhythms",
            ],
        },
        TechnoSubgenre.BREAKBEAT: {
            "description": "Broken rhythms, non-4/4 patterns",
            "bpm_range": "130-140",
            "key_features": [
                "High spectral flux std (varied)",
                "High onset rate",
                "Low pulse clarity (broken beat)",
                "Variable tempo",
            ],
        },
        TechnoSubgenre.PEAK_TIME: {
            "description": "High-energy main floor anthems",
            "bpm_range": "130-138",
            "key_features": [
                "High energy mean",
                "High kick prominence",
                "High loudness (LUFS)",
                "High pulse clarity",
            ],
        },
        TechnoSubgenre.ACID: {
            "description": "TB-303 basslines, squelchy resonance",
            "bpm_range": "132-140",
            "key_features": [
                "High spectral centroid",
                "High spectral flux mean",
                "Moderate-high energy",
                "Distinctive timbre",
            ],
        },
        TechnoSubgenre.RAW: {
            "description": "Unpolished, distorted, aggressive",
            "bpm_range": "135-145",
            "key_features": [
                "High spectral centroid",
                "Low spectral flatness",
                "High energy mean",
                "Narrow loudness range",
            ],
        },
        TechnoSubgenre.INDUSTRIAL: {
            "description": "Harsh, metallic, noise elements",
            "bpm_range": "138-150",
            "key_features": [
                "Very low harmonic-to-percussive ratio",
                "High spectral centroid",
                "Narrow loudness range",
                "High energy mean",
            ],
        },
        TechnoSubgenre.HARD_TECHNO: {
            "description": "Maximum intensity, pounding kicks",
            "bpm_range": "140-155",
            "key_features": [
                "Very high energy mean",
                "Very high kick prominence",
                "High loudness (LUFS)",
                "Narrow loudness range",
            ],
        },
    }

    for subgenre in TechnoSubgenre:
        details = subgenre_details[subgenre]
        subgenres.append(
            {
                "name": subgenre.value,
                "energy_level": energy_level,
                "description": details["description"],
                "typical_bpm_range": details["bpm_range"],
                "key_features": details["key_features"],
            }
        )
        energy_level += 1

    data = {
        "total_subgenres": len(subgenres),
        "energy_order": "Ordered from lowest (ambient_dub=1) to highest (hard_techno=15)",
        "subgenres": subgenres,
        "classifier_note": (
            "'driving' and 'hypnotic' are catch-all categories and are "
            "penalized in the mood classifier to prevent over-representation."
        ),
    }

    return json.dumps(data, indent=2)

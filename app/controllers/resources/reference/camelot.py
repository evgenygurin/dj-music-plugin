"""Reference resources — static domain knowledge and configuration.

Resources:
- reference://camelot — 24 Camelot keys with compatibility rules
- reference://templates — 8 DJ set templates with slot definitions
- reference://subgenres — 15 techno subgenres with descriptions and energy order
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.core.constants import CAMELOT_KEYS


@resource(
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
    keys.sort(key=lambda k: (int(str(k["camelot"])[:-1]), str(k["camelot"])[-1]))

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

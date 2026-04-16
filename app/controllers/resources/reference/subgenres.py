"""Reference resources — static domain knowledge and configuration.

Resources:
- reference://camelot — 24 Camelot keys with compatibility rules
- reference://templates — 8 DJ set templates with slot definitions
- reference://subgenres — 15 techno subgenres with descriptions and energy order
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.core.constants import TechnoSubgenre


@resource(
    uri="reference://subgenres",
    name="Techno Subgenres",
    title="Techno Subgenres",
    description="15 techno subgenres ordered by energy intensity with descriptions",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
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

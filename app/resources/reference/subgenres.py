"""Subgenre profiles reference resource.

URI: ``reference://subgenres``

Serializes the 15 techno subgenre profiles used by ``MoodClassifier``.
Shape adaptation: source profiles are ``SubgenreProfile`` dataclasses with
``features: dict[str, FeatureTarget]`` — we flatten to a list of feature
targets ordered by insertion so callers can reproduce scoring logic.
No standalone "description" field exists in the v2 source; the low-to-high
ordering in ``ALL_PROFILES`` encodes the energy narrative.

Render presets: 11 distinct ``SubgenreRenderPreset`` (7 techno + 4 house; 18 entries in ``PRESET_MAP`` with aliases) live in
``app/domain/performance/subgenre_presets.py:PRESET_MAP`` — see
``reference/subgenres.md`` for the full table. House presets:
``deep_house 32/48``, ``tech_house 16/32``, ``progressive_house 32/56``,
``classic_house 16/32``. ``hypnotic_techno`` is deprecated for House.
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.audio.classification.profiles import (
    ALL_PROFILES,
    CATCH_ALL_SUBGENRES,
    SubgenreProfile,
)
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.schemas.resource_views import (
    SubgenreFeatureView,
    SubgenreProfileView,
    SubgenresView,
)


def _profile_to_view(profile: SubgenreProfile) -> SubgenreProfileView:
    features = [
        SubgenreFeatureView(
            name=name,
            weight=target.weight,
            ideal=target.ideal,
            tolerance=target.tolerance,
        )
        for name, target in profile.features.items()
    ]
    return SubgenreProfileView(
        subgenre=profile.subgenre.value,
        catch_all_penalty=profile.catch_all_penalty,
        is_catch_all=profile.subgenre in CATCH_ALL_SUBGENRES,
        features=features,
    )


_PAYLOAD_JSON: str = SubgenresView(
    total=len(ALL_PROFILES),
    catch_all=sorted(s.value for s in CATCH_ALL_SUBGENRES),
    profiles=[_profile_to_view(p) for p in ALL_PROFILES],
).model_dump_json()


@resource(
    "reference://subgenres",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:subgenres"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_subgenres() -> str:
    """15 techno subgenre profiles (low-to-high) + 18 render presets (14 techno aliases + 4 house presets; see reference/subgenres.md and app/config/subgenre_constants.json)."""
    return _PAYLOAD_JSON


# ── Multi-genre resource template (polymorphic) ─────────────────

import json as _json_module


@resource(
    "local://genres/{genre}/subgenres",
    mime_type="application/json",
    tags={"core", "namespace:local", "view:subgenres", "polymorphic"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta={**RESOURCE_META, "template": "multi-genre"},
)
async def genre_subgenres(genre: str = "techno") -> str:
    """Polymorphic subgenre profile resource for a genre (techno, house, industrial, acid, etc.). Loads from subgenre_constants.json."""
    try:
        constants_path = __file__.replace(
            "app/resources/reference/subgenres.py", "app/config/subgenre_constants.json"
        )
        # Use relative path from module file
        import pathlib

        constants_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "app"
            / "config"
            / "subgenre_constants.json"
        )
        with open(constants_path, encoding="utf-8") as _cf:
            constants = _json_module.load(_cf)
        presets = constants.get("presets", {})
        profiles = constants.get("subgenre_profiles", {})
        genre_key = genre.strip().lower().replace(" ", "_")
        # Filter presets/profiles by group matching genre
        genre_presets = {
            k: v
            for k, v in presets.items()
            if v.get("group", "").startswith(genre_key) or genre_key in k
        }
        genre_profiles = {
            k: v
            for k, v in profiles.items()
            if v.get("group", "").startswith(genre_key) or genre_key in k
        }
        result = {
            "genre": genre,
            "subgenres": list(genre_presets.keys()),
            "profiles": genre_profiles,
            "presets_summary": {
                k: {
                    "transition_bars": v.get("transition_bars"),
                    "body_bars": v.get("body_bars"),
                    "bpm_range": v.get("bpm_range"),
                    "group": v.get("group"),
                }
                for k, v in genre_presets.items()
            },
            "audit_thresholds": constants.get("audit_thresholds", {}),
        }
        return _json_module.dumps(result, indent=2, ensure_ascii=False)
    except Exception as _exc:
        return _json_module.dumps(
            {"genre": genre, "error": str(_exc), "fallback": "reference://subgenres"}, indent=2
        )

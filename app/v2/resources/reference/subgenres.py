"""Subgenre profiles reference resource.

URI: ``reference://subgenres``

Serializes the 15 techno subgenre profiles used by ``MoodClassifier``.
Shape adaptation: source profiles are ``SubgenreProfile`` dataclasses with
``features: dict[str, FeatureTarget]`` — we flatten to a list of feature
targets ordered by insertion so callers can reproduce scoring logic.
No standalone "description" field exists in the v2 source; the low-to-high
ordering in ``ALL_PROFILES`` encodes the energy narrative.
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.v2.audio.classification.profiles import (
    ALL_PROFILES,
    CATCH_ALL_SUBGENRES,
    SubgenreProfile,
)
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
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
    """15 techno subgenre profiles (low-to-high energy order)."""
    return _PAYLOAD_JSON

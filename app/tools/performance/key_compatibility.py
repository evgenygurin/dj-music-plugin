"""key_compatibility — Camelot wheel key analysis with subgenre weighting."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.key_interchange import (
    analyze_key_relation,
    key_to_camelot,
    subgenre_key_score,
)
from app.schemas.key_compatibility import KeyCompatibilityResult


@tool(
    name="key_compatibility",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Analyze harmonic compatibility between two Camelot keys. "
        "Returns relation type (same/perfect/energy_up/modal/tritone/clash), "
        "compatibility score 0.0-1.0, and description. "
        "Optional subgenre weights alter scoring (e.g. industrial tolerates "
        "tritone transitions better than dub techno)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def key_compatibility(
    from_key: Annotated[int, Field(ge=0, le=23, description="Source Camelot key (0-23)")],
    to_key: Annotated[int, Field(ge=0, le=23, description="Target Camelot key (0-23)")],
    subgenre: Annotated[
        str | None,
        Field(description="Optional subgenre for weighted scoring"),
    ] = None,
) -> KeyCompatibilityResult:
    score = subgenre_key_score(from_key, to_key, subgenre)
    result = analyze_key_relation(from_key, to_key)
    return KeyCompatibilityResult(
        from_key=from_key,
        to_key=to_key,
        from_camelot=key_to_camelot(from_key),
        to_camelot=key_to_camelot(to_key),
        distance=result.distance,
        relation=result.relation.value,
        compatibility_score=round(score, 3),
        description=result.description,
    )

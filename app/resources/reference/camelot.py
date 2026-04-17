"""Camelot wheel reference resource.

URI: ``reference://camelot``
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.domain.camelot.wheel import camelot_distance
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.schemas.resource_views import (
    CamelotKeyView,
    CamelotWheelView,
)
from app.shared.constants import CAMELOT_KEYS, KEY_CODE_MAX, KEY_CODE_MIN

_WHEEL_SIZE = 12
# Compatible edges within this Camelot distance are pre-computed for the view.
_COMPAT_MAX_DISTANCE = 2


def _build_payload() -> CamelotWheelView:
    keys: list[CamelotKeyView] = []
    codes = range(KEY_CODE_MIN, KEY_CODE_MAX + 1)
    for code in codes:
        notation, name = CAMELOT_KEYS[code]
        edges: list[dict[str, object]] = []
        for other in codes:
            if other == code:
                continue
            dist = camelot_distance(code, other)
            if dist <= _COMPAT_MAX_DISTANCE:
                other_notation, _ = CAMELOT_KEYS[other]
                edges.append(
                    {
                        "target_code": other,
                        "target_notation": other_notation,
                        "distance": dist,
                    }
                )
        keys.append(
            CamelotKeyView(
                code=code,
                notation=notation,
                name=name,
                position=(code // 2) + 1,
                mode="A" if code % 2 == 0 else "B",
                compat_edges=edges,
            )
        )
    return CamelotWheelView(
        total=len(keys),
        wheel_size=_WHEEL_SIZE,
        keys=keys,
    )


# Pre-compute once at import time — static data never changes.
_PAYLOAD_JSON: str = _build_payload().model_dump_json()


@resource(
    "reference://camelot",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:camelot"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_camelot() -> str:
    """24-key Camelot wheel with compatibility edges (distance <= 2)."""
    return _PAYLOAD_JSON

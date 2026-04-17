"""Set templates reference resource.

URI: ``reference://templates``
"""

from __future__ import annotations

from fastmcp.resources import resource

from app.v2.domain.template.models import SetTemplateDefinition
from app.v2.domain.template.registry import TEMPLATES
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
    TemplateSlotView,
    TemplatesView,
    TemplateView,
)


def _to_view(tpl: SetTemplateDefinition) -> TemplateView:
    slots = [
        TemplateSlotView(
            position=s.position,
            target_mood=s.target_mood,
            energy_lufs=s.energy_lufs,
            bpm_min=s.bpm_min,
            bpm_max=s.bpm_max,
            duration_ms=s.duration_ms,
            flexibility=s.flexibility,
        )
        for s in tpl.slots
    ]
    return TemplateView(
        name=tpl.name,
        duration_min=tpl.duration_min,
        description=tpl.description,
        slots=slots,
    )


_PAYLOAD_JSON: str = TemplatesView(
    total=len(TEMPLATES),
    templates=[_to_view(t) for t in TEMPLATES.values()],
).model_dump_json()


@resource(
    "reference://templates",
    mime_type="application/json",
    tags={"core", "namespace:reference", "view:templates"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def reference_templates() -> str:
    """8 DJ set templates with slot-based energy arcs."""
    return _PAYLOAD_JSON

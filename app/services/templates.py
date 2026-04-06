"""Backward-compatibility shim — real code lives in app.domain.templates.

Will be removed in Phase 5 (cleanup).
"""

from app.domain.templates.models import (
    SetTemplateDefinition as SetTemplateDefinition,
)
from app.domain.templates.models import TemplateSlot as TemplateSlot
from app.domain.templates.registry import TEMPLATES as TEMPLATES
from app.domain.templates.registry import get_template as get_template
from app.domain.templates.registry import list_template_names as list_template_names

"""Backward-compatibility shim — real code lives in app.templates.

Will be removed in Phase 5 (cleanup).
"""

from app.templates.models import (
    SetTemplateDefinition as SetTemplateDefinition,
)
from app.templates.models import TemplateSlot as TemplateSlot
from app.templates.registry import TEMPLATES as TEMPLATES
from app.templates.registry import get_template as get_template
from app.templates.registry import list_template_names as list_template_names

"""Set template definitions — pure domain data (v2)."""

from app.domain.template.models import SetTemplateDefinition, TemplateSlot
from app.domain.template.registry import TEMPLATES, get_template, list_template_names

__all__ = [
    "TEMPLATES",
    "SetTemplateDefinition",
    "TemplateSlot",
    "get_template",
    "list_template_names",
]

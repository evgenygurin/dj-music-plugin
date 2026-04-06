"""Set template definitions — pure domain data."""

from app.domain.templates.models import SetTemplateDefinition, TemplateSlot
from app.domain.templates.registry import TEMPLATES, get_template, list_template_names

__all__ = [
    "TEMPLATES",
    "SetTemplateDefinition",
    "TemplateSlot",
    "get_template",
    "list_template_names",
]

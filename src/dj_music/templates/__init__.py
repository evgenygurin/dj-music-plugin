"""Set template definitions — pure domain data."""

from dj_music.templates.models import SetTemplateDefinition, TemplateSlot
from dj_music.templates.registry import TEMPLATES, get_template, list_template_names

__all__ = [
    "TEMPLATES",
    "SetTemplateDefinition",
    "TemplateSlot",
    "get_template",
    "list_template_names",
]

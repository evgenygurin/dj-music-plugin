"""Validation helpers for declarative configuration documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import TransitionSchema


def validate_fields(schema: TransitionSchema, values: Mapping[str, Any]) -> tuple[str, ...]:
    """Return deterministic validation errors without silently dropping fields."""
    errors: list[str] = []
    definitions = schema.by_name
    for name, value in values.items():
        definition = definitions.get(name)
        if definition is None:
            errors.append(f"unknown configuration field: {name}")
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            errors.append(f"{name} must be numeric")
            continue
        if not definition.minimum <= numeric <= definition.maximum:
            errors.append(f"{name} must be between {definition.minimum} and {definition.maximum}")
    return tuple(errors)

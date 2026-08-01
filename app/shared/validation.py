"""Shared validation utilities — reusable guards for handler inputs."""

from __future__ import annotations

from app.shared.errors import ValidationError


def validate_out_name(out_name: str | None) -> None:
    """Ensure ``out_name`` is a bare filename (no path separators, no . or ..)."""
    if not out_name:
        return
    if "/" in out_name or "\\" in out_name or out_name in {".", ".."}:
        raise ValidationError(
            f"out_name must be a bare filename, got {out_name!r}",
            details={"out_name": out_name},
        )

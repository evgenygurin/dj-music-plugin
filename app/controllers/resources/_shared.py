"""Shared helpers for resource responses."""

from __future__ import annotations

from typing import Any

from fastmcp.resources import ResourceContent, ResourceResult


def json_resource(content: Any) -> ResourceResult:
    """Wrap content in an explicit JSON-typed ``ResourceResult``."""
    return ResourceResult(
        contents=[ResourceContent(content=content, mime_type="application/json")]
    )

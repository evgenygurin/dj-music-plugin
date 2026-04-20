"""Typed error hierarchy for DJ Music Plugin v2.

These map to MCP errors at the tool boundary:
- NotFoundError    -> ToolError "entity not found" (404-like)
- ValidationError  -> ToolError with details (400-like)
- ConflictError    -> ToolError "duplicate / version mismatch" (409-like)
- NotAllowedError  -> ToolError "operation not permitted on entity" (403-like)

Infrastructure errors (DB, HTTP) are masked in production — never surfaced raw.
"""

from __future__ import annotations

from typing import Any


class DJMusicError(Exception):
    """Base for all domain errors."""


class NotFoundError(DJMusicError):
    """Entity not found by identifier."""

    def __init__(self, entity_type: str, identifier: Any) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier!r}")


class ValidationError(DJMusicError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class ConflictError(DJMusicError):
    """Conflict: duplicate key, optimistic-lock mismatch, invalid state transition."""


class NotAllowedError(DJMusicError):
    """Operation not allowed on this entity (missing from EntityConfig.allowed_ops)."""

    def __init__(self, *, entity: str, operation: str) -> None:
        self.entity = entity
        self.operation = operation
        super().__init__(f"operation {operation!r} not allowed on entity {entity!r}")


class TransientError(Exception):
    """Marker for errors safe to retry.

    Raise from providers / DB / network layers when a call failed due to a
    transient condition (timeout, rate-limit, connection reset). The
    ``RetryMiddleware`` retries these with exponential backoff.
    """

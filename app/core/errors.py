"""Typed error hierarchy for DJ Music Plugin.

Maps to MCP errors:
- NotFoundError -> ToolError "Entity not found"
- ValidationError -> ToolError with details
- ConflictError -> ToolError "Duplicate / version mismatch"
- Infrastructure errors -> masked in production
"""

from __future__ import annotations

from typing import Any


class DJMusicError(Exception):
    """Base error for all DJ Music Plugin errors."""


class NotFoundError(DJMusicError):
    """Entity not found."""

    def __init__(self, entity_type: str, identifier: Any) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")


class ValidationError(DJMusicError):
    """Input validation failed."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        self.field = field
        self.value = value
        super().__init__(message)


class ConflictError(DJMusicError):
    """Duplicate entity or version mismatch."""


# ── Pipeline Errors ──────────────────────────────────


class PipelineError(DJMusicError):
    """Audio analysis pipeline failure."""


class AnalyzerUnavailableError(PipelineError):
    """Required analyzer's dependency is not installed."""

    def __init__(self, analyzer: str, package: str) -> None:
        self.analyzer = analyzer
        self.package = package
        super().__init__(f"Analyzer '{analyzer}' requires package '{package}'")


class AnalysisTimeoutError(PipelineError):
    """Analysis exceeded timeout."""

    def __init__(self, analyzer: str, timeout: float) -> None:
        self.analyzer = analyzer
        self.timeout = timeout
        super().__init__(f"Analyzer '{analyzer}' timed out after {timeout}s")


# ── Yandex Music Errors ─────────────────────────────


class YandexMusicError(DJMusicError):
    """Yandex Music API error."""


class RateLimitedError(YandexMusicError):
    """HTTP 429 — rate limited."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limited by Yandex Music API"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(msg)


class AuthFailedError(YandexMusicError):
    """HTTP 401/403 — authentication failed."""

    def __init__(self, message: str = "Check DJ_YM_TOKEN") -> None:
        super().__init__(message)


class APIError(YandexMusicError):
    """Generic YM API error (4xx/5xx)."""

    def __init__(self, status_code: int, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"YM API error {status_code}: {body[:200]}")


# ── Export Errors ────────────────────────────────────


class ExportError(DJMusicError):
    """File export failure."""

    def __init__(self, message: str, path: str | None = None) -> None:
        self.path = path
        super().__init__(message)

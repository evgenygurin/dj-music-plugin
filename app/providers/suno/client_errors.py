"""Shared Suno provider exceptions."""

from __future__ import annotations


class SunoError(Exception):
    """Base Suno client error."""


class AuthFailedError(SunoError):
    """HTTP 401 / 403, expired session, or login failure."""


class RateLimitedError(SunoError):
    """HTTP 429 — too many requests."""


class APIError(SunoError):
    """HTTP 4xx (non-auth/non-rate-limit) or 5xx."""


class AudioNotReadyError(SunoError):
    """Generation has no downloadable audio URL yet."""

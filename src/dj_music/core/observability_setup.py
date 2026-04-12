"""Observability bootstrap helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dj_music.core.config import settings

ErrorCallback = Callable[[Exception, Any], None]


@dataclass(frozen=True)
class ObservabilityConfig:
    """Resolved observability hooks for the MCP server."""

    sentry_enabled: bool
    error_callback: ErrorCallback | None


def setup_observability(logger: logging.Logger | None = None) -> ObservabilityConfig:
    """Configure process-wide observability hooks."""
    log = logger or logging.getLogger(__name__)
    sentry_enabled = False

    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment="development" if settings.debug else "production",
                release=f"dj-music@{os.environ.get('DJ_PLUGIN_VERSION', 'dev')}",
                traces_sample_rate=1.0 if settings.debug else 0.2,
                profiles_sample_rate=1.0 if settings.debug else 0.1,
                send_default_pii=False,
                attach_stacktrace=True,
                integrations=[
                    AsyncioIntegration(),
                    SqlalchemyIntegration(),
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
            )
            sentry_enabled = True
            log.info(
                "Sentry error tracking enabled (env=%s)",
                "debug" if settings.debug else "production",
            )
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk not installed (uv sync --extra sentry)")

    def _sentry_error_callback(error: Exception, ctx: Any) -> None:
        """Forward FastMCP middleware errors into Sentry with tool/method context."""
        if not sentry_enabled:
            return
        try:
            import sentry_sdk

            method = getattr(ctx, "method", None) or "unknown"
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("mcp.method", method)
                scope.set_tag("mcp.error_type", type(error).__name__)
                sentry_sdk.capture_exception(error)
        except Exception as exc:  # never let telemetry crash the request path
            log.debug("Sentry capture_exception failed: %s", exc)

    return ObservabilityConfig(
        sentry_enabled=sentry_enabled,
        error_callback=_sentry_error_callback if sentry_enabled else None,
    )

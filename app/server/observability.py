"""Sentry + OpenTelemetry bootstrap.

Idempotent. Safe to call from the server entrypoint and from tests. Both
integrations are optional: if the driving env var is unset, the integration
is skipped silently.
"""

from __future__ import annotations

import logging
import os
from threading import Lock

try:  # pragma: no cover - optional extra
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

_bootstrap_lock = Lock()
_bootstrapped = False


def _init_otel(endpoint: str) -> None:  # pragma: no cover - optional
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("opentelemetry packages missing — OTEL disabled")
        return
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)


def _looks_like_url(value: str | None) -> bool:
    """Reject empty / unresolved-interpolation / non-URL strings.

    FastMCP's ``${VAR}`` interpolation in ``fastmcp.json`` leaves the literal
    placeholder when the env var is unset, so a downstream ``getenv`` returns
    ``"${DJ_SENTRY_DSN}"`` — truthy but invalid. Also tolerates whitespace.
    """
    if not value:
        return False
    s = value.strip()
    if not s or s.startswith("${"):
        return False
    return "://" in s


def bootstrap_observability() -> None:
    """Initialize Sentry and OTEL once per process. Idempotent."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        _bootstrapped = True

    dsn = os.getenv("DJ_SENTRY_DSN")
    if _looks_like_url(dsn) and sentry_sdk is not None:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.getenv("DJ_SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            environment=os.getenv("DJ_ENV", "dev"),
        )

    otel_endpoint = os.getenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT")
    if _looks_like_url(otel_endpoint):
        _init_otel(otel_endpoint)  # type: ignore[arg-type]

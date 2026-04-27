"""Middleware order matches blueprint §11. Do not reorder without updating spec."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE


def test_order_length_is_sixteen_post_v110() -> None:
    """v1.1.0 added JsonStringCoerceMiddleware (architectural fix for the
    v1.0.10-v1.0.13 transport-asymmetry bug class). Sits at position #2 so
    every other middleware sees already-coerced args."""
    assert len(ALL_MIDDLEWARE) == 16


def test_order_matches_spec() -> None:
    expected = [
        "DomainErrorMiddleware",
        "JsonStringCoerceMiddleware",
        "SentryContextMiddleware",
        # OTELTracingMiddleware removed in PR1 - FastMCP v3 native OTEL tracing.
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        "ToolCallTimeoutMiddleware",
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    actual = [c.__name__ for c in ALL_MIDDLEWARE]
    assert actual == expected

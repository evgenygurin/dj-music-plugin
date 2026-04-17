"""Middleware order matches blueprint §11 EXACTLY. Do not reorder."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE


def test_order_is_exactly_sixteen() -> None:
    assert len(ALL_MIDDLEWARE) == 16


def test_order_matches_spec() -> None:
    expected = [
        "ErrorHandlingMiddleware",
        "SentryContextMiddleware",
        "OTELTracingMiddleware",
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

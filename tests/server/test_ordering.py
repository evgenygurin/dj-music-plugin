"""Middleware order matches blueprint §11. Do not reorder without updating spec."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE


def test_order_length_is_seventeen_post_v190() -> None:
    """v1.9.0 added PromptGuardMiddleware for placeholder-argument guard."""
    assert len(ALL_MIDDLEWARE) == 17


def test_order_matches_spec() -> None:
    expected = [
        "DomainErrorMiddleware",
        "PromptGuardMiddleware",
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

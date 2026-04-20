"""Middleware order matches blueprint §11. Do not reorder without updating spec."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE


def test_order_length_is_fourteen_post_pr2() -> None:
    """PR1 dropped OTELTracingMiddleware. PR2 dropped ToolCallTimeoutMiddleware."""
    assert len(ALL_MIDDLEWARE) == 14


def test_order_matches_spec() -> None:
    expected = [
        "DomainErrorMiddleware",
        "SentryContextMiddleware",
        # OTELTracingMiddleware removed in PR1 — FastMCP v3 native OTEL tracing.
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        # ToolCallTimeoutMiddleware removed in PR2 — @tool(timeout=N) native.
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    actual = [c.__name__ for c in ALL_MIDDLEWARE]
    assert actual == expected

"""16 middleware classes — one per file, ordered outer→inner per blueprint §11.

First entry wraps all others at call time. DO NOT reorder without updating
the spec.
"""

from __future__ import annotations

from app.server.middleware.audit_log import AuditLogMiddleware
from app.server.middleware.cost_tracking import CostTrackingMiddleware
from app.server.middleware.db_session import DbSessionMiddleware
from app.server.middleware.deprecation_warning import DeprecationWarningMiddleware
from app.server.middleware.error_handling import ErrorHandlingMiddleware
from app.server.middleware.otel_tracing import OTELTracingMiddleware
from app.server.middleware.progress_throttle import ProgressThrottleMiddleware
from app.server.middleware.provider_rate_limit import ProviderRateLimitMiddleware
from app.server.middleware.response_caching import ResponseCachingMiddleware
from app.server.middleware.response_limit import ResponseLimitingMiddleware
from app.server.middleware.retry import RetryMiddleware
from app.server.middleware.sampling_budget import SamplingBudgetMiddleware
from app.server.middleware.sentry_context import SentryContextMiddleware
from app.server.middleware.structured_logging import StructuredLoggingMiddleware
from app.server.middleware.timing import DetailedTimingMiddleware
from app.server.middleware.tool_timeout import ToolCallTimeoutMiddleware

# ORDER MATTERS — matches blueprint §11. First added wraps all others at call time.
ALL_MIDDLEWARE: tuple[type, ...] = (
    ErrorHandlingMiddleware,  # 1  outermost
    SentryContextMiddleware,  # 2
    OTELTracingMiddleware,  # 3
    DetailedTimingMiddleware,  # 4
    AuditLogMiddleware,  # 5
    RetryMiddleware,  # 6
    ResponseLimitingMiddleware,  # 7
    ResponseCachingMiddleware,  # 8
    DeprecationWarningMiddleware,  # 9
    CostTrackingMiddleware,  # 10
    SamplingBudgetMiddleware,  # 11
    ProgressThrottleMiddleware,  # 12
    ToolCallTimeoutMiddleware,  # 13
    ProviderRateLimitMiddleware,  # 14
    DbSessionMiddleware,  # 15
    StructuredLoggingMiddleware,  # 16 innermost
)

__all__ = ["ALL_MIDDLEWARE"]

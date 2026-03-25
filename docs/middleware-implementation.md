# FastMCP Middleware Implementation

## Overview

This document describes the middleware pipeline implemented for the DJ Music MCP server, following FastMCP v3.1 best practices.

## Middleware Stack

The middleware are applied in the following order (outermost → innermost):

1. **ErrorHandlingMiddleware** (FastMCP built-in)
   - Catches all downstream errors
   - Includes tracebacks in debug mode
   - Transforms errors to proper MCP error responses

2. **StructuredLoggingMiddleware** (custom)
   - JSON-formatted request/response logging
   - Includes timestamp, method, source, type, duration
   - Optional payload logging (controlled by `settings.payload_logging`)
   - Payload truncation to prevent log explosion

3. **DetailedTimingMiddleware** (custom)
   - Per-operation timing for tools, resources, and prompts
   - Logs execution duration at INFO level
   - Logs failures at WARNING level with duration

4. **RateLimitingMiddleware** (FastMCP built-in)
   - Global rate limiting: 10 requests/second
   - Burst capacity: 20 requests
   - Token bucket algorithm

5. **ResponseLimitingMiddleware** (FastMCP built-in)
   - Limits response size to 50KB
   - Truncates large responses with suffix message
   - Prevents LLM context window overflow

6. **PingMiddleware** (FastMCP built-in)
   - 30-second keep-alive interval
   - Maintains long-lived connections
   - No effect on stateless connections

7. **YMRateLimitMiddleware** (custom, innermost)
   - Yandex Music API-specific rate limiting
   - Enforces 1.5s delay between consecutive YM tool calls
   - Only applies to tools prefixed with `ym_`

## Custom Middleware Details

### YMRateLimitMiddleware

**Purpose**: Respect Yandex Music API rate limits by enforcing a minimum delay between consecutive YM tool calls.

**Configuration**:
- `delay_seconds`: Minimum seconds between YM tool calls (default: 1.5, configurable via `settings.ym_rate_limit_delay`)

**Behavior**:
- Detects YM tools by `ym_` prefix
- First YM call proceeds immediately
- Subsequent YM calls wait if less than `delay_seconds` has elapsed since last call
- Non-YM tools pass through without delay

**Implementation**: `app/mcp/custom_middleware.py::YMRateLimitMiddleware`

### StructuredLoggingMiddleware

**Purpose**: Provide machine-readable JSON logs for aggregation tools (Datadog, Splunk, etc.)

**Configuration**:
- `include_payloads`: Log request/response content (default: False, controlled by `settings.payload_logging`)
- `max_payload_length`: Truncate payloads beyond this length (default: 500 chars)
- `logger_instance`: Custom logger (optional)

**Log Schema**:
```json
{
  "timestamp": "2025-03-25T05:30:00.123456Z",
  "method": "tools/call",
  "source": "client",
  "type": "request",
  "duration_ms": 42.56,
  "request": "..." (if include_payloads=true),
  "response": "..." (if include_payloads=true),
  "error": {  (on failure)
    "type": "ValueError",
    "message": "Invalid input"
  }
}
```

**Implementation**: `app/mcp/custom_middleware.py::StructuredLoggingMiddleware`

### DetailedTimingMiddleware

**Purpose**: Track execution time for different operation types (tools, resources, prompts, requests).

**Configuration**:
- `logger_instance`: Custom logger (optional)

**Log Examples**:
```
INFO  Tool timing: build_set completed in 1234.56ms
INFO  Resource timing: track://123/features read in 45.67ms
INFO  Prompt timing: build_set_workflow retrieved in 12.34ms
DEBUG Request timing: tools/call completed in 1250.00ms
WARN  Tool timing: analyze_track failed after 120000.00ms
```

**Implementation**: `app/mcp/custom_middleware.py::DetailedTimingMiddleware`

## Architecture Decision: Wrapper Pattern

To enable testing without importing the full FastMCP stack (which has dependency issues), we use a wrapper pattern:

- **`app/mcp/custom_middleware.py`**: Pure logic implementations (no FastMCP imports)
- **`app/mcp/middleware.py`**: Thin wrappers extending `fastmcp.server.middleware.Middleware`
- **`tests/test_middleware.py`**: Tests import from `custom_middleware.py` directly

This separation allows:
- Testing middleware logic without FastMCP dependency issues
- Clean integration with FastMCP's middleware system
- Type safety via mypy strict mode

## Configuration

All middleware settings are in `app/config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `debug` | `False` | Enable traceback in error handling |
| `payload_logging` | `False` | Include payloads in structured logs |
| `ym_rate_limit_delay` | `1.5` | Seconds between YM API calls |

## Testing

All custom middleware have comprehensive tests in `tests/test_middleware.py`:

- Rate limiting behavior (YM-specific)
- Structured logging with/without payloads
- Payload truncation
- Error logging
- Timing for different operation types
- Middleware chain integration

Run tests:
```bash
uv run pytest tests/test_middleware.py -v
```

## References

- FastMCP Middleware Documentation: https://gofastmcp.com/servers/middleware.md
- Design Spec: `docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md` §2.5
- REQUIREMENTS.md §15 (Non-Functional Requirements)

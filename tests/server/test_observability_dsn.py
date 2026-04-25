"""Regression: bootstrap_observability must not crash on FastMCP unresolved
``${VAR}`` interpolation passed as env value.

If the user does not set ``DJ_SENTRY_DSN`` in `.env`, FastMCP leaves the
literal ``${DJ_SENTRY_DSN}`` string from `fastmcp.json` as the env var
value. Without this guard, ``sentry_sdk.init(dsn="${DJ_SENTRY_DSN}")``
crashes with ``Unsupported scheme ''`` and the entire MCP stdio process
fails to start — making every native MCP call from Claude Code time out.
"""

from __future__ import annotations

from app.server.observability import _looks_like_url


def test_rejects_none() -> None:
    assert _looks_like_url(None) is False


def test_rejects_empty() -> None:
    assert _looks_like_url("") is False


def test_rejects_whitespace_only() -> None:
    assert _looks_like_url("   ") is False


def test_rejects_unresolved_interpolation_literal() -> None:
    assert _looks_like_url("${DJ_SENTRY_DSN}") is False


def test_rejects_non_url_truthy_value() -> None:
    assert _looks_like_url("not-a-url") is False


def test_accepts_real_sentry_dsn() -> None:
    assert _looks_like_url("https://abc@o123456.ingest.sentry.io/789") is True


def test_accepts_otel_http_endpoint() -> None:
    assert _looks_like_url("http://localhost:4317") is True

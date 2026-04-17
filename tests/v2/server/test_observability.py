"""Tests for observability bootstrap (Task 23)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app.v2.server.observability as obs


@pytest.fixture(autouse=True)
def _reset_bootstrap():
    obs._bootstrapped = False
    yield
    obs._bootstrapped = False


def test_bootstrap_noop_when_nothing_configured(monkeypatch) -> None:
    monkeypatch.delenv("DJ_SENTRY_DSN", raising=False)
    monkeypatch.delenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Must not raise even when nothing is configured.
    obs.bootstrap_observability()


def test_bootstrap_initializes_sentry_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DJ_SENTRY_DSN", "https://x@example.com/1")
    monkeypatch.delenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    with patch("app.v2.server.observability.sentry_sdk") as sdk:
        obs.bootstrap_observability()
        sdk.init.assert_called_once()
        kwargs = sdk.init.call_args.kwargs
        assert kwargs["dsn"] == "https://x@example.com/1"


def test_bootstrap_initializes_otel_when_configured(monkeypatch) -> None:
    monkeypatch.delenv("DJ_SENTRY_DSN", raising=False)
    monkeypatch.setenv("DJ_OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    with patch("app.v2.server.observability._init_otel") as init_otel:
        obs.bootstrap_observability()
        init_otel.assert_called_once_with("http://collector:4318")


def test_bootstrap_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("DJ_SENTRY_DSN", "https://x@example.com/1")
    with patch("app.v2.server.observability.sentry_sdk") as sdk:
        obs.bootstrap_observability()
        obs.bootstrap_observability()
        assert sdk.init.call_count == 1

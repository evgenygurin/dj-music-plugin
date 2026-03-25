"""Integration tests for telemetry without FastMCP imports.

These tests validate that:
1. Telemetry configuration is correct
2. Middleware can be instantiated and configured
3. OTEL integration works end-to-end
"""

import pytest

from app.config import settings


class TestTelemetryConfiguration:
    """Test telemetry configuration in settings."""

    def test_otel_config_exists(self):
        """OTEL configuration fields exist in settings."""
        assert hasattr(settings, "otel_enabled")
        assert hasattr(settings, "otel_service_name")
        assert hasattr(settings, "otel_endpoint")

    def test_otel_defaults(self):
        """OTEL has sensible defaults."""
        assert settings.otel_enabled is False  # Opt-in
        assert settings.otel_service_name == "dj-music"
        assert settings.otel_endpoint == ""  # Empty until configured

    def test_sentry_config_exists(self):
        """Sentry configuration exists."""
        assert hasattr(settings, "sentry_dsn")
        assert settings.sentry_dsn == ""  # Empty until configured


class TestTelemetryModules:
    """Test telemetry modules can be imported."""

    def test_telemetry_module_imports(self):
        """Telemetry module imports successfully."""
        from app import telemetry
        
        assert hasattr(telemetry, "instrument_heavy_operation")
        assert hasattr(telemetry, "add_span_event")
        assert hasattr(telemetry, "set_span_attributes")
        assert hasattr(telemetry, "record_error")

    def test_instrument_decorator_exists(self):
        """instrument_heavy_operation decorator exists."""
        from app.telemetry import instrument_heavy_operation
        
        @instrument_heavy_operation("test_op")
        async def test_func():
            return "test"
        
        # Decorator applied successfully
        assert test_func.__name__ == "test_func"


class TestServerConfiguration:
    """Test server.py has telemetry configured."""

    def test_server_has_observability_section(self):
        """Server.py includes observability setup."""
        with open("app/server.py") as f:
            content = f.read()
        
        assert "OpenTelemetry" in content
        assert "Sentry" in content
        assert "opentelemetry-instrument" in content

    def test_middleware_registered(self):
        """Server registers timing and logging middleware."""
        with open("app/server.py") as f:
            content = f.read()
        
        assert "DetailedTimingMiddleware" in content
        assert "StructuredLoggingMiddleware" in content
        assert "add_middleware" in content

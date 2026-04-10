"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py            # production

OpenTelemetry (optional, requires `uv sync --extra otel`):
    opentelemetry-instrument \
      --service_name dj-music \
      --exporter_otlp_endpoint http://localhost:4317 \
      fastmcp run app/server.py
"""

from app.bootstrap.server_builder import build_mcp_server

mcp = build_mcp_server()


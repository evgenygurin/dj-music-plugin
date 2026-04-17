"""MCP server composition root.

Per blueprint §§11, 12, 15.6. All wiring — middleware, transforms, visibility,
lifespan, DI, sampling, observability — lives in this package.

Public entrypoint: ``from app.v2.server.app import build_mcp_server``.
"""

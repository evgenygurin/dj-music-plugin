"""MCP server composition root.

Per blueprint §§11, 12, 15.6. All wiring — middleware, transforms, visibility,
lifespan, DI, sampling, observability — lives in this package.

Public entrypoint: ``from app.v2.server.app import build_mcp_server``.

For ``fastmcp run`` / ``python -m`` callers we also expose a module-level
``mcp`` constructed eagerly from ``build_mcp_server()``.

Run with::

    uv run fastmcp run app.v2.server --reload
    uv run python -m app.v2.server
"""

from __future__ import annotations

from app.v2.server.app import build_mcp_app_for_tests, build_mcp_server

__all__ = ["build_mcp_app_for_tests", "build_mcp_server", "mcp"]

mcp = build_mcp_server()


if __name__ == "__main__":  # pragma: no cover
    mcp.run()

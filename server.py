"""FastMCP stdio entrypoint.

Thin bootstrap module loaded by ``fastmcp run server.py``. Kept at the
project root so that ``import app.server.app`` resolves as a proper
package submodule (the FastMCP filesystem loader imports pointed
files as synthetic modules, which breaks self-referential
``from app.server.X import ...`` inside ``app/server/app.py``).
"""

from app.server.app import build_mcp_server

mcp = build_mcp_server()

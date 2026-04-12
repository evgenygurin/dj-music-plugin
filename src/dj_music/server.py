"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev src/dj_music/server.py --reload   # development
    uv run fastmcp run src/dj_music/server.py            # production
    uv run fastmcp dev app/server.py --reload             # legacy alias
"""

from dj_music.di.server_builder import build_mcp_server

mcp = build_mcp_server()

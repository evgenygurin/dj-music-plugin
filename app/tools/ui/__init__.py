"""Prefab Apps UI tools.

Tools in this package return ``prefab_ui`` component trees (charts, tables,
badges) that Prefab-aware MCP clients render inline. Non-Prefab clients fall
back to the JSON payloads declared in ``_fallback.py``.

Each tool is marked with ``meta={"ui": True}`` (the FastMCP wire format for
``@mcp.tool(app=True)``). FileSystemProvider auto-discovers the tool files
under this directory — no explicit registration needed.
"""

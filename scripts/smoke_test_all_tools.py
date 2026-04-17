"""Smoke-test the v1 MCP server — verify it boots and exposes tools/resources/prompts.

Usage: uv run python scripts/smoke_test_all_tools.py

Phase 7 note: the legacy per-tool invocation smoke targeted the pre-swap
API surface (88 tools across `app.controllers.*`). The v1 architecture
exposes a smaller, composable toolkit — this smoke just verifies the
server boots and the FileSystemProvider has registered all components.
Per-tool exercise is covered by the full pytest suite.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client


async def main() -> int:
    from app.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        print(f"tools={len(tools)}, resources={len(resources)}, prompts={len(prompts)}")

        if not tools:
            print("FAIL: zero tools discovered", flush=True)
            return 1
        if not resources:
            print("FAIL: zero resources discovered", flush=True)
            return 1
        if not prompts:
            print("FAIL: zero prompts discovered", flush=True)
            return 1

        print("sample tools:", [t.name for t in tools[:5]])
        print("sample resources:", [str(r.uri) for r in resources[:5]])
        print("sample prompts:", [p.name for p in prompts[:5]])
        print("OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Live MCP host for Prefab UI previews.

``prefab export`` output is a *static* renderer: the embedded MCP-Apps
client connects to ``window.parent`` over postMessage and, with no host
answering ``ui/initialize``, every button (``CallTool`` action) fails
with "Not connected". This script provides that host:

1. Builds the real ``ui_control_center`` PrefabApp for a live
   ``version_id`` (real DB data, in-process UoW) and renders it to a
   bundled HTML page (served at ``/app``).
2. Serves a wrapper page at ``/`` that iframes ``/app`` and implements
   the host side of the MCP-Apps postMessage protocol: replies to
   ``ui/initialize`` and forwards ``tools/call`` to ``POST /call``.
3. ``POST /call`` proxies into the real FastMCP server via an in-memory
   ``fastmcp.Client`` — full middleware/DI stack (UoW commit, hidden
   app-only tools like ``control_center_panel`` / ``act_build``), same
   process, so ``RENDER_JOBS`` state is shared with the served page.

Usage (from repo root, .env must point at the live DB):

    uv run python scripts/prefab_previews/serve_live.py --version-id 57
    # then open http://127.0.0.1:8300/
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any
from unittest.mock import MagicMock

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

HOST_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DJ Control Center — live preview host</title>
<style>
  html, body { margin: 0; height: 100%; background: #0b0b0e; }
  #bar { font: 12px/1.6 ui-monospace, monospace; color: #9ca3af;
         padding: 4px 12px; border-bottom: 1px solid #26262b; }
  #bar b { color: #34d399; }
  iframe { border: 0; width: 100%; height: calc(100% - 26px); }
</style>
</head>
<body>
<div id="bar">dj-preview-host — <b id="status">waiting for app…</b></div>
<iframe id="app" src="/app"></iframe>
<script>
const iframe = document.getElementById("app");
const status = document.getElementById("status");
const setStatus = (t) => { status.textContent = t; };

window.addEventListener("message", async (e) => {
  if (e.source !== iframe.contentWindow) return;
  const msg = e.data;
  if (!msg || msg.jsonrpc !== "2.0") return;
  // Responses and notifications from the app need no reply.
  if (msg.method === undefined || msg.id === undefined) return;

  const reply = (payload) =>
    iframe.contentWindow.postMessage({ jsonrpc: "2.0", id: msg.id, ...payload }, "*");

  try {
    if (msg.method === "ui/initialize") {
      setStatus("connected");
      reply({
        result: {
          protocolVersion: (msg.params && msg.params.protocolVersion) || "2026-01-26",
          hostInfo: { name: "dj-preview-host", version: "0.1.0" },
          hostCapabilities: { serverTools: {}, openLinks: {}, logging: {} },
          hostContext: {},
        },
      });
    } else if (msg.method === "tools/call") {
      const name = msg.params && msg.params.name;
      setStatus("calling " + name + "…");
      const r = await fetch("/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg.params),
      });
      const data = await r.json();
      if (data.error) {
        setStatus(name + " → error");
        reply({ error: { code: -32000, message: data.error } });
      } else {
        setStatus(name + " → ok");
        reply({ result: data.result });
      }
    } else if (msg.method === "ui/open-link" && msg.params && msg.params.url) {
      window.open(msg.params.url, "_blank", "noopener,noreferrer");
      reply({ result: {} });
    } else {
      // ping / ui/message / update-model-context — acknowledge.
      reply({ result: {} });
    }
  } catch (err) {
    reply({ error: { code: -32000, message: String(err) } });
  }
});
</script>
</body>
</html>
"""


async def _build_live_app_html(version_id: int) -> str:
    """Render the real ui_control_center PrefabApp for *version_id*."""
    import app.tools.ui.control_center as cc
    from app.db.session import get_session_factory
    from app.repositories.unit_of_work import UnitOfWork

    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(return_value=True)

    factory = get_session_factory()
    async with factory() as session:
        prefab_app = await cc.ui_control_center(
            version_id=version_id, uow=UnitOfWork(session), ctx=ctx
        )
    return prefab_app.html(renderer_mode="bundled")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version-id",
        type=int,
        default=int(os.environ.get("DJ_PREVIEW_VERSION_ID", "0")) or None,
        help="set_version id (live DB); env fallback DJ_PREVIEW_VERSION_ID",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8300")),
        help="HTTP port; env fallback PORT (dev-server harness)",
    )
    args = parser.parse_args()
    if not args.version_id:
        parser.error("--version-id (or DJ_PREVIEW_VERSION_ID env) is required")

    import uvicorn
    from fastmcp import Client

    from app.server.app import build_mcp_server

    print(f"building live control center for version_id={args.version_id} …")
    app_html = await _build_live_app_html(args.version_id)
    print(f"rendered app HTML ({len(app_html) / 1e6:.1f} MB)")

    mcp = build_mcp_server()

    async with Client(mcp) as client:

        async def index(_: Request) -> HTMLResponse:
            return HTMLResponse(HOST_PAGE)

        async def app_page(_: Request) -> HTMLResponse:
            return HTMLResponse(app_html)

        async def call(request: Request) -> JSONResponse:
            body: dict[str, Any] = await request.json()
            name = body.get("name", "")
            arguments = body.get("arguments") or {}
            meta = body.get("_meta")
            try:
                result = await client.call_tool_mcp(name, arguments, meta=meta, timeout=1800)
            except Exception:
                # Hidden app-only tools may be invisible to a plain client —
                # retry through the always-visible tool_invoke proxy.
                try:
                    result = await client.call_tool_mcp(
                        "tool_invoke", {"name": name, "arguments": arguments}, timeout=1800
                    )
                except Exception as exc:
                    return JSONResponse({"error": f"{type(exc).__name__}: {exc}"})
            return JSONResponse(
                {"result": result.model_dump(by_alias=True, mode="json", exclude_none=True)}
            )

        http_app = Starlette(
            routes=[
                Route("/", index),
                Route("/app", app_page),
                Route("/call", call, methods=["POST"]),
            ]
        )
        config = uvicorn.Config(http_app, host="127.0.0.1", port=args.port, log_level="info")
        server = uvicorn.Server(config)
        print(f"live preview host: http://127.0.0.1:{args.port}/")
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

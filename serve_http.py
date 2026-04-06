# serve_http.py
"""FastAPI wrapper exposing FastMCP server over HTTP.

Usage:
    uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.server import mcp

mcp_app = mcp.http_app(path="/")

api = FastAPI(title="DJ Music MCP API", lifespan=mcp_app.lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/api/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "tools": 50}


api.mount("/mcp", mcp_app)

---
paths: app/bootstrap/**/*.py
---

# Bootstrap (MCP Server Assembly)

- `build_mcp_server()` in `server_builder.py` is the ONLY place that assembles FastMCP
- `app/server.py` is a thin compatibility module — NEVER add logic there, modify `server_builder.py`
- Lifespan composition uses `|` operator: `db | ym | analyzer | cache | audio`
- Middleware ordering matters: log → timing → rate_limit → response_limit → retry → error_masking
- Visibility disables go in `visibility.py` — NEVER scatter `mcp.disable_*` calls elsewhere
- Transforms (namespace, R→T, P→T) go in `transforms.py`
- Sampling fallback handler goes in `sampling.py`
- OTEL + Sentry setup goes in `observability.py`

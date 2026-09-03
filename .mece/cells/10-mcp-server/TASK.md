# Cell 10 — MCP Server

## Mission
Own the FastMCP public surface and server composition.

## Read
- `app/tools/**`, `app/resources/**`, `app/prompts/**`, `app/server/**`
- `server.py`, `fastmcp.json`, MCP tests and relevant docs

## Scope
- Generic entity/provider dispatchers.
- Tool, resource, prompt, middleware, visibility and lifecycle contracts.
- MCP-facing errors and response schemas.
- Exposure of validated audio/DJ capabilities without duplicating domain logic.

## Write ownership
- `app/tools/**`, `app/resources/**`, `app/prompts/**`, `app/server/**`
- `server.py` / `fastmcp.json` only with explicit parent coordination.

## Constraints
- Preserve polymorphic dispatcher architecture.
- Discover/list servers before MCP verification.
- GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with surface changes, compatibility impact, tests, and dependencies.
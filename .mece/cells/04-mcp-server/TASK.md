# Cell 04 — MCP Server

## Mission
Own the FastMCP public surface and server composition: tools, resources, prompts, middleware/composition, and MCP-facing contracts.

## Read
- `AGENTS.md` and relevant `rules/`
- `app/tools/**`
- `app/resources/**`
- `app/prompts/**`
- `app/server/**`
- `server.py`, `fastmcp.json`, and MCP-related config/docs
- relevant MCP tests

## Scope
- Generic entity/provider dispatchers.
- UI Prefab tools.
- Resource URI surface.
- Workflow prompts.
- FastMCP composition, middleware, transforms, visibility, lifecycle.
- MCP-facing error/response contracts.

## Write ownership
- `app/tools/**`
- `app/resources/**`
- `app/prompts/**`
- `app/server/**`
- `server.py` and `fastmcp.json` only when explicitly delegated by parent

## Do not touch
Domain algorithms, audio implementation, persistence/provider internals, shared root governance, or another cell's files.

## Constraints
- Preserve the v1 polymorphic dispatcher architecture; do not proliferate one tool per entity operation.
- Preserve existing MCP visibility/resource/prompt semantics.
- Discover/list FastMCP servers before invoking tools during verification.
- Run GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with MCP surface changes, compatibility impact, tool/resource/prompt counts where relevant, tests, and integration dependencies.

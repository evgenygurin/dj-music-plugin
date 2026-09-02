# Research: FastMCP v3 structured output JSON serialization

**Target versions:** fastmcp 3.2.4 (pyproject.toml: "fastmcp[tasks,apps]>=3.2.4,<3.4"), Python 3.12, MCP spec 2025-06-18

**Sources inspected:**
- context7 /prefecthq/fastmcp v3.2.4 (4349 snippets, benchmark 84.31) — docs/servers/tools.mdx, docs/clients/tools.mdx
- GitHub prefecthq/fastmcp: docs/servers/tools.mdx (structured output rules), docs/clients/tools.mdx (result.data hydrated, result.structured_content raw), examples/code_mode/client.py, examples/search/client_*.py, PR #901 (structured outputs), PR #3604 (CallToolResult.data), issue #3596
- Local: app/tools/render/render_validate_grid.py:44 (-> GridCheckResult), app/schemas/render.py:58 (BaseModel), fastmcp 3.2.4 Client

**Findings:**
1. FastMCP v3 auto-generates structuredContent for Pydantic BaseModel returns. Server: `@mcp.tool -> GridCheckResult` generates outputSchema (object) and sends both `content[0].text` (JSON string) and `structuredContent` (dict) plus `_meta.x-fastmcp-wrap-result` for primitives.
2. Client: `result = await client.call_tool(...)` returns `CallToolResult` with:
   - `result.data` = hydrated Pydantic model (via `json_schema_to_type` + `TypeAdapter.validate_python(structured_content)`), includes complex types (datetime, UUID)
   - `result.structured_content` = raw dict (server's structuredContent)
   - `result.content[0].text` = JSON string (fallback)
   - `result.data is None` only if no structuredContent or deserialization fails (issue #3596, PR #3604 fixed tuple vs CallToolResult)
3. `json.dumps(result.data)` fails because stdlib json doesn't know Pydantic BaseModel. Correct per docs:
   - `result.data.model_dump()` or `result.data.model_dump(mode='json')` for hydrated object
   - `result.structured_content` for raw dict (already JSON-serializable)
   - `result.content[0].text` for text
   Examples: docs/clients/tools.mdx shows `result.data` field access, not json.dumps; examples/code_mode/client.py uses `_get_result` helper that returns `structured_content` or `text`.
4. Server returning `dict` vs `BaseModel`: both become structuredContent, but BaseModel gives precise outputSchema. Returning `dict` makes `res.data` a dict (json-serializable) but loses schema precision. Best practice per FastMCP docs: return BaseModel for schema, client uses `model_dump()` for json.

**Decision:**
- Keep server returning `GridCheckResult` (BaseModel) for schema precision.
- Fix client-side usage: document `result.data.model_dump()` / `result.structured_content`, add helper `pydantic_json_dumps` in shared utils, and update tool docstring to clarify.
- Add test that verifies `json.dumps` with helper works.

**Unresolved:** none. Evidence sufficient.

**Verification plan:**
- Unit test: `json.dumps(helper(result.data))` passes
- MCP Client test: call_tool with GridCheckResult, assert `result.data` is GridCheckResult and `json.dumps(result.data.model_dump())` succeeds

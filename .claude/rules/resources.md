---
description: MCP resource implementation patterns
globs: app/mcp/resources/**/*.py
---

# MCP Resources

- Use standalone `@resource` decorator from `fastmcp` (auto-discovered)
- Return JSON strings via `json.dumps()` or `ResourceResult` for multi-content
- Tags required: `tags={"core"}` or `tags={"admin"}`
- Static resources: fixed URI (e.g., `status://library`)
- Template resources: parametric URI (e.g., `track://{track_id}/features`)
- Query parameter resources: `{?param}` syntax (e.g., `catalog://stats{?mood,bpm_min}`)
- Reference resources: static domain data (Camelot wheel, templates, subgenres)
- All resources are read-only: `annotations={"readOnlyHint": True}`
- Use `Depends()` for DB access, same as tools

---
description: MCP resource implementation patterns
globs: app/controllers/resources/**/*.py
---

# MCP Resources

- Use standalone `@resource` decorator from `fastmcp` (auto-discovered by FileSystemProvider)
- **Return `dict[str, Any]`** — FastMCP serializes to JSON automatically. Do NOT use `json.dumps()`
  - Exception: knowledge:// reference blobs return `str` with `mime_type="application/json"` (too large for structured parsing)
- Tags required: `tags={"core"}`, `tags={"sets"}`, `tags={"admin"}`, etc. — matches visibility tiers
- Static resources: fixed URI (e.g., `status://library`)
- Template resources: parametric URI (e.g., `transition://{from_id}/{to_id}/score`)
- Reference resources: static domain data (Camelot wheel, templates, subgenres) — return `str` with `mime_type="application/json"`
- All resources are read-only: `annotations=ANNOTATIONS_READ_ONLY` (from `_shared.taxonomy`)
- Use `Depends()` for DB access, same as tools
- **Context injection**: `ctx: Context = CurrentContext()  # noqa: B008` when resource needs session context
  - Import `Context` from `fastmcp.server.context`, `CurrentContext` from `fastmcp.dependencies`
- Icons and meta: `icons=ICON_*`, `meta=RESOURCE_META` from `app.controllers.tools._shared.taxonomy`

## Gotchas

- Tests that parse resource return values: use `result` directly if `dict`, `json.loads(result)` if `str` — both forms can appear depending on resource type
- `session://` resources (set-draft, tool-history) must NOT be cached by `ResponseCachingMiddleware` — configured in `bootstrap/middleware.py`
- Template resource URIs use `{param}` syntax; query params use `{?param}` (e.g., `catalog://stats{?mood}`)

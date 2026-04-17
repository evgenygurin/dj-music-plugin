---
description: MCP resource implementation patterns (v1 layout)
globs: app/resources/**/*.py
---

# MCP Resources

- All `@resource` decorators live in `app/resources/` (auto-discovered).
- Use standalone `@resource` decorator from `fastmcp`.
- All resources are read-only (`mime_type="application/json"` for JSON).
- URI schemes:
  - `local://` — DB-backed entity views
    (e.g. `local://playlists/{id}`, `local://sets/{id}/{view}`,
    `local://transition/{from}/{to}/score`).
  - `schema://` — introspection
    (`schema://entities`, `schema://entities/{entity}`,
    `schema://providers/{name}`).
  - `session://` — per-client state
    (`session://set-draft`, `session://tool-history`,
    `session://energy-trend`).
  - `reference://` — static domain knowledge
    (`reference://camelot`, `reference://subgenres`,
    `reference://templates`, `reference://audit_rules`).
- Template resources: `{id}` for path params, `{?param}` for query params.
- Return JSON string via `json.dumps()` or a typed Pydantic model.
- Use `Depends(get_uow)` for DB access (same as tools).
- Tags default to `{"namespace:resource"}`.

Exposing resources as tools for tool-only clients is handled by
transforms in `app/server/transforms.py` — do not hand-roll wrapper
tools.

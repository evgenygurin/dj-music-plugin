---
description: Service layer patterns
globs: app/services/**/*.py
---

# Services

- Receive repositories via `__init__()`, never create them internally
- **No MCP/FastMCP imports** — services are framework-agnostic
- **No session imports** — services don't know about SQLAlchemy sessions
- Raise domain errors from `app/core/errors.py`: `NotFoundError`, `ValidationError`, `ConflictError`
- All public methods are async
- Use `settings.*` for all configurable values, never hardcode
- Use constants from `app/core/constants.py` for enums and domain values
- Complex operations should report progress via a callback (not MCP context directly)
- Services coordinate multiple repositories in a single transaction

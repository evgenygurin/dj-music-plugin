---
description: Service layer patterns
globs: src/dj_music/services/**/*.py
---

# Services

- Receive repositories via `__init__()`, never create them internally
- **No MCP/FastMCP imports** — services are framework-agnostic
- **No session imports** — services don't know about SQLAlchemy sessions
- Raise domain errors from `src/dj_music/core/errors.py`: `NotFoundError`, `ValidationError`, `ConflictError`
- All public methods are async
- Use `settings.*` for all configurable values, never hardcode
- Use constants from `src/dj_music/core/constants.py` for enums and domain values
- Complex operations should report progress via a callback (not MCP context directly)
- Services coordinate multiple repositories in a single transaction

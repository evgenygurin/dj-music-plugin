---
description: Testing patterns and conventions
globs: tests/**/*.py
---

# Tests

- Use `pytest` with `pytest-asyncio` (asyncio_mode = "auto")
- **Never mock the database** — use in-memory SQLite via `seeded_db` fixture
- MCP tool tests use `FastMCP Client` fixture — in-memory, no network
- Assert on `result.structured_content` for tool return values
- Assert on `result.meta` for warnings and alternatives
- Test tool metadata: tags, annotations, visibility
- Test pagination: verify `next_cursor`, `total`, no overlap between pages
- Test entity resolution: by ID, by query, ambiguous query
- Test elicitation: mock elicitation responses via FastMCP test utilities
- Test error cases: not found, invalid params, partial success
- Audio tests use synthetic WAV fixtures (440Hz sine, 128 BPM click, white noise)
- Name test files to mirror source: `app/services/track.py` → `tests/test_services/test_track.py`

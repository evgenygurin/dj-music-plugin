---
description: Testing patterns and conventions (v1)
globs: tests/**/*.py
---

# Tests

- Use `pytest` with `pytest-asyncio` (asyncio_mode = "auto").
- **Never mock the database** — use in-memory SQLite via `seeded_db`
  fixture (SQLite is tests-only; production is Supabase PostgreSQL).
- MCP tool tests use `FastMCP Client` fixture — in-memory, no network.
- Assert on `result.structured_content` for tool return values.
- Assert on `result.meta` for warnings and alternatives.
- Test tool metadata: tags, annotations, visibility.
- Test pagination: verify `next_cursor`, `total`, no overlap between
  pages.
- Test entity resolution: by ID, by filter, ambiguous filter.
- Test elicitation: mock elicitation responses via FastMCP test
  utilities.
- Test error cases: not found, invalid params, partial success.
- Audio tests use synthetic WAV fixtures (440 Hz sine, 128 BPM click,
  white noise).
- Name test files to mirror source:
  `app/handlers/track_import.py` → `tests/test_handlers/test_track_import.py`;
  `app/tools/entity/list.py` → `tests/test_tools/test_entity_list.py`;
  `app/repositories/track.py` → `tests/test_repositories/test_track.py`.

## Gotchas

- **Sort/order assertions**: always `assert len(result) > 0` BEFORE
  checking order. `[] == sorted([])` is trivially true.
- **Filter DSL tests**: seed `TrackAudioFeaturesComputed` for every
  Track before a query that joins features (INNER JOIN filters
  featureless rows).
- **BPM analyzer tests**: use `_kick_pattern(bpm)` helper — synthetic
  click track 30s+ gives stable onset envelope.
- **EntityRegistry**: tests that add a new entity must register it
  via the fixture, not by mutating the global registry directly
  (test pollution).

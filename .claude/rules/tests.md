---
description: Testing patterns and conventions (v1)
globs: tests/**/*.py
---

# Tests

- Use `pytest` with `pytest-asyncio` (asyncio_mode = "auto"). Pytest
  config lives in `pyproject.toml` under `[tool.pytest.ini_options]`:
  `testpaths = ["tests"]`, `addopts = "-n auto --dist loadfile"`
  (parallel via pytest-xdist; override with `-n 0` for serial /
  pdb). DeprecationWarnings from sqlalchemy and a couple of
  librosa UserWarnings on short synthetic signals are filtered.
- Dev tooling lives in `[dependency-groups] dev` (uv-native):
  pytest, pytest-asyncio, pytest-xdist, ruff, mypy, alembic,
  import-linter, respx. NOT under `[project.optional-dependencies]`.
- **Never mock the database** — use in-memory SQLite
  (aiosqlite) via the shared `engine` / `session` fixtures in
  `tests/conftest.py`. SQLite is tests-only; production is
  Supabase PostgreSQL.
- MCP tool tests use the `FastMCP Client` fixture — in-memory, no network.
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
- **Test dir layout mirrors `app/` (no `test_` prefix on dirs, only
  on files):**
  - `app/handlers/track_import.py` → `tests/handlers/test_track_import.py`
  - `app/tools/entity/list.py` → `tests/tools/entity/test_list.py`
  - `app/repositories/track.py` → `tests/repositories/test_track_repo.py`
  - Top-level test dirs: `audio/`, `config/`, `db/`, `domain/`,
    `handlers/`, `migrations/`, `models/`, `prompts/`, `providers/`,
    `registry/`, `repositories/`, `resources/`, `rest/`, `schemas/`,
    `server/`, `shared/`, `tools/`.

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

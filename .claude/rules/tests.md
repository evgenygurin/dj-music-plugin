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
- **`make test` / `make check` are hermetic** — live external-service
  round-trips (`-m integration`, currently the YM tests in
  `tests/providers/yandex/test_yandex_integration.py`) are excluded from
  the default gate: they share the YM rate budget per token/IP, so a
  running download job makes them flake with real 429s. Run explicitly
  via `make test-integration` (needs `DJ_YM_TOKEN`, pause download jobs
  first). New live tests MUST carry `pytest.mark.integration`.
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
    `registry/`, `repositories/`, `resources/`, `schemas/`,
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
- **SQLite PRAGMA foreign_keys=ON (v1.3.7).** `app/db/session.py`
  registers a `connect` event listener that enables FK enforcement on
  every aiosqlite connection. Tests that previously slipped through
  with orphan FK references now raise. Seed parents (e.g. `Track`,
  `Playlist`, `DjSet`) before children (`TrackFeatures`,
  `DjPlaylistItem`, `DjSetItem`) in fixtures.
- **`safe_info` / `safe_report_progress` in handlers (v1.3.7).**
  Handlers must use the wrappers from `app/handlers/_context_log.py`
  instead of `ctx.info()` / `ctx.report_progress()` directly — the
  wrappers fall back to stdlib logger when no active MCP session
  exists (headless scripts, unit tests). Test handlers in isolation
  by passing `ctx=None` — wrappers handle it.

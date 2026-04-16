---
description: Testing patterns and conventions
globs: tests/**/*.py
---

# Tests

- Use `pytest` with `pytest-asyncio` (asyncio_mode = "auto")
- **Never mock the database** — use in-memory SQLite via `seeded_db` fixture (SQLite used only for tests; production uses Supabase PostgreSQL)
- MCP tool tests use `FastMCP Client` fixture — in-memory, no network:
  ```python
  from fastmcp.client import Client
  from fastmcp.client.transports import FastMCPTransport
  from app.server import mcp

  @pytest.fixture
  async def client():
      async with Client(mcp) as c:
          yield c
  ```
- Tool result assertions — три уровня, выбирай нужный:
  - `result.data` — Pydantic-объект (когда инструмент возвращает Pydantic-модель)
  - `result.structured_content` — сырой dict из MCP `structuredContent`
  - `result.content[0].text` — текстовое представление
- Assert on `result.meta` for warnings and alternatives
- Test tool metadata: tags, annotations, visibility
- Test pagination: verify `next_cursor`, `total`, no overlap between pages
- Test entity resolution: by ID, by query, ambiguous query
- Test elicitation: в тестах FastMCP возвращает `decline` если elicitation-handler не настроен. Настраивай через `Client(mcp, elicitation_handler=lambda req: ...)` или мокай `ctx.elicit`
- Test error cases: not found, invalid params, partial success
- Audio tests use synthetic WAV fixtures (440Hz sine, 128 BPM click, white noise)
- Name test files to mirror source: `app/services/track_service.py` → `tests/test_services/test_track_service.py`

- **inline-snapshot** (`pytest-inline-snapshot`): snapshot testing without separate fixture files:
  ```python
  from inline_snapshot import snapshot
  assert result.content[0].text == snapshot("expected text here")
  # First run: add --snapshot-update flag to auto-fill the expected value
  ```
- **dirty-equals** for flexible type assertions:
  ```python
  from dirty_equals import IsStr, IsInt, IsPositive
  assert result.data.track_id == IsInt()
  assert result.data.title == IsStr(min_length=1)
  ```
- **Progress testing**: tools with `ctx.report_progress()` — use `Client(mcp)` in-memory. Progress calls are no-ops without a progress token. Test behavior and return values, not progress events.

## Gotchas

- **Sort/order assertions**: всегда `assert len(result) > 0` ПЕРЕД проверкой порядка. `[] == sorted([])` тривиально true и даёт false-positive PASS — баг сортировки пройдёт незамеченным
- **`filter_tracks_advanced` тесты**: seed `TrackAudioFeaturesComputed` для каждого Track перед вызовом, иначе INNER JOIN на features отсеет всё (см. `_seed_tracks_with_features` helper в `tests/test_repositories/test_track.py`)
- **BPM analyzer тесты**: используй `_kick_pattern(bpm)` (см. `tests/test_audio/test_bpm_detector.py`) — синтетический click track 30s+, дающий стабильную onset envelope

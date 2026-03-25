# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой.

- Спецификация: @REQUIREMENTS.md
- Дизайн-документ: @docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — слои, data flow, ключевые решения
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — все 45 MCP tools с параметрами
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 5-компонентная формула, Camelot wheel, caching
- @docs/background-tasks.md — FastMCP background tasks, progress, Docket, workers

## Принципы

- MCP — единственный интерфейс (нет REST API, нет CLI, нет web UI)
- FastMCP v3.1 — framework для MCP-сервера
- Python 3.12+, все операции async
- Strict typing: mypy strict + pydantic v2
- Тесты обязательны для каждого компонента
- **Никаких magic numbers** — все настройки в `app/config.py` (`settings.*`), все константы в `app/core/constants.py`

## Архитектура (слои)

```text
app/models/       → SQLAlchemy модели (данные)
app/repositories/ → Data access (flush, never commit)
app/services/     → Business logic (domain errors, no MCP imports)
app/mcp/tools/    → MCP tools (thin wrappers, DI via Depends)
app/mcp/resources/ → MCP resources (read-only data views)
app/mcp/prompts/  → Workflow prompt templates
app/audio/        → Audio analysis (optional deps)
app/ym/           → Yandex Music client (async httpx)
app/core/         → Shared: errors, constants, pagination, entity resolver
```

Правило: каждый слой импортирует только слой ниже. Tools → Services → Repositories → Models.

## Команды

```bash
uv sync                                    # Install deps
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run alembic upgrade head                # Migrations
uv run fastmcp dev app/server.py --reload  # Dev server
make check                                 # lint + typecheck + test
```

## Ключевые паттерны

### Конфигурация
```python
# ✅ Из settings
if bpm_diff > settings.transition_hard_reject_bpm_diff:
    return 0.0

# ❌ Никогда
if bpm_diff > 10:
    return 0.0
```

### MCP Tools
```python
from fastmcp import tool
from fastmcp.dependencies import Depends, CurrentContext

@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def my_tool(
    id: int,
    view: Literal["summary", "full"] = "summary",
    service=Depends(get_my_service),  # hidden from Claude
    ctx: Context = CurrentContext(),
) -> MyModel:
    """Short description ≤50 words."""
    ...
```

### Repositories
```python
# flush(), никогда commit() — commit делает DI wrapper get_db_session()
await self.session.flush()
```

### Errors
```python
from app.core.errors import NotFoundError, ValidationError
# В services — raise domain errors
raise NotFoundError(f"Track {id} not found")
# В tools — ToolError для input validation
raise ToolError("Provide either id or query")
```

## Плагины Claude Code

| Плагин | Когда использовать |
|--------|-------------------|
| **fastmcp-builder** | Перед реализацией MCP tools/resources/prompts |
| **mcp-server-dev** | При проектировании tool patterns, elicitation, auth |
| **superpowers** | Brainstorming, planning, TDD, debugging |
| **feature-dev** | Guided feature development с пониманием codebase |
| **python** | pytest fixtures, ruff config, mypy |
| **fastapi** | Alembic migrations (fastapi plugin имеет migrate-* скиллы) |
| **tech-lead** | Architecture review, dependency analysis |
| **context7** | Документация библиотек (FastMCP, SQLAlchemy, librosa) |
| **commit-commands** | Git commit workflow |

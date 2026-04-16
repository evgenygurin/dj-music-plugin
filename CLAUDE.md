# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Quick Start

```bash
uv sync --all-extras                       # Install all deps
# Sampling: index https://gofastmcp.com/llms.txt — page https://gofastmcp.com/servers/sampling (client default; optional ``--extra llm`` + ``DJ_ANTHROPIC_API_KEY``)
make check                                 # lint + typecheck + arch + test
uv run fastmcp run app/server.py --reload  # MCP dev server
cd panel && bun dev                        # Panel on :3000
./start.sh                                 # Both at once
```

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой. Включает веб-панель для мониторинга и аналитики.

- Спецификация: @REQUIREMENTS.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — слои, data flow, middleware pipeline, ключевые решения
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — каталог MCP tools с visibility tier
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 6-компонентная формула, Camelot wheel
- @docs/panel-guide.md — Panel архитектура, data flow, компоненты
- @docs/structure.md — полная структура директорий и файлов

## Архитектура (кратко)

```text
Interface    controllers (MCP tools/prompts/resources) + api (REST routes) + schemas (DTOs)
Application  services · workflows
Domain       entities · transition · optimization · templates · audit · export · camelot
Persistence  db (models · repositories · migrations · seed)
External     ym (Yandex Music client) · audio (analyzers · pipeline)
Core         config · constants · errors · utils
```

**Dependency rule (закреплено import-linter):**
- `controllers → services/workflows → services → repositories → entities/db.models`
- `services` framework-agnostic (нет fastmcp / app.controllers импортов)
- `transition` / `optimization` pure (нет DB / HTTP / MCP / SQLAlchemy / httpx)
- `core/utils` — leaf, не импортирует ни один app слой

## Команды

```bash
# Backend
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run lint-imports                        # Architecture contracts
uv run alembic upgrade head                # Migrations
make check                                 # lint + typecheck + arch + test

# Fallback если uv не в PATH:
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy app/
.venv/bin/python -m ruff check app/ tests/

# REST API
uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload

# Panel
cd panel && bun install && bun dev         # http://localhost:3000
```

## Правила

- **Один файл = одна ответственность.** Не создавать дублирующие файлы
- **Время:** все datetime-операции через `app/core/utils/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`)
- **Линтер:** ruff + mypy + import-linter. Pyright игнорируй — ложные ошибки на `@tool`
- **Magic numbers:** запрещены — только `settings.*` и `app/core/constants.py`
- **Context injection:** `ctx: Context = CurrentContext()  # noqa: B008`. Не использовать `Annotated[Context|None, ...] = None`
- **DI параметры:** `svc: MyService = Depends(get_my_service)` — без `Annotated[..., Field(...)]` обёртки
- **Tools:** описания ≤50 слов. Детали → в описания параметров. Технические параметры скрывать через `ArgTransformConfig(hide=True)` в `bootstrap/transforms.py`
- **Prompts:** возвращают `PromptResult(messages=[...], description="...")`, не `list[Message]`
- **Resources:** возвращают `dict[str, Any]` (FastMCP сериализует). Исключение: knowledge:// блобы → `str` с `mime_type="application/json"`
- **Visibility:** per-session через `ctx.enable_components(tags={...})`. Не использовать `ctx.fastmcp.enable()`
- **Structured output:** ключевые инструменты возвращают Pydantic-модели из `app/schemas/tool_responses.py` — FastMCP авто-генерирует `output_schema`

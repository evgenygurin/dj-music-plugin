# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Quick Start

```bash
uv sync --all-extras                       # Install all deps
make check                                 # lint + typecheck + arch + test
uv run fastmcp run app/server.py --reload  # MCP dev server
cd panel && bun dev                        # Panel on :3000
./start.sh                                 # Both at once
```

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс ��узыкой. Включает веб-панель для мониторинга и аналитики.

- Спецификация: @REQUIREMENTS.md

## Документация

При работе с конкретной областью — загрузи соответствующий doc:

- @docs/architecture.md — слои, data flow, ключевые решения
- @docs/domain-glossary.md — DJ терминология (BPM, Camelot, LUFS, subgenres)
- @docs/tool-catalog.md — каталог MCP tools с visibility tier
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/ym-api-guide.md — YM API quirks, rate limiting, diff format
- @docs/transition-scoring.md — 6-компонентная формула, Camelot wheel
- @docs/panel-guide.md — Panel архитектура, data flow, компоненты
- @docs/vm-deployment.md — continuous import+analyze loop на VM

## Принципы

- MCP — primary interface (tools, resources, prompts)
- Panel (Next.js) — monitoring/analytics UI, reads from Supabase, mutations via MCP
- REST API (`app/api/server.py`) — тонкая FastAPI сборка поверх `app/api/routes/*`, `state.py`, `lifespan.py`, `openapi.py`
- FastMCP v3.x — FileSystemProvider auto-discovers tools/resources/prompts из `app/controllers/` (standalone `@tool`, не `@mcp.tool`)
- Lifespan composition через `|` оператор: `db | ym | analyzer | cache | audio`
- Python 3.12+, все операции async
- Strict typing: mypy strict + pydantic v2
- Тесты обязательны для каждого компонента
- **Никаких magic numbers** — `app/config.py` (`settings.*`), `app/core/constants.py`

## Архитектура

```text
Interface    controllers (MCP tools/prompts/resources) + api (REST routes) + schemas (DTOs)
Application  services · workflows
Domain       entities · transition · optimization · templates · audit · export · camelot
Persistence  db (models · repositories · migrations · seed)
External     ym (Yandex Music client) · audio (analyzers · pipeline)
Core         config · constants · errors · utils
```

```text
Panel (Next.js) → REST API (FastAPI) ─┐
                                       ├──→ Controllers (FastMCP) → Services → Repositories → DB
MCP Client (stdio)                   ─┘                          → External (YM/audio)
```

```text
app/
├── core/              # config, constants, errors, utils, middleware
├── controllers/       # MCP entry (tools, prompts, resources, dependencies)
├── bootstrap/         # MCP composition root (lifespans, transforms, visibility)
├── api/               # FastAPI REST wrapper (routes, services, state)
├── schemas/           # Pydantic DTOs
├── services/          # request-scoped use cases + workflows
├── entities/          # pure dataclass domain (TrackFeatures)
├── transition/        # 6-component scoring + intent
├── optimization/      # GA, greedy, fitness
├── templates/         # set templates registry
├── audit/             # techno audit specs
├── export/            # M3U8, Rekordbox, JSON writers
├── camelot/           # Camelot wheel math
├── audio/             # analysis pipeline (analyzers, classification)
├── providers/         # MusicProvider protocol, models, registry (multi-platform)
├── clients/ym/        # Yandex Music client + adapter (implements MusicProvider)
├── db/                # persistence (models, repositories, migrations)
├── server.py          # thin entry → bootstrap/server_builder.py
├── config.py          # Settings (env DJ_*)
└── telemetry.py       # Sentry / OTEL
panel/                 # Next.js dashboard (shadcn, Supabase, Recharts)
```

**Dependency rule (закреплено import-linter):**
- `controllers → services/workflows → services → repositories → entities/db.models`
- `services` framework-agnostic (нет fastmcp / app.controllers импортов)
- `transition` / `optimization` pure (нет DB / HTTP / MCP / SQLAlchemy / httpx)
- `core/utils` — leaf, не импортирует ни один app слой

## Команды

```bash
# Backend (MCP server)
uv sync                                    # Install deps
uv run pytest -v                           # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                           # Type-check
uv run lint-imports                        # Architecture contracts
uv run alembic upgrade head                # Migrations
uv run fastmcp run app/server.py --reload  # MCP dev server (3.x: dev → run)
make check                                 # lint + typecheck + arch + test

# Fallback если uv не в PATH (используй venv напрямую):
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy app/
.venv/bin/python -m ruff check app/ tests/

# REST API
uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload

# Panel
cd panel && bun install && bun dev         # http://localhost:3000

# All-in-one
./start.sh                                 # Backend + Panel dev servers
```

## Правила

- **Один файл = одна ответственность.** Не создавать дублирующие файлы
- **Время:** все datetime-операции через `app/core/utils/time.py` (`utc_now()`, `utc_timestamp_iso()`, `sa_now()`)
- **Линтер:** ruff + mypy + import-linter. Pyright игнорируй — ложные ошибки на `@tool`
- **Архитектурные контракты** защищены `import-linter` (`make arch`)

## Selectel VM (audio analysis server)

Production DB (PostgreSQL) и audio analysis pipeline запускаются на Selectel VM.

### Подключение
```bash
bash scripts/selectel_run.sh "команда"           # выполнить команду на VM
bash scripts/selectel_run.sh                      # интерактивный SSH
```

Креды в `.env`: `SELECTEL_SSH_HOST`, `SELECTEL_SSH_USER`, `SELECTEL_SSH_KEY_PATH`, `SELECTEL_PROJECT_PATH`.

### Типовые операции на VM
```bash
# Подтянуть код и запустить миграции
bash scripts/selectel_run.sh "git pull && uv run alembic upgrade head"

# Запустить верификацию audio pipeline
bash scripts/selectel_run.sh "uv run python scripts/verify_audio_pipeline.py"

# Запустить тесты
bash scripts/selectel_run.sh "uv run pytest -v"

# Применить фикс beat detection
bash scripts/selectel_run.sh "bash scripts/fix_beat_on_server.sh"
```

### Selectel API (если нужно управление инфраструктурой)
- Keystone token: `POST https://cloud.api.selcloud.ru/identity/v3/auth/tokens`
- OpenStack CLI: `openstack server list`, `openstack server show <id>`
- Креды OpenStack в `.env`: `OS_AUTH_URL`, `OS_PROJECT_ID`, `OS_USERNAME`, `OS_PASSWORD`

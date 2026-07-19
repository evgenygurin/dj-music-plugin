# DJ Music Plugin — Project Instructions

> MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с Яндекс Музыкой.
> Версия: 1.10.0

**Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.**

## ⚠️ ВСЕГДА используй `uv`

**Запрещено** запускать `python`, `pip`, `pytest`, `ruff`, `mypy` напрямую.
Только через `uv`:

- `uv run python script.py` — запуск скриптов
- `uv run pytest tests/` — тесты
- `uv run ruff check` — линтинг
- `uv sync` / `uv sync --all-extras` — установка зависимостей
- `uv run alembic upgrade head` — миграции БД
- `uv run python -c "..."` — однострочники

## Quick Check

- `make check` — lint (ruff) + typecheck (mypy strict) + tests (pytest) + import-linter
- `uv run pytest` — run tests
- `uv run ruff check` — lint only
- Package manager: **uv** (not pip, not poetry)

## ⛔ No CI (GitHub Actions)

GitHub Actions unavailable for this account (billing lock). Quality via local gates only:
- `make check` — primary gate before every commit
- `hooks/pre-push` — auto-runs `make check` (skip: `DJ_SKIP_CHECK=1 git push`)

## Plugin Architecture

This project is a **FastMCP v3** server with bounded-contexts architecture.
Entry point: `server.py` → `fastmcp.json`. The MCP server exposes 20+ tools,
27 resources, and 30 prompts for DJ techno library management.

Key bounded contexts: `app/domain/` (pure logic), `app/audio/` (DSP/librosa),
`app/handlers/` (orchestration), `app/tools/` (MCP tool definitions),
`app/repositories/` (DB queries).

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **dj-music-plugin** (13438 symbols, 22137 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/dj-music-plugin/context` | Codebase overview, check index freshness |
| `gitnexus://repo/dj-music-plugin/clusters` | All functional areas |
| `gitnexus://repo/dj-music-plugin/processes` | All execution flows |
| `gitnexus://repo/dj-music-plugin/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## Project Routing

- Suno используй как opt-in provider в текущем проектном режиме no-browser
  session auth:
  `DJ_SUNO_COOKIE_HEADER` или `DJ_SUNO_BEARER_TOKEN`/`DJ_SUNO_CLIENT_TOKEN`
  плюс `DJ_SUNO_DEVICE_ID`; можно загрузить JSON из
  `DJ_SUNO_STORAGE_STATE_PATH`. Практичный browser export формат: Cookie header
  с `__session`, `__client` и `suno_device_id` или `ajs_anonymous_id`.
- Не запускай Playwright/browser-login из плагина. Пользователь проходит
  Google/Suno OAuth в своем браузере, а MCP provider использует уже готовые
  Suno/Clerk session credentials.
- Session путь работает через Suno web API:
  `https://studio-api-prod.suno.com` + `https://auth.suno.com`, Clerk Bearer
  token, `browser-token` и `device-id`. Не заменяй его старым generic
  `/v1/generations`; generic mode оставлен только для явно заданных
  Suno-compatible провайдеров с кастомным endpoint shape.
- SunoAPI из `docs.sunoapi.org` поддержан только opt-in, когда реально есть
  `DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_API_KEY`: default base
  `https://api.sunoapi.org`, create `/api/v1/generate`, polling
  `/api/v1/generate/record-info?taskId=...`, credits `/api/v1/generate/credit`,
  payload mode `sunoapi`.
- Не пытайся обходить CAPTCHA/2FA. Если Suno/Google просит ручное действие,
  остановись и попроси пользователя обновить session credentials после
  завершения проверки в браузере.
- Для самодостаточных сетов запускай `suno_set_asset_workflow`: генерируй
  intro/outro/bridges/rescue loops, скачивай через
  `provider_write(provider="suno", entity="generation", operation="download")`
  и держи эти файлы как export-side assets до появления local-file track import.

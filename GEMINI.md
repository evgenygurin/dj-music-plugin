# DJ Music Plugin

> MCP-сервер для управления DJ techno библиотекой. Версия: 1.10.0

**Всегда думай по-русски и отвечай по-русски.**

## ⚠️ ВСЕГДА используй `uv`

**Запрещено** запускать `python`, `pip`, `pytest`, `ruff`, `mypy` напрямую.
Только через `uv`:

- `uv run python script.py` — запуск скриптов
- `uv run pytest tests/` — тесты
- `uv run ruff check` — линтинг
- `uv sync` / `uv sync --all-extras` — установка зависимостей
- `uv run alembic upgrade head` — миграции БД

## Инструменты

`make check` — lint + typecheck + test. `uv run pytest` — тесты. **uv** — package manager.

## ⛔ GitHub Actions отключены

Проверка качества только локально: `make check` + pre-push хук.

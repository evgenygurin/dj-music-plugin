# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Цель проекта

Реализовать систему по спецификации в `REQUIREMENTS.md`. Прочитай его полностью перед началом работы.

## Принципы

- MCP — единственный интерфейс (нет REST API, нет CLI, нет web UI)
- Python 3.12+
- Все операции async
- Strict typing (mypy strict + pydantic)
- Тесты обязательны для каждого компонента

## Команды

```bash
uv sync                         # Install deps
uv run pytest -v                # Tests
uv run ruff check && uv run ruff format --check  # Lint
uv run mypy app/                # Type-check
```

## Плагины Claude Code

| Плагин | Назначение |
|--------|-----------|
| **fastmcp-builder** (husniadil) | Production-ready FastMCP patterns, tools, resources, prompts, testing |
| **mcp-server-dev** (Anthropic) | MCP server design: deployment model, tool patterns, auth, elicitation |
| **superpowers** (obra) | Brainstorming, planning, TDD, debugging workflows |
| **feature-dev** (Anthropic) | Guided feature development with codebase understanding |
| **context7** (Anthropic) | Documentation lookup for libraries |
| **commit-commands** (Anthropic) | Git commit workflow |

Перед реализацией MCP tools — используй скиллы `fastmcp-builder` и `mcp-server-dev` для выбора patterns.

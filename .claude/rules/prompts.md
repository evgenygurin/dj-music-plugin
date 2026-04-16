---
description: MCP workflow prompt implementation patterns (FastMCP v3)
globs: app/controllers/prompts/**/*.py
---

# MCP Workflow Prompts

- Use standalone `@prompt` decorator from `fastmcp` (auto-discovered via FileSystemProvider)
- **Return `PromptResult`**, NOT `list[Message]`:
  ```python
  from fastmcp.prompts import Message, PromptResult, prompt

  @prompt(name="my_prompt", ...)
  def my_prompt(arg: str) -> PromptResult:
      return PromptResult(
          messages=[Message("Instructions here...")],
          description=f"Dynamic description with {arg}",
      )
  ```
- `description` в `PromptResult` — динамическое, включает аргументы (например `f"Build set from '{playlist_name}'"`)
- Prompts are synchronous functions (не async) — они только возвращают инструкции для LLM, не выполняют I/O
  - Исключение: промпт может быть async если нужен `ctx` для `ctx.read_resource()` или `ctx.list_prompts()` — тогда `ctx: Context = CurrentContext()  # noqa: B008`
- Tags: `tags={"sets", "workflow"}` для стандартных workflow. Теги `"curation"`, `"discovery"` скрыты по умолчанию (в `_DISABLED_AT_STARTUP` в `bootstrap/visibility.py`) — используй `"sets"` или `"core"` для видимых промптов
- Все промпты регистрируются в `app/controllers/prompts/workflows/__init__.py` через `__all__`
- `meta={"version": "1.0"}` обязателен на каждом промпте
- `title="Human Readable Name"` — REQUIRED (отображается в UI)

## Gotchas

- Тег `"curation"` на промпте = скрыт по умолчанию. Если промпт должен быть виден — используй `"sets"` или `"workflow"`
- Тесты промптов: `assert isinstance(result, PromptResult)`, затем `result.messages[0].role` — НЕ `result[0].role` (PromptResult не является list)
- Промпты не имеют доступа к БД — они только формируют текстовые инструкции. Для логики с данными используй инструменты

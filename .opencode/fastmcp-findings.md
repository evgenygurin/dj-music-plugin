# FastMCP v3 — аудит dj-music-plugin

> Собрано из https://gofastmcp.com/. Сверено с реальным кодом проекта.
> Статус: ✅ уже есть | 🔧 можно улучшить | 💡 идея на будущее

---

## 1. Tools (`@tool`)

| Практика | Статус | Где |
|----------|--------|-----|
| standalone `@tool(...)` декоратор | ✅ | `app/tools/entity/*.py` |
| `tags={"namespace:crud:read", "read"}` | ✅ | все entity tools |
| `annotations={readOnlyHint, idempotentHint, destructiveHint}` | ✅ | создают правильные hints |
| `timeout=120.0` / `timeout=30.0` | ✅ | в декораторе |
| `meta={"timeout_s": 120.0}` | ✅ | **нужен** — `ToolCallTimeoutMiddleware` читает его, т.к. `FileSystemProvider` не пробрасывает `@tool(timeout=N)` |
| `version` в `@tool()` | 🔧 | можно добавить для API versioning |
| `output_schema` | ✅ | авто-генерируется из Pydantic return type |

## 2. Context

| Возможность | Статус | Где |
|-------------|--------|-----|
| `CurrentContext()` DI | ✅ | `entity_create`, `entity_update`, etc. |
| `ctx.info/warning/error()` | ✅ | handlers |
| `ctx.report_progress()` | 🔧 | для entity_create audio_file (долгая загрузка) |
| `ctx.elicit()` | 💡 | подтверждение destructive ops |
| `ctx.get_state/set_state()` | 💡 | кэш entity_list в рамках сессии |
| `ctx.read_resource(uri)` | 💡 | чтение `schema://entities/{entity}` |
| `ctx.sample()` | 💡 | LLM-анализ треков |

## 3. Dependency Injection

| Практика | Статус | Где |
|----------|--------|-----|
| `Depends(get_uow)` | ✅ | все entity tools |
| `Depends(get_provider_registry)` | ✅ | entity_create/update/delete |
| `Depends(get_audio_pipeline)` | ✅ | entity_create/update |
| `Depends(get_transition_scorer)` | ✅ | entity_create/update |
| `CurrentHeaders()` | 🔧 | для API-ключей |
| Кастомный `Depends(get_user)` | 💡 | аудит кто что сделал |

## 4. Middleware (15 шт)

| # | Middleware | Статус | Назначение |
|---|-----------|--------|------------|
| 1 | `DomainErrorMiddleware` | ✅ | NotFound/Validation → ToolError |
| 2 | `PromptGuardMiddleware` | ✅ | защита от placeholder-промптов |
| 3 | `JsonStringCoerceMiddleware` | ✅ | Claude Code stdio shim |
| 4 | `SentryContextMiddleware` | ✅ | Sentry breadcrumbs |
| 5 | `DetailedTimingMiddleware` | ✅ | встроенный из FastMCP |
| 6 | `AuditLogMiddleware` | ✅ | лог мутаций с content hash |
| 7 | `RetryMiddleware` | ✅ | TransientError retry |
| 8 | `ResponseLimitingMiddleware` | ✅ | кап размера ответа |
| 9 | `ResponseCachingMiddleware` | ✅ | entity_list/get/aggregate кэш (TTL через settings) |
| 10 | `DeprecationWarningMiddleware` | ✅ | предупреждения о версиях |
| 11 | `CostTrackingMiddleware` | ✅ | учёт токенов |
| 12 | `SamplingBudgetMiddleware` | ✅ | лимит sampling |
| 13 | `ProgressThrottleMiddleware` | ✅ | throttle 1/s |
| 14 | `ToolCallTimeoutMiddleware` | ✅ | per-tool timeout из `meta["timeout_s"]` |
| 15 | `ProviderRateLimitMiddleware` | ✅ | YM rate limit |
| 16 | `DbSessionMiddleware` | ✅ | open/commit/rollback UoW |
| — | `StructuredLoggingMiddleware` | ✅ | встроенный из FastMCP |

## 5. Visibility / Namespace Activation

| Практика | Статус | Где |
|----------|--------|-----|
| `mcp.disable(tags={"namespace:crud:destructive"})` | 🔧 | код есть, но `DISABLED_NAMESPACE_TAGS = frozenset()` — отключено из-за бага Claude Code |
| `ctx.enable_components(tags=...)` | ✅ | `unlock_namespace` tool |
| `ctx.disable_components(tags=...)` | ✅ | `unlock_namespace` tool |
| `ctx.reset_visibility()` | 🔧 | можно добавить в unlock_namespace |
| `mcp.enable(tags={...}, only=True)` | 💡 | allowlist mode для restricted окружений |

## 6. Lifespan

| Практика | Статус | Где |
|----------|--------|-----|
| `@lifespan` декоратор | ✅ | `app/server/lifespan.py` (6 lifespan-ов) |
| Composition через `|` | ✅ | `build_server_lifespan = a | b | c | d | e | f` |
| Access via `ctx.lifespan_context` | ✅ | в handlers |

## 7. Pagination

| Практика | Статус | Где |
|----------|--------|-----|
| `list_page_size` на FastMCP | 💡 | для MCP-level пагинации (tools/resources list) |
| Cursor-based пагинация для entity_list | ✅ | своя реализация через repos |

## 8. Background Tasks

| Практика | Статус | Применение |
|----------|--------|------------|
| `FastMCP(tasks=True)` | ✅ | server/app.py:79 |
| `@tool(task=True)` | 🔧 | для entity_create (долгие handlers) |
| `Progress()` dependency | 🔧 | прогресс загрузки/анализа |
| Redis backend | 💡 | для production scaling |

## 9. Transforms

| Практика | Статус | Где |
|----------|--------|-----|
| `ResourcesAsTools` | ✅ | `register_post_constructor_transforms` |
| `PromptsAsTools` | ✅ | `register_post_constructor_transforms` |
| `CodeModeTransform` | ✅ | опционально |

---

## Что реально можно улучшить (приоритет)

### 🔧 Сейчас

1. **Background Tasks для entity_create с тяжёлыми handler-ами** — `track_features_analyze`, `set_version_build`, `audio_file_download` могут работать в фоне с progress reporting.

2. **Валидация `field` в entity_aggregate** — сейчас не проверяется что поле существует в filter_schema сущности. DB ошибка приходит, но можно дать более понятную.

3. **`ctx.report_progress()` в долгих handler-ах** — даже без background tasks, progress reporting улучшит UX.

### 💡 На будущее

4. **Elicitation для destructive ops** — `ctx.elicit("Удалить трек #146?", response_type=bool)` перед entity_delete.

5. **Session State кэш** — кэшировать результаты entity_list в `ctx.set_state()`, инвалидировать при мутациях.

6. **`mask_error_details=True`** — отдельный FastMCP для prod с маскировкой внутренних ошибок.

7. **API Versioning через `@tool(version=...)`** — плавная миграция при изменении схем.

# FastMCP v3 Best Practices Alignment Report

**Date**: 2026-03-25  
**Scope**: All 44 MCP tools across 11 files  
**Status**: 🔴 Multiple patterns need correction

---

## Executive Summary

Проанализированы все 44 инструмента в проекте DJ Music Plugin. Обнаружены системные паттерны, которые не соответствуют лучшим практикам FastMCP v3:

| Категория | Проблема | Охват | Приоритет |
|-----------|----------|-------|-----------|
| **DI Pattern** | Ручное получение сессии вместо `Depends()` | 100% (44/44) | 🔴 Critical |
| **Context** | `ctx: Context \| None` вместо `CurrentContext()` | 100% (44/44) | 🔴 Critical |
| **Error Handling** | `return {"error": "..."}` вместо `ToolError` | ~80% (35/44) | 🔴 Critical |
| **Return Types** | `dict` вместо Pydantic models | ~70% (31/44) | 🟡 High |
| **Annotations** | Неправильные/отсутствующие annotations | ~50% (22/44) | 🟡 High |
| **Commits** | Прямые вызовы `session.commit()` в tools | ~30% (13/44) | 🟡 High |

---

## 1. Dependency Injection Pattern

### ❌ Текущая реализация (неправильно)

```python
# В КАЖДОМ файле дублируется этот helper:
async def _get_session(ctx: Context | None):
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()

@mcp.tool(tags={"core"})
async def list_tracks(
    limit: int = 20,
    ctx: Context | None = None,  # <-- ❌ Ручной параметр
) -> dict:
    async with await _get_session(ctx) as session:  # <-- ❌ Ручной вызов
        repo = TrackRepository(session)
        ...
```

**Проблемы:**
1. Код дублируется в 11 файлах
2. Параметр `ctx` виден в MCP-схеме (хотя не должен)
3. Нет кэширования сессии между зависимостями
4. Транзакции управляются вручную (риск утечек)
5. Нарушается Single Responsibility Principle

### ✅ Правильная реализация (FastMCP v3 best practices)

```python
# app/mcp/dependencies.py — единственный файл с DI
from typing import Annotated
from fastmcp.server.dependencies import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db_session() -> AsyncSession:
    """Scoped async DB session from lifespan context."""
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        yield session
        await session.commit()  # Auto-commit on success

async def get_track_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> TrackRepository:
    """TrackRepository with injected session."""
    return TrackRepository(session)


# app/mcp/tools/crud.py — инструменты используют DI
from fastmcp.server.dependencies import Depends, CurrentContext
from app.mcp.dependencies import get_track_repo

@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    track_repo: Annotated[TrackRepository, Depends(get_track_repo)],  # <-- ✅ Hidden
    ctx: Context = CurrentContext(),  # <-- ✅ Auto-injected
) -> PaginatedResponse[TrackBrief]:  # <-- ✅ Pydantic model
    page = await track_repo.list_all(limit=limit, cursor=cursor)
    return PaginatedResponse(
        items=[TrackBrief.from_model(t) for t in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )
```

**Преимущества:**
1. ✅ Нет дублирования кода
2. ✅ `Depends()` скрывает параметры из схемы
3. ✅ Сессия кэшируется в рамках одного запроса
4. ✅ Автоматический commit/rollback
5. ✅ Простые unit-тесты (можно мокировать DI)

---

## 2. Context Injection

### ❌ Текущая реализация

```python
@mcp.tool(tags={"core"})
async def list_tracks(
    limit: int = 20,
    ctx: Context | None = None,  # <-- ❌ Nullable, ручной параметр
) -> dict:
    if ctx:  # <-- ❌ Проверки на каждом шаге
        await ctx.info("Loading tracks...")
```

**Проблемы:**
1. `ctx` виден в MCP-схеме (параметр для LLM)
2. Nullable тип требует проверок везде
3. Inconsistent: иногда `if ctx:`, иногда `if ctx is None: raise`

### ✅ Правильная реализация

```python
from fastmcp.server.dependencies import CurrentContext

@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    ctx: Context = CurrentContext(),  # <-- ✅ Auto-injected, hidden
) -> PaginatedResponse[TrackBrief]:
    await ctx.info("Loading tracks...")  # <-- ✅ Всегда валиден
```

**Преимущества:**
1. ✅ Скрыт от MCP-схемы
2. ✅ Гарантированно не None
3. ✅ Чистый код без проверок

---

## 3. Error Handling

### ❌ Текущая реализация

```python
@mcp.tool(tags={"core"})
async def get_track(
    id: int | None = None,
    query: str | None = None,
) -> dict:
    if id is None and query is None:
        return {"error": "Provide id or query"}  # <-- ❌ Dict с ошибкой

    track = await repo.get_by_id(id)
    if track is None:
        return {"error": "Track not found"}  # <-- ❌ LLM видит {"error": "..."}
```

**Проблемы:**
1. LLM получает `{"error": "..."}` вместо MCP error
2. Нет стандартизации формата ошибок
3. Невозможно отличить ошибку от валидного ответа
4. Нет stack trace для debugging

### ✅ Правильная реализация

```python
from fastmcp import ToolError

@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_track(
    id: int | None = None,
    query: str | None = None,
    track_repo: Annotated[TrackRepository, Depends(get_track_repo)],
) -> TrackFull:
    if id is None and query is None:
        raise ToolError("Provide either 'id' or 'query' parameter")  # <-- ✅ MCP error

    track = await track_repo.get_by_id(id) if id else None
    if track is None:
        raise NotFoundError(f"Track {id or query!r} not found")  # <-- ✅ Domain error

    return TrackFull.from_model(track)
```

**Преимущества:**
1. ✅ MCP protocol compliance
2. ✅ Стандартный формат ошибок
3. ✅ Stack traces для debugging
4. ✅ Typed exceptions

---

## 4. Return Types

### ❌ Текущая реализация

```python
@mcp.tool(tags={"core"})
async def list_tracks(...) -> dict:  # <-- ❌ Untyped dict
    return {
        "items": [...],
        "next_cursor": "...",
        "total": 123,
    }
```

**Проблемы:**
1. Нет type safety
2. LLM не получает `structuredContent`
3. Нет валидации ответа
4. Тяжело тестировать

### ✅ Правильная реализация

```python
from app.core.schemas import PaginatedResponse, TrackBrief

@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(...) -> PaginatedResponse[TrackBrief]:  # <-- ✅ Pydantic
    return PaginatedResponse(
        items=[TrackBrief.from_model(t) for t in tracks],
        next_cursor=cursor,
        total=total,
    )
```

**Преимущества:**
1. ✅ Type safety (mypy checks)
2. ✅ Auto-generated `structuredContent` for LLM
3. ✅ Валидация на Pydantic
4. ✅ Простые тесты (`assert result.total == 42`)

---

## 5. Tool Annotations

### ❌ Текущие проблемы

| Tool | Текущие annotations | Должно быть | Проблема |
|------|-------------------|-------------|----------|
| `list_tracks` | `{"readOnlyHint": True}` | ✅ Correct | — |
| `manage_tracks` | `{"readOnlyHint": False}` | Should be omitted | Redundant |
| `deliver_set` | `{"destructiveHint": True, "readOnlyHint": False}` | Only `destructiveHint` | Redundant |
| `import_tracks` | `{"readOnlyHint": False, "idempotentHint": True}` | Only `idempotentHint` | Redundant |
| `find_similar_tracks` | `{"readOnlyHint": True, "openWorldHint": True}` | ✅ Correct | — |
| `unlock_tools` | Missing | `{}` | No annotations |

### ✅ Правильный подход

```python
# READ-ONLY tools
@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(...) -> PaginatedResponse[TrackBrief]:
    pass

# DESTRUCTIVE tools
@mcp.tool(tags={"delivery"}, annotations={"destructiveHint": True}, timeout=300.0)
async def deliver_set(...) -> DeliveryResult:
    pass

# IDEMPOTENT tools (НЕ read-only, но safe to retry)
@mcp.tool(tags={"discovery"}, annotations={"idempotentHint": True})
async def import_tracks(...) -> ImportResult:
    pass

# OPEN-WORLD tools (calls external API)
@mcp.tool(tags={"ym"}, annotations={"readOnlyHint": True, "openWorldHint": True})
async def ym_search(...) -> YMSearchResults:
    pass

# MUTATION tools (по умолчанию нет annotations)
@mcp.tool(tags={"core"})
async def manage_tracks(...) -> TrackStandard:
    pass
```

---

## 6. Transaction Management

### ❌ Текущая реализация

```python
@mcp.tool(tags={"core"})
async def manage_tracks(action: str, data: dict | None = None, ctx: Context | None = None):
    async with await _get_session(ctx) as session:
        repo = TrackRepository(session)

        if action == "create":
            track = Track(title=data["title"])
            track = await repo.create(track)
            await session.commit()  # <-- ❌ Прямой вызов commit
            return _track_standard(track)

        if action == "update":
            track = await repo.get_by_id(data["id"])
            track.title = data["title"]
            await repo.update(track)
            await session.commit()  # <-- ❌ Дублирование commit logic
            return _track_standard(track)
```

**Проблемы:**
1. Commit вызывается вручную 13 раз в разных местах
2. Нет единой точки управления транзакциями
3. Риск забыть commit
4. Риск commit после partial failure

### ✅ Правильная реализация

```python
# app/mcp/dependencies.py
async def get_db_session() -> AsyncSession:
    ctx = get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        yield session
        # ✅ Единственное место с commit — DI граница
        await session.commit()


# app/repositories/track.py
class TrackRepository:
    async def create(self, track: Track) -> Track:
        self.session.add(track)
        await self.session.flush()  # <-- ✅ flush, НЕ commit
        return track

    async def update(self, track: Track) -> Track:
        await self.session.flush()  # <-- ✅ flush, НЕ commit
        return track


# app/mcp/tools/crud.py
@mcp.tool(tags={"core"})
async def manage_tracks(
    action: str,
    data: dict | None = None,
    track_repo: Annotated[TrackRepository, Depends(get_track_repo)],
) -> TrackStandard:
    if action == "create":
        track = Track(title=data["title"])
        track = await track_repo.create(track)
        # ✅ НЕТ commit — сделается автоматически в DI
        return TrackStandard.from_model(track)
```

---

## Приоритизированный план исправлений

### Phase 1: Critical Infrastructure (1-2 дня)

1. **Fix `dependencies.py`** ✅ Частично сделано
   - Убрать `@asynccontextmanager` из `get_db_session()`
   - Заменить на `yield` паттерн
   - Добавить `Annotated[..., Depends(...)]` во все repo factories

2. **Create Pydantic response models** (1 день)
   ```python
   # app/core/schemas.py
   class TrackBrief(BaseModel):
       id: int
       title: str
       artist_names: list[str] = []
       bpm: float | None = None
       key_camelot: str | None = None
       duration_ms: int | None = None

   class DeliveryResult(BaseModel):
       set_id: int
       set_name: str
       track_count: int
       conflicts: int
       output_dir: str
       generated_files: list[str]
   ```

3. **Create domain errors** (2 часа)
   ```python
   # app/core/errors.py
   class DJMusicError(Exception):
       """Base domain error."""

   class NotFoundError(DJMusicError):
       """Entity not found."""

   class ValidationError(DJMusicError):
       """Invalid input data."""
   ```

### Phase 2: High-Priority Tools (3-4 дня)

Исправить по приоритету использования:

1. **CRUD tools (crud.py)** — 10 tools, тяжёлое использование
   - `list_tracks`, `get_track`, `manage_tracks`
   - `list_playlists`, `get_playlist`, `manage_playlist`
   - `list_sets`, `get_set`, `manage_set`
   - `get_track_features`

2. **Search tools (search.py)** — 2 tools
   - `search`, `filter_tracks`

3. **Sets tools (sets.py)** — 4 tools
   - `build_set`, `rebuild_set`, `score_transitions`, `get_set_cheat_sheet`

4. **Reasoning tools (reasoning.py)** — 5 tools
   - `suggest_next_track`, `explain_transition`, `find_replacement`
   - `compare_set_versions`, `quick_set_review`

### Phase 3: Extended Tools (2-3 дня)

5. **Delivery tools (delivery.py)** — 2 tools
6. **Discovery tools (discovery.py)** — 3 tools
7. **Curation tools (curation.py)** — 5 tools
8. **Sync tools (sync.py)** — 2 tools
9. **YM tools (ym.py)** — 6 tools
10. **Audio tools (audio.py)** — 3 tools
11. **Admin tools (admin.py)** — 2 tools

### Phase 4: Testing & Validation (1-2 дня)

- Add metadata tests for all tools
- Integration tests with FastMCP Client
- Validate annotations match design spec

---

## Example: Correct Implementation

### Before (crud.py, lines 102-141)

```python
@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    mood: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    status: str = "active",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List tracks with optional filters and cursor pagination."""
    async with await _get_session(ctx) as session:
        repo = TrackRepository(session)

        if bpm_min is not None or bpm_max is not None:
            page = await repo.filter_by_features(
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                limit=limit,
                cursor=cursor,
            )
        else:
            page = await repo.list_all(limit=limit, cursor=cursor)

        return PaginatedResponse[TrackBrief](
            items=[
                TrackBrief(
                    id=t.id,
                    title=t.title,
                    artist_names=[],
                    bpm=None,
                    key_camelot=None,
                    duration_ms=t.duration_ms,
                )
                for t in page.items
            ],
            next_cursor=page.next_cursor,
            total=page.total,
        ).model_dump()  # <-- ❌ Возвращаем dict вместо Pydantic
```

### After (correct FastMCP v3 pattern)

```python
from typing import Annotated, Literal
from fastmcp import ToolError
from fastmcp.server.context import Context
from fastmcp.server.dependencies import CurrentContext, Depends

from app.core.schemas import PaginatedResponse, TrackBrief
from app.mcp.dependencies import get_track_repo
from app.repositories.track import TrackRepository
from app.server import mcp


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    mood: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    status: Literal["active", "archived"] = "active",
    track_repo: Annotated[TrackRepository, Depends(get_track_repo)],  # <-- ✅ DI
    ctx: Context = CurrentContext(),  # <-- ✅ Auto-injected
) -> PaginatedResponse[TrackBrief]:  # <-- ✅ Pydantic return
    """List tracks with optional filters and cursor pagination.

    Supports filtering by mood, BPM range, and status. Returns paginated results.
    """
    if limit > 100:
        raise ToolError("limit must be ≤100")  # <-- ✅ Input validation

    await ctx.info(f"Listing tracks (limit={limit}, status={status})")

    # Business logic — clean, no session management
    if bpm_min is not None or bpm_max is not None:
        page = await track_repo.filter_by_features(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            limit=limit,
            cursor=cursor,
        )
    else:
        page = await track_repo.list_all(limit=limit, cursor=cursor)

    # ✅ Возвращаем Pydantic model напрямую
    return PaginatedResponse(
        items=[TrackBrief.from_model(t) for t in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )
```

**Что изменилось:**
1. ✅ `track_repo: Annotated[TrackRepository, Depends(get_track_repo)]` — DI
2. ✅ `ctx: Context = CurrentContext()` — авто-инъекция
3. ✅ `-> PaginatedResponse[TrackBrief]` — Pydantic return
4. ✅ `raise ToolError(...)` — правильная обработка ошибок
5. ✅ Нет `async with session`, нет `.model_dump()`
6. ✅ Чистая бизнес-логика

---

## Рекомендации

### Immediate Action (сделать сейчас)

1. ✅ **Зафиксировать `dependencies.py`** — уже начато
2. **Создать все Pydantic response models** в `app/core/schemas.py`
3. **Исправить 10 CRUD tools** — самые часто используемые
4. **Добавить metadata tests** для проверки annotations

### Short-term (1-2 недели)

1. Исправить остальные 34 tools по приоритету
2. Написать integration tests с FastMCP Client
3. Обновить документацию (`docs/tool-catalog.md`)

### Long-term (после завершения Sub-Project #2)

1. Code review всех tools через `fastmcp-builder` plugin
2. Performance testing (measure DI overhead)
3. Add OpenTelemetry spans для DI chain visibility

---

## Checklist для каждого tool

При исправлении tool, убедиться:

- [ ] Убран `_get_session(ctx)` helper
- [ ] Добавлен `Depends(get_*_repo)` для каждого используемого repo
- [ ] Параметр `ctx: Context = CurrentContext()`
- [ ] Возвращается Pydantic model, НЕ dict
- [ ] Input validation через `ToolError`, НЕ `return {"error": "..."}`
- [ ] Domain errors через `raise NotFoundError(...)`, НЕ `return {"error": "..."}`
- [ ] Убраны все `await session.commit()` из tool
- [ ] Annotations соответствуют таблице в design spec §4.5
- [ ] Description ≤50 words
- [ ] Tags соответствуют категории (core/extended/hidden)

---

## Metrics

### Current State

- **Total tools**: 44
- **Following best practices**: 0 (0%)
- **Using DI**: 0 (0%)
- **Using CurrentContext**: 0 (0%)
- **Returning Pydantic**: ~13 (30%)
- **Using ToolError**: ~9 (20%)

### Target State

- **Following best practices**: 44 (100%)
- **Using DI**: 44 (100%)
- **Using CurrentContext**: 44 (100%)
- **Returning Pydantic**: 44 (100%)
- **Using ToolError**: 44 (100%)

### Effort Estimate

- **Phase 1**: 1-2 дня (infrastructure)
- **Phase 2**: 3-4 дня (high-priority tools)
- **Phase 3**: 2-3 дня (extended tools)
- **Phase 4**: 1-2 дня (testing)
- **Total**: 7-11 рабочих дней

---

## Conclusion

Проект имеет solid foundation, но systematic refactoring необходим для соответствия FastMCP v3 best practices. Предложенный план позволяет:

1. ✅ Минимизировать risk — исправления incremental
2. ✅ Сохранить functionality — не breaking changes для пользователей
3. ✅ Улучшить maintainability — меньше дублирования, больше type safety
4. ✅ Подготовить к scale — правильная архитектура для будущих features

**Next Step**: Begin Phase 1 — fix `dependencies.py` and create Pydantic models.

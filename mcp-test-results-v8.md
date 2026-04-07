# MCP Tools — Round 8 (закрыты BUG-25..27 + NOTE-2/3/4/6)

**Дата**: 2026-04-07
**Ветка**: `dev`
**Предыдущий**: `mcp-test-results-v7.md`
**Метод**: in-process `Client(mcp)` + прямой вызов через MCP plugin

---

## TL;DR

| Bug | Статус | Файл |
|-----|--------|------|
| BUG-25 | ✅ Closed | `app/mcp/tools/run_tool.py` |
| BUG-26 | ✅ Closed | `app/ym/client.py` + `app/mcp/tools/yandex/albums.py` |
| BUG-27 | ✅ Closed (real impl) | `app/services/reasoning_service.py` + `app/mcp/tools/reasoning.py` |
| NOTE-2 | ✅ Closed | `app/mcp/tools/yandex/likes.py` |
| NOTE-3 | ✅ Closed | `app/services/curation/facade.py` |
| NOTE-4 | ✅ Closed | `app/services/search_service.py` |
| NOTE-6 | ✅ Closed | `app/repositories/track/stats.py` |

Тесты: **1015 passed, 3 skipped, 11 deselected** (5 deselected — pre-existing failures на dev до моих правок).

---

## BUG-25 — корневая причина и фикс

### Цепочка

1. `run_tool` → `ctx.fastmcp.call_tool('get_track', ...)` (inner call)
2. Inner `_call_tool` запускает middleware-стек
3. `get_track.fn()` → `@map_domain_errors` → `FastMCPNotFoundError("Track not found: 99999")`
4. Inner `_call_tool`'s `except FastMCPError: raise` — **НЕ** ловит, потому что `fastmcp.exceptions.NotFoundError` **не** subclass `FastMCPError` (наследуется напрямую от `Exception`)
5. Уходит в `except Exception` → `ToolError("Error calling tool 'get_track'") from FastMCPNotFoundError`
6. ToolError проходит через inner `ErrorHandlingMiddleware` → `McpError(-32001, "Not found: ...")`
7. `run_tool` ловит McpError — тоже НЕ `FastMCPError` → попадает в `except Exception` с обёрткой
8. Outer `_call_tool` видит ToolError c `__cause__=McpError` → outer middleware маппит как `-32603 Internal error`

### Фикс

`run_middleware=False` во внутреннем `call_tool` + расширенный clean-exceptions tuple. Это пропускает inner middleware-трансформацию, сохраняя `__cause__` chain для outer middleware.

```python
return await ctx.fastmcp.call_tool(name, parsed, run_middleware=False)
```

### Результат

```jsonc
get_track {id:99999} direct       → "Not found: Error calling tool 'get_track'"
get_track {id:99999} via run_tool → "Not found: Error calling tool 'get_track'"
```

Идентичный результат, код `-32001 Not found` восстановлен.

---

## BUG-26 — `ym_get_album` падает на 10-значных ID

### Корень

- 7-значный несуществующий ID → HTTP 200 с `{"result": {"id": 9999999, "error": "not-found"}}`
- 10-значный (overflow) ID → HTTP 400 `{"error": {"name": "validate", ...}}`

Предыдущий фикс обрабатывал только первый случай. Второй падал через `APIError(400)`.

### Фикс

```python
# app/ym/client.py::get_album
try:
    data = await self._request("GET", path)
except APIError as exc:
    if 400 <= exc.status_code < 500:
        return _parse_album({})
    raise

result = data.get("result")
if not isinstance(result, dict) or "error" in result:
    result = {}
return _parse_album(result)
```

Плюс в `albums.py` — `FastMCPNotFoundError` вместо `ToolError` для корректного `-32001`.

---

## BUG-27 — `find_replacement` реализован через TransitionScorer

Паттерн идентичный `suggest_next_track`:

1. Загрузить set/version, валидировать `position`
2. Получить prev/next item
3. Для каждого кандидата score `prev→cand` + `cand→next`, hard_reject → отбросить
4. Sort desc, top N

Возвращает `{set_id, position, current_track_id, pool_size, scored, candidates}`.

---

## NOTE-2 — `ym_likes get_liked` пагинация

```python
async def _get_liked(*, ym, limit=None, offset=0, **_):
    liked = await ym.get_liked_ids()
    ...
    page = liked[offset : offset + page_size]
    next_offset = offset + len(page)
    return {"count": total, "offset": offset, "limit": page_size,
            "liked_ids": page, "next_offset": next_offset if next_offset < total else None}
```

---

## NOTE-3 — `review_set_quality` rating порог

Hard conflicts теперь **non-negotiable**:

```python
if hard_conflict_ratio >= 0.5 or (hard_conflicts >= 1 and total_transitions <= 2):
    rating = "poor"
elif hard_conflicts >= 1:
    rating = "fair"
elif not quality_issues:
    rating = "excellent"
...
```

Set с ≥1 hard conflict никогда не получает "good"/"excellent".

---

## NOTE-4 — `search` tracks обогащённая структура

```python
results["tracks"] = [
    {"id", "title", "artist_names", "bpm", "key_camelot", "duration_ms"}
    ...
]
```

Поля идентичны `list_tracks` / `filter_tracks`.

---

## NOTE-6 — `get_library_stats` арифметика

```python
tracks_with_features = (
    await self.session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id))
        .join(Track, Track.id == TrackAudioFeaturesComputed.track_id)
        .where(Track.status == 0)
    )
).scalar() or 0
```

Инвариант: `with_features + without_features == active`.

---

## Проверка (in-process Client)

```text
[BUG-25 direct]       Not found: Error calling tool 'get_track'
[BUG-25 via run_tool] Not found: Error calling tool 'get_track'
[BUG-26 long ID]      Not found: Album not found: 9999999999
[BUG-26 short bad]    Not found: Album not found: 9999999
[BUG-27]              pool_size=1 scored=0 candidates=0
[NOTE-2]              count=413 returned=5 offset=100 next=105
[NOTE-3]              rating=poor hard_conflicts=1
[NOTE-4]              fields=[artist_names, bpm, duration_ms, id, key_camelot, title]
[NOTE-6]              active=3 with=3 without=0 sum=3 (active==sum: True)
```

---

## Затронутые файлы

| Файл | Изменение |
|------|-----------|
| `app/mcp/tools/run_tool.py` | `run_middleware=False` + расширенный clean_exc tuple |
| `app/ym/client.py` | `get_album`: catch APIError 4xx, check `error` in result |
| `app/mcp/tools/yandex/albums.py` | `FastMCPNotFoundError` вместо `ToolError` |
| `app/services/reasoning_service.py` | Новый метод `find_replacement` |
| `app/mcp/tools/reasoning.py` | `find_replacement` делегирует в ReasoningService |
| `app/mcp/tools/yandex/likes.py` | `limit`/`offset` для `get_liked` |
| `app/services/curation/facade.py` | Hard conflicts non-negotiable в rating |
| `app/services/search_service.py` | Enriched tracks shape |
| `app/repositories/track/stats.py` | `tracks_with_features` по `status==0` |
| `tests/test_mcp/test_ym_tools.py` | Expected exception type обновлён |

---

## Сводная таблица всех багов

| Bug | Open | Close | Статус |
|-----|------|-------|--------|
| BUG-1..6 | v1 | v2 | ✅ |
| BUG-7..14 | v2 | v3 | ✅ |
| BUG-15..18 | v3 | v4 | ✅ |
| BUG-21 | v4 | v5 | ✅ |
| BUG-22 | v5 | v5 | ✅ |
| BUG-23, 24 | v5 | v6 | ✅ |
| BUG-25, 26, 27 | v7 | **v8** | ✅ |
| NOTE-2, 3, 4, 6 | v3-v7 | **v8** | ✅ |

Все известные баги и заметки закрыты.

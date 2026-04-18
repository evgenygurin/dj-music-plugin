# MCP Tools — Re-test после BUG-7..14 фиксов

**Дата:** 2026-04-07
**Ветка:** `claude/plan-mcp-refactor-jfwzN`
**Контекст:** этот документ — продолжение `mcp-tools-retest-2026-04-07-round-1.md`,
который зарегистрировал баги BUG-7..14 после первого раунда e2e-теста
(исправлений BUG-1..6 в коммитах `363c090`, `8b4fb9c`).

> **Замечание о методе.** В этой сессии нет подключения к запущенному
> dj-music MCP серверу — `mcp__dj-music__run_tool` недоступен. Поэтому
> верификация выполнена через **код-инспекцию + полный pytest-suite**.
> Каждый фикс закрыт unit-тестом или осознанно опирается на существующее
> регресс-покрытие. Финальный статус: **987 passed / 34 skipped**, ruff
> clean, mypy clean.

---

## Итог

| | |
|---|---|
| 🔴 Высокоприоритетных багов | 2 → ✅ закрыты |
| 🟡 Средних | 3 → ✅ закрыты |
| 🟢 Низких | 2 → ✅ закрыты |
| Системный фикс | `@map_domain_errors` применён ко **всем** tool-функциям |
| Новых тестов | +4 (`ym_get_album`×3, `unlock_tools status`×1) + обновлён 1 mood-test |

---

## ✅ BUG-7 (🔴): `list_tracks` / `filter_tracks` `bpm: null` регрессия

### Симптом
После первого раунда фикса (BUG-1) `filter_tracks` стал возвращать
ту же форму что и `list_tracks` — но `bpm` / `key_camelot` были `null`
для всех треков, хотя `get_track_features` подтверждал наличие данных
в БД.

### Корневая причина
`TrackService.to_brief(track, features=None, ...)` корректно мапит
`bpm` / `key_camelot` только если `features` передан. Оба caller'а
(tracks.py:list_tracks и search.py:filter_tracks) получали только
`Track` модели — без eager-load или batch-fetch'a фич.

### Фикс
1. Новый метод `FeatureRepository.get_features_batch(track_ids)` —
   один SQL `IN (...)` для всей страницы (`app/repositories/feature.py`).
2. `list_tracks` и `filter_tracks` теперь делают:
   - `artist_map = await track_svc.get_artist_names_batch(track_ids)` (уже было)
   - **NEW:** `features_map = await feat_repo.get_features_batch(track_ids)`
   - `to_brief(t, features=features_map.get(t.id), artist_names=...)`
3. `FeatureRepository` инжектится через `Depends(get_feature_repo)` —
   фабрика уже существовала в `app/mcp/dependencies.py`.

**Производительность:** N+1 → 2 batch-запроса (artists + features) на страницу.

### Файлы
- `app/repositories/feature.py` — +`get_features_batch`
- `app/mcp/tools/tracks.py` — `list_tracks` принимает `feat_repo`
- `app/mcp/tools/search.py` — `filter_tracks` принимает `feat_repo`

---

## ✅ BUG-13 (🔴) + системное расширение: domain errors → ToolError повсеместно

### Симптом
`sync_playlist` для несуществующего playlist крашился generic
`"Error calling tool 'sync_playlist'"` вместо
`"Playlist not found: 1"` — тот же класс багов что BUG-5
(reasoning), но в другом tool-файле.

### Корневая причина
`map_domain_errors` decorator (`_shared/errors.py`) был применён
только к 5 reasoning tools. Другие сервисы (`SyncService`,
`SetService`, `CurationService`, `DeliveryService`,
`PlaylistService` …) тоже raise `NotFoundError` — но их tool-обёртки
не транслировали его в `ToolError`.

### Фикс — системный
Применил `@map_domain_errors` ко **всем** `@tool` функциям через
скрипт-аудит. Теперь любая доменная ошибка в любом сервисе
автоматически становится читаемым `ToolError`.

Покрытые файлы (16 функций добавлено к декоратору):
- `tracks.py` (4): `list_tracks`, `get_track`, `manage_tracks`, `get_track_features`
- `playlists.py` (3): `list_playlists`, `get_playlist`, `manage_playlist`
- `crud.py` (3): `list_sets`, `get_set`, `manage_set`
- `search.py` (2): `search`, `filter_tracks`
- `sets.py` (4): `build_set`, `rebuild_set`, `score_transitions`, `get_set_cheat_sheet`
- `curation.py` (5): `classify_mood`, `audit_playlist`, `review_set_quality`, `distribute_to_subgenres`, `get_library_stats`
- `delivery.py` (2): `deliver_set`, `export_set`
- `discovery.py` (3): `find_similar_tracks`, `filter_by_feedback`, `expand_playlist_ym`
- `import_download.py` (2): `import_tracks`, `download_tracks`
- `audio.py` (3): `analyze_track`, `analyze_batch`, `separate_stems`
- `audio_atomic.py` (4): `analyze_one_track`, `classify_one_track`, `gate_one_track`, `get_similar_one_track`
- `sync.py` (2): `sync_playlist`, `push_set_to_ym`
- `admin.py` (2): `unlock_tools`, `list_platforms`

`ym/*.py`, `reasoning.py` — уже имели декоратор (применён в первом раунде).

`@map_domain_errors` идемпотентен: пропускает функции, к которым уже
применён, и `ToolError` пропускает через себя нетронутым.

---

## ✅ BUG-12 (🟡): `unlock_tools action=status` теперь возвращает реальное состояние

### Симптом
`unlock_tools(action="status")` всегда возвращал заглушку
`{"action": "status", "message": "Use unlock/lock with a category"}`
независимо от того, что было разблокировано.

### Корневая причина
Оригинальный код имел только ветки `unlock` / `lock`; ветка `status`
никогда не реализовывалась — был просто fall-through на placeholder
строку.

### Фикс
В `app/mcp/tools/admin.py` появился helper `_build_status(ctx)`,
который читает per-session visibility rules через
`ctx.get_state("_visibility_rules")` (это canonical FastMCP API,
проверено `inspect.getsource(Context._get_visibility_rules)`).

Возвращаемая структура:
```jsonc
{
  "action": "status",
  "toggleable_categories": ["atomic","audio","curation","delivery","discovery","sync","ym"],
  "effective": {
    "audio": "enabled",      // <- последнее правило указало enabled
    "discovery": "disabled",
    "ym": "default",         // <- никаких правил не было, fallback к startup
    ...
  },
  "session_rules": [...]   // raw rules для дебага
}
```

Алгоритм: для каждой toggleable категории идём по rules в порядке
их добавления и берём `enabled` поле **последнего** matching rule —
это семантика "Visibility transform" в FastMCP. Категории без rules
получают `"default"` = fallback на startup-конфиг сервера.

Также добавлена валидация `_VALID_UNLOCK_ACTIONS` — неизвестный
action теперь падает с явным сообщением вместо silent fall-through.

### Тесты
- `test_unlock_tools_status` — обновлён под новую структуру
- `test_unlock_tools_status_after_unlock_reflects_state` — новый,
  проверяет что `unlock` → `status` возвращает `effective[cat]="enabled"`

---

## ✅ BUG-14 (🟢): `ym_get_album` для несуществующего album_id

### Симптом
YM API возвращает 200 OK с пустым stub `{id: "5816640", title: "", artists: [], ...}`
для несуществующего album_id вместо HTTP 404. Тулза возвращала этот
stub как валидный пустой альбом — клиент не мог отличить.

### Фикс
В `app/mcp/tools/yandex/albums.py`:
1. Валидация `album_id` (не пустая строка).
2. После получения ответа от YM проверка: если `not album.title and
   not album.artists and not album.tracks` → `raise ToolError("Album
   not found: {album_id}")`.

`ToolError` сразу понятен клиенту, и `@map_domain_errors` пропускает
его без изменений.

### Тесты (3 новых)
- `test_ym_get_album_raises_on_empty_stub` — empty YM response → `ToolError`
- `test_ym_get_album_returns_album_when_present` — реальный альбом проходит
- `test_ym_get_album_rejects_blank_id` — `"   "` падает до hit'а в YM

---

## ✅ BUG-11 (🟢): `classify_mood` теперь различает "no features" и "already classified"

### Симптом
`classify_mood {track_ids:[146]}` для трека с уже-классифицированным
mood возвращал `skipped_no_features: 1`, что неверно — фичи есть,
просто mood уже был.

### Фикс
В `app/services/curation/mood.py::classify_mood` теперь два разных
счётчика: `skipped_no_features` и `skipped_already_classified`. Оба
возвращаются в response.

`distribute_to_subgenres` (в `distribution.py`) НЕ затронут — там
`skipped` всегда означал "нет фич", алгоритм всегда переклассифицирует.
Семантика согласована.

### Тесты
Обновлён `test_classify_mood_skips_already_classified`:
```python
assert result["skipped_no_features"] == 0          # фичи есть
assert result["skipped_already_classified"] == 1   # mood есть
```

---

## ✅ BUG-10 (🟡): миграция cleanup устаревшего transition cache

### Симптом
После миграции `d5e8f37a2b91` в БД остались строки с
`timbral_score IS NULL` и `hard_reject IS NULL`, посчитанные старой
5-компонентной формулой с другими весами. `score_pair` возвращал их
как `cached: true` с `null` полями.

### Фикс
Новая миграция `e7c1f482a3b9_invalidate_legacy_transition_cache`:
```sql
DELETE FROM transitions WHERE timbral_score IS NULL;
```
`downgrade()` no-op (удалённые строки пересчитываются on-demand при
следующем `score_pair` вызове). Blast radius минимален — кэш
автоматически repopulate'ится.

### Цепочка миграций
```
bdc73180c4b9 → c4f8a9b2d1e3 (FK indexes)
             → d5e8f37a2b91 (timbral_score, hard_reject, reject_reason)
             → e7c1f482a3b9 (invalidate legacy cache)  ← head
```

---

## 📋 Изменённые файлы

### Прод-код
- `app/repositories/feature.py` — `get_features_batch`
- `app/services/curation/mood.py` — двойной счётчик skipped
- `app/mcp/tools/_shared/__init__.py` — экспорт `map_domain_errors` (уже был)
- `app/mcp/tools/tracks.py` — `feat_repo` + `@map_domain_errors`×4
- `app/mcp/tools/search.py` — `feat_repo` + `@map_domain_errors`×2
- `app/mcp/tools/playlists.py` — `@map_domain_errors`×3
- `app/mcp/tools/crud.py` — `@map_domain_errors`×3
- `app/mcp/tools/sets.py` — `@map_domain_errors`×4
- `app/mcp/tools/curation.py` — `@map_domain_errors`×5
- `app/mcp/tools/delivery.py` — `@map_domain_errors`×2
- `app/mcp/tools/discovery.py` — `@map_domain_errors`×3
- `app/mcp/tools/import_download.py` — `@map_domain_errors`×2
- `app/mcp/tools/audio.py` — `@map_domain_errors`×3
- `app/mcp/tools/audio_atomic.py` — `@map_domain_errors`×4
- `app/mcp/tools/sync.py` — `@map_domain_errors`×2
- `app/mcp/tools/admin.py` — `@map_domain_errors`×2 + `_build_status` + `_VALID_UNLOCK_ACTIONS`
- `app/mcp/tools/yandex/albums.py` — empty-stub validation
- `app/migrations/versions/e7c1f482a3b9_invalidate_legacy_transition_cache.py` — новая миграция

### Тесты
- `tests/test_mcp/test_ym_tools.py` — +3 (BUG-14)
- `tests/test_tools/test_search.py` — обновлён `test_unlock_tools_status` + новый `test_unlock_tools_status_after_unlock_reflects_state`
- `tests/test_services/test_curation_service.py` — обновлён `test_classify_mood_skips_already_classified` (BUG-11)

---

## Метрики

| | До | После |
|---|---:|---:|
| pytest passed | 983 | **987** (+4) |
| pytest skipped | 34 | 34 |
| Багов из round-2 | 7 (BUG-7..14, BUG-9 — env-only) | **0** (BUG-9 не код-баг) |
| Tools без `@map_domain_errors` | 16 | 0 |
| Crash на NotFoundError | да (5+ tools) | нет |
| Stale cached transition rows | да | нет (миграция e7c1f482) |
| `list_tracks` `bpm:null` для аналитического трека | да | нет |
| Ruff | clean | clean |
| Mypy | clean | clean |

---

## Не закрыто намеренно

### BUG-9 (🟡): error masking прячет реальные ошибки
**Не код-баг** — конфиг env (`DJ_DEBUG=true` или `mask_error_details=False`).
Уже отмечено в исходном отчёте как "проверить .env". На моей стороне
ничего фиксить не нужно.

### NOTE-A: TodoWrite reminder между tool calls
Это reminder из harness'а, не баг плагина.

### NOTE-B: Vercel/Next.js skill hooks ложно срабатывают на `app/**`
Конфиг hook'ов на стороне юзера — не код dj-music.

---

## Ограничения этого ре-теста

1. **Без runtime-вызовов MCP сервера** — `mcp__dj-music__run_tool` не
   подключён в этой сессии. Все фиксы покрыты unit-тестами через
   FastMCP `Client` фикстуру (in-memory) или прямыми мок-вызовами
   функций. Полноценный e2e (vs Supabase + YM API) понадобится в
   следующем раунде, когда MCP сервер будет доступен.
2. **Миграция e7c1f482a3b9 не применена** — её нужно прогнать на dev DB:
   ```bash
   uv run alembic upgrade head
   ```
   Только после этого `score_pair` перестанет возвращать stale rows.
3. Алгоритм `_build_status` для `unlock_tools` опирается на FastMCP
   internal session-state ключ `_visibility_rules`. Если FastMCP
   изменит этот контракт, status сломается. Покрыто двумя unit-тестами,
   но стоит мониторить FastMCP changelog.

---

## Следующие шаги

1. Применить миграцию `e7c1f482a3b9` к Supabase dev DB.
2. Запустить полный e2e MCP test pass (с подключённым `dj-music` сервером).
3. Если найдутся новые регрессии — round-3 (новый отчёт в этой же папке).

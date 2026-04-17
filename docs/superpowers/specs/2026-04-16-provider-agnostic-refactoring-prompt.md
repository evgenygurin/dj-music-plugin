# Provider-Agnostic рефакторинг

## Контекст

DJ Music Plugin — MCP-сервер для управления DJ techno библиотекой, построения сетов и интеграции с музыкальными платформами. Стек: Python 3.12, FastMCP, SQLAlchemy async, Pydantic v2, uv.

### Что уже сделано

В предыдущей сессии ([code-docs-audit](0b358b8e-0f78-421d-97fc-f11e01edb1f1)):

- Все сервисы (`sync_service`, `discovery_service`, `import_service`) принимают `ym: MusicProvider` вместо `YandexMusicClient`
- Все инструменты в `controllers/tools/yandex/` используют `provider: MusicProvider = Depends(get_music_provider)`
- Существует `ProviderRegistry`, `MusicProvider` протокол (18 методов), `YandexMusicAdapter`
- Модели: `ProviderTrack`, `ProviderAlbum`, `ProviderPlaylist`, `ProviderArtist`
- `save_ym_metadata` и `_extract_from_ym_track` обрабатывают и `ProviderTrack`, и `YMTrack`
- `make check` — 1362 passed, 0 failed

### Проблема

Кодовая база по-прежнему **пронизана YM-специфичным неймингом и структурой**:

1. **Директории**: `app/controllers/tools/yandex/` — привязана к провайдеру
2. **Инструменты**: `ym_search`, `ym_playlists`, `ym_get_album`, `ym_get_tracks`, `ym_likes` — префикс `ym_`
3. **Сервисы**: параметр `ym` в конструкторах (`self._ym`), методы `_push_to_ym`, `_collect_ym_track_ids`, `_extract_ym_kind` — не просто нейминг, а **YM-бизнес-логика** (формат `owner_id:kind`, `trackId:albumId`)
4. **Репозитории**: `save_ym_metadata`, `get_ym_metadata`
5. **Схемы**: `YMAlbumResponse`, `YMPlaylistActionResult`, `YMArtistTrackItem` и др. в `ym_responses.py`
6. **Конфигурация**: `settings.ym_user_id` используется в `_playlist_id()` — hardcode провайдера в контроллере
7. **Фильтры**: `discovery_service.py` импортирует `from app.clients.ym.filters import is_excluded_title` — нарушение слоёв (services → clients)
8. **Dict-ключи**: `"ym_id"` в ответах сервисов (`_provider_track_summary`) — контракт API
9. **Visibility**: `ToolCategory.YM = "ym"` — MCP visibility tag
10. **Тесты**: `make_ym_track`, `_make_ym_mock`, `ym=ym_mock`
11. **Параметры инструментов**: `kind: int` — YM-специфичный тип (Spotify использует строковые ID)

## Задача

**Используй скилл brainstorming** для проектирования. Рефакторинг разбит на **4 фазы** — каждая фаза самодостаточна и завершается зелёным `make check`.

---

## Фаза 1: Схемы, репозитории, фильтры (~12 файлов)

*Низкий риск, высокая ценность. Внутренний рефакторинг — не виден снаружи.*

### 1.1 Схемы ответов

Переименовать файл и классы:

| Было | Стало |
|------|-------|
| `app/schemas/ym_responses.py` | `app/schemas/platform_responses.py` |
| `YMSearchResponse` | `PlatformSearchResult` |
| `YMTrackBatch` | `PlatformTrackBatch` |
| `YMArtistTrackItem` | `ArtistTrackItem` |
| `YMArtistTracksPage` | `ArtistTracksPage` |
| `YMAlbumResponse` | `AlbumResult` |
| `YMPlaylistActionResult` | `PlaylistActionResult` |
| `YMLikesActionResult` | `LikesActionResult` |

В `app/schemas/__init__.py` оставить re-export alias-ы для обратной совместимости на время рефакторинга.

### 1.2 Репозитории

| Было | Стало |
|------|-------|
| `save_ym_metadata()` | `save_platform_metadata()` |
| `get_ym_metadata()` | `get_platform_metadata()` |

Python-класс `YandexMetadata` **оставить** (маппит на таблицу `yandex_metadata` в БД).

### 1.3 Фильтры — устранить нарушение слоёв

`discovery_service.py` импортирует `from app.clients.ym.filters import is_excluded_title`. Это нарушение: services → clients.

Перенести `is_excluded_title` в `app/core/utils/filters.py`. Добавить import-linter контракт:

```ini
[importlinter:contract:services-no-clients]
name = Services must not import client layer directly
type = forbidden
source_modules = app.services
forbidden_modules = app.clients
```

### 1.4 Выходной критерий

```bash
make check  # зелёный
rg "YMSearch|YMTrack|YMAlbum|YMPlaylist|YMLikes" app/schemas/ | wc -l  # 0 (кроме alias-ов)
```

---

## Фаза 2: Сервисный слой (~15 файлов)

*Средний риск. Ядро рефакторинга — переименование + вынос YM-логики в адаптер.*

### 2.1 Переименование параметров и полей

Во всех сервисах:

| Было | Стало |
|------|-------|
| `ym: MusicProvider` | `provider: MusicProvider` |
| `self._ym` | `self._provider` |

Затронутые файлы: `sync_service.py`, `discovery_service.py`, `import_service.py` + DI factories в `controllers/dependencies/services.py`.

### 2.2 Вынос YM-специфичной бизнес-логики

**Критически важно:** Не просто переименовать `_push_to_ym` → `_push_to_platform`. Эти методы содержат YM-бизнес-логику (формат `owner_id:kind`, `trackId:albumId`). Переименование без рефакторинга = ложная абстракция.

Стратегия: делегировать platform-specific операции **в адаптер через `MusicProvider` протокол**.

| Метод | Проблема | Решение |
|-------|----------|---------|
| `SyncService._extract_ym_kind()` | Парсит `platform_ids["yandex_music"]` | Вынести в `MusicProvider.parse_playlist_ref(platform_ids)` или оставить как private helper с чётким именем `_extract_platform_playlist_id()` |
| `SyncService._push_to_ym()` | Использует `settings.ym_user_id` для формирования playlist ID | `_push_to_platform()`, playlist ID формирует адаптер |
| `SyncService._collect_ym_track_ids()` | Формат `trackId:albumId` — YM-специфика | Переименовать в `_collect_platform_track_ids()`, формат ID оставить адаптеру |
| `_playlist_id(kind)` (в playlists.py) | `f"{settings.ym_user_id}:{kind}"` | Убрать — контроллер передаёт `playlist_id: str`, адаптер знает формат |
| `_provider_track_summary()` | Ключ `"ym_id"` в dict | Переименовать в `"platform_id"` или `"external_id"` |

### 2.3 Dict-ключи в ответах

`"ym_id"` → `"external_id"` в dict-ответах сервисов. Одновременно обновить все assert-ы в тестах и panel (если есть зависимости).

### 2.4 Legacy DI

Удалить `get_ym_client()` из `app/controllers/dependencies/external.py` (помечен как legacy). Проверить, что никто его не использует.

### 2.5 Выходной критерий

```bash
make check  # зелёный
rg "self\._ym\b|_push_to_ym|_collect_ym|_extract_ym|\"ym_id\"" app/services/ | wc -l  # 0
```

---

## Фаза 3: Контроллеры и инструменты (~18 файлов)

*Высокий риск — изменение MCP API (имена инструментов). Big bang rename.*

### 3.1 Перемещение директории

`app/controllers/tools/yandex/` → `app/controllers/tools/platform/`

### 3.2 Переименование инструментов

| Было | Стало | Обоснование |
|------|-------|-------------|
| `ym_search` | `search_platform` | Зеркалит `search_library` (локально vs платформа) |
| `ym_get_tracks` | `get_platform_tracks` | Зеркалит `get_track` (локальный) |
| `ym_artist_tracks` | `get_artist_tracks` | Добавляем `get_` для единообразия |
| `ym_get_album` | `get_album` | Нет локального аналога, префикс лишний |
| `ym_playlists` | `platform_playlists` | Dispatch-паттерн `noun_noun` как `track_feedback` |
| `ym_likes` | `platform_likes` | Симметрично с `platform_playlists` |
| `push_set_to_ym` | `push_set` | «Push» уже подразумевает remote |
| `expand_playlist_ym` | `expand_playlist` | Платформа определяется через DI |

### 3.3 Смена типа параметра

`kind: int` → `playlist_id: str` — универсальный идентификатор плейлиста. YM-адаптер сам преобразует `"42"` в `owner_id:42`.

### 3.4 Visibility tag

`ToolCategory.YM = "ym"` → `ToolCategory.PLATFORM = "platform"`. Обновить `dj_expert_session` промпт и все места с `enable_components(tags={"ym"})`.

### 3.5 Обновление промптов

Все файлы в `app/controllers/prompts/workflows/` ссылаются на tool names в текстах промптов — обновить.

### 3.6 Panel

Обновить 5 файлов в `panel/src/` с новыми именами инструментов. Это ~16 упоминаний `ym_`/`yandex`.

### 3.7 Выходной критерий

```bash
make check  # зелёный
rg -i "ym_search|ym_playlists|ym_get|ym_likes|ym_artist|push_set_to_ym|expand_playlist_ym" app/ panel/ | wc -l  # 0
```

---

## Фаза 4: Тесты, cleanup, import-linter (~15 файлов)

*Средний риск. Финализация.*

### 4.1 Тесты

| Было | Стало |
|------|-------|
| `make_ym_track()` | `make_legacy_ym_track()` (пометить) или удалить если не используется |
| `_make_ym_mock()` | `make_provider_mock()` |
| `ym=ym_mock` | `provider=provider_mock` |
| `ym_mock` | `provider_mock` (в acceptance conftest) |

### 4.2 `app/bootstrap/lifespans.py`

Убрать legacy `"ym_client"` ключ из lifespan context (если не используется).

### 4.3 Import-linter

Обновить контракты для новых путей. Усилить:

```ini
[importlinter:contract:services-no-clients]
name = Services must not import client layer directly
type = forbidden
source_modules = app.services
forbidden_modules = app.clients

[importlinter:contract:tools-no-ym-direct]
name = Tools must not import YM client directly
type = forbidden
source_modules = app.controllers
forbidden_modules = app.clients.ym
```

### 4.4 Финальный аудит

```bash
make check  # зелёный
# Ни одного упоминания ym/yandex вне app/clients/ym/ (кроме enum Provider.YANDEX_MUSIC):
rg -i "ym_|yandex" app/ --glob '!app/clients/ym/**' --glob '!app/providers/models.py' | grep -v "YANDEX_MUSIC" | wc -l  # 0
```

---

## НЕ трогаем (explicit exclusion list)

| Что | Почему |
|-----|--------|
| **Таблицы БД** (`yandex_metadata`, `spotify_metadata`, ...) | Имена таблиц — инвариант, переименование дорого и бессмысленно |
| **Данные в БД** | 23 926 записей, 1.6M track_sections — не трогаем |
| **`settings.ym_token`, `settings.ym_user_id`** и пр. `ym_*` env vars | Ломает `.env`, CI, Supabase secrets. Нулевая ценность. Доступ к ним вынести в `app/clients/ym/` — сервисы не должны знать про `settings.ym_*` |
| **`app/clients/ym/`** (7 файлов) | Это и есть YM-specific слой. Остаётся на месте |
| **Python-класс `YandexMetadata`** | Маппит на таблицу `yandex_metadata`. Можно добавить абстракцию поверх, но класс остаётся |
| **Enum `Provider.YANDEX_MUSIC`** | Это значение, не нейминг. Остаётся |

## Анализ БД (справка)

47 таблиц, 23 928 треков. Фундамент **уже мультиплатформенный:**

| Таблица | Что хранит | Статус |
|---------|-----------|--------|
| `providers` (4 записи) | Реестр: `yandex_music`, `spotify`, `beatport`, `soundcloud` | Generic |
| `track_external_ids` (23 926) | Связь трек ↔ платформа (`platform` = строка) | Generic |
| `raw_provider_responses` (23 926) | Кеш API-ответов через FK → `providers.id` | Generic |
| `yandex_metadata` (23 926) | YM-поля: `album_genre`, `cover_uri`, `label` | Наполнена |
| `spotify_metadata` (0) | Spotify-поля: `popularity`, `preview_url` | Схема готова |
| `spotify_audio_features` (0) | `danceability`, `energy`, `valence` | Схема готова |
| `beatport_metadata` (0) | `bpm`, `subgenre`, `preview_url` | Схема готова |
| `soundcloud_metadata` (0) | `playback_count`, `reposts_count` | Схема готова |
| `dj_playlists.platform_ids` | JSON: `{"yandex_music": "42"}` | Мультиплатформенное |

Per-platform таблицы **НЕ объединять** — у каждой платформы уникальные поля.

## Принципы

- **OOP**: классы с чёткой ответственностью, полиморфизм через `MusicProvider` протокол
- **SOLID**: Open/Closed (новый провайдер = новый адаптер, без изменений существующего кода), Dependency Inversion (сервисы зависят от `MusicProvider`, не от `YandexMusicClient`)
- **KISS**: не оверинжинирить. Проект имеет **1 активный провайдер** — абстракции должны быть оправданы, не спекулятивны
- **DRY**: убрать дубликаты, но НЕ создавать `PlatformMetadataRepository` / Strategy per platform — это overengineering для текущего масштаба
- **GoF**: Strategy (провайдеры через протокол), Adapter (`YandexMusicAdapter`), Repository (persistence). Не добавлять Template Method, Facade, Factory Method — YAGNI

## Справка

- Провайдеры: `app/providers/protocol.py`, `app/providers/models.py`, `app/providers/registry.py`
- Адаптер YM: `app/clients/ym/adapter.py`
- DI: `app/controllers/dependencies/`
- Правила: `@CLAUDE.md`, `@REQUIREMENTS.md`
- Архитектура: `@docs/architecture.md`, `@docs/tool-catalog.md`, `@docs/structure.md`

## Git-workflow рефакторинга

### Ветка и стратегия

Рефакторинг ведётся в ветке `refactor/provider-agnostic-naming`, отведённой от `main` после PR #99.

**Один коммит = одна логическая единица работы** (файл, группа связанных файлов, один тест-фикс). НЕ копить изменения — коммитить часто, с осмысленными сообщениями.

### Формат коммитов

```bash
<type>(<scope>): <what changed>

<why, if not obvious>
```

Типы: `refactor`, `fix`, `test`, `docs`, `chore`.
Scope: `schemas`, `services`, `tools`, `tests`, `panel`, `config`.

Примеры:
- `refactor(schemas): rename YM* response classes to platform-agnostic names`
- `refactor(services): rename self._ym → self._provider in sync/discovery/import`
- `fix(tools): move is_excluded_title to core/utils/filters`
- `test(tools): update test_ym_tools to use provider_mock`
- `docs(structure): update docs/structure.md after directory rename`

### Порядок работы по фазам

```text
Фаза N:
  1. Внести изменения
  2. make check (должен быть зелёным)
  3. git add -A && git commit
  4. Повторить для каждой логической единицы внутри фазы

После завершения фазы:
  5. git push -u origin refactor/provider-agnostic-naming
  6. Проверить, что push прошёл
  7. Перейти к следующей фазе
```

### Правила ветвления

- **НЕ создавать sub-branch на каждую фазу** — всё в одной ветке `refactor/provider-agnostic-naming`
- **НЕ мержить в main между фазами** — один PR в конце всех 4 фаз
- **Пушить после каждой фазы** — backup и возможность review
- При конфликтах с main: `git fetch origin && git rebase origin/main` (rebase, не merge)

### Финализация

После завершения всех 4 фаз:

```bash
make check                    # финальная проверка
git push origin refactor/provider-agnostic-naming
gh pr create --title "refactor: provider-agnostic naming and structure" --body "..."
```

PR должен содержать:
- Summary с перечислением изменений по фазам
- Grep-результаты из выходных критериев каждой фазы
- `make check` статус

После ревью — squash merge в main, удалить ветку.

### Откат

Если фаза сломала что-то фундаментально и `make check` не проходит после разумных усилий:

```bash
git log --oneline -20          # найти последний зелёный коммит
git reset --hard <commit>      # откатиться
```

Не бояться откатывать — коммиты частые, потеря минимальна.

---

## Результат (после всех 4 фаз)

1. Ни один файл вне `app/clients/ym/` не содержит `ym_` или `yandex` (кроме enum `Provider.YANDEX_MUSIC` и Python-класса `YandexMetadata`)
2. Добавление нового провайдера = создать адаптер + зарегистрировать в registry
3. Все инструменты принимают `playlist_id: str` вместо `kind: int`
4. `settings.ym_*` используются **только** внутри `app/clients/ym/`
5. `make check` — зелёный

---
name: ym-sync
description: "This skill should be used when the user asks to sync a playlist, push or pull from Yandex Music, search YM, manage YM playlists, or manage YM likes. Covers bidirectional sync, playlist management, ordered pushes, search and likes."
version: 1.1.0
---

# Yandex Music Sync Workflow

Синхронизация с YM через v1-диспетчеры (@docs/tool-catalog.md). Все namespace видимы со старта (v1.3.7+); `unlock_namespace` остаётся для audit-log и клиентов, честно обрабатывающих `tools/list_changed`.

## Read

- Поиск: `provider_search(provider="yandex", query="...", type="tracks", limit=20)`; `type ∈ tracks|albums|artists|playlists|all`.
- Трек: `provider_read(provider="yandex", entity="track", id=<ym_id>)` (`id` — int или str); батч: `entity="track_batch", params={"track_ids": [...]}` (legacy `ids` тоже принимается).
- Similar: `entity="track_similar", id=<ym_id>`; альбом: `entity="album"`; треки артиста: `entity="artist_tracks"`; плейлист: `entity="playlist", id="<owner>:<kind>"` или bare `<kind>`; списки: `entity="playlist_list" | "likes" | "dislikes"`.

## Mutate (`provider_write`)

Матрица операций — `YandexAdapter.operations_supported`: `playlist × {create, rename, set_description, delete, add_tracks, remove_tracks}`, `likes × {add, remove}`. `create_from_set` НЕ существует — пуш сета = `create` → `add_tracks`.

- **Create**: `provider_write(provider="yandex", entity="playlist", operation="create", params={"title": "..."})` → из ответа возьми `kind` (и `trackCount`).
- **Add tracks (порядок = продукт)**:
  `provider_write(..., operation="add_tracks", params={"playlist_id": "<kind>", "track_ids": [<ym ids по порядку>], "at": <текущий trackCount>})`
  - ⚠️ **Без `at` YM вставляет в позицию 0 (prepend)** — существующий плейлист получит треки в начало, порядок разрушен. Append = `at=<trackCount>`; свежесозданный плейлист: `at=0`.
  - Один вызов со списком сохраняет порядок списка. Bare track ids, без `albumId`.
  - `revision` опционален — адаптер сам резолвит текущую ревизию; после каждой мутации ревизия меняется (следующая мутация — с fresh-состоянием).
  - **Верифицируй ответ**: `trackCount` и `durationMs` должны сойтись с ожиданием — частичный пуш иначе останется незамеченным.
- **Remove — индексный диапазон, НЕ track_ids**: `operation="remove_tracks", params={"playlist_id": "<kind>", "from": <индекс вкл.>, "to": <индекс искл.>}` (YM-семантика delete-diff; позицию трека найди через `provider_read(entity="playlist")`). rename/set_description/delete — с `playlist_id`.
- Likes: `entity="likes", operation="add"|"remove", params={"track_ids": [...]}`.

## Bidirectional sync (`playlist_sync`)

- Diff: `playlist_sync(playlist_id=<local_id>, direction="diff", source="yandex", dry_run=true)`; `pull` (YM→local), `push` (local→YM). `dry_run=true` — превью без мутаций. Default `direction` — всегда `"diff"`.
- Поле `playlist.source_of_truth` (`local`|`yandex`) — информационное: sync-логика его НЕ читает, направление выбирай явно.

## Push a DJ Set to YM (проверенный путь)

1. `create` с `title` = имя сета → `kind`.
2. `add_tracks` одним вызовом: YM ids в порядке сета, `at=0` (плейлист пуст).
3. Верификация `trackCount`/`durationMs` из ответа.
   YM ids бери из `track_external_ids` или из `[<ym_id>]` в именах скачанных файлов.

## YM API Quirks

@docs/ym-api-guide.md. Ключевое: rate limit 1.5 с/вызов + backoff на 429; **budget общий на токен/IP** — фоновая качалка (usb_download и т.п.) делает параллельные write/интеграционные вызовы флаки с реальными 429; playlist-правки идут diff-форматом внутри адаптера; broken endpoints: artist brief-info (403), lyrics (400).

## Tips

- YM track id — строки в API; адаптер стрингифицирует числа сам.
- Батч-чтения (`track_batch`, `playlist_list`) дешевле цикла по одному id.
- `playlist_sync(direction="pull")` перед сборкой сетов из YM-плейлистов.

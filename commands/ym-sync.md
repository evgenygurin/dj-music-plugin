---
name: ym-sync
description: Sync playlists with Yandex Music — push, pull, search, manage YM playlists and likes
argument-hint: "[action] [playlist_name]"
---

Запусти skill `dj-music:ym-sync` со следующими аргументами: $ARGUMENTS

Если аргументы пустые — skill проведёт интерактивный workflow. Иначе используй их так:
- 1-й аргумент — `action` (sync, push, pull, search)
- 2-й аргумент — `playlist_name` или поисковый запрос

Действия:
- `sync` — двунаправленная синхронизация плейлиста
- `push` — выгрузить локальный плейлист в YM
- `pull` — загрузить YM плейлист локально
- `search` — поиск по каталогу YM

Примеры:
- `/ym-sync` — интерактивный workflow
- `/ym-sync push "Friday Night Set"` — выгрузка сета в YM
- `/ym-sync search "Amelie Lens"` — поиск по каталогу YM

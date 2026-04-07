---
name: expand-playlist
description: Expand a playlist with similar tracks from Yandex Music — discover, import, download, analyze
argument-hint: "[playlist_name] [target_count]"
---

Запусти skill `dj-music:expand-playlist` со следующими аргументами: $ARGUMENTS

Если аргументы пустые — skill проведёт интерактивный workflow. Иначе используй их так:
- 1-й аргумент — `playlist_name` (плейлист для расширения)
- 2-й аргумент — `target_count` (целевое количество треков)

Примеры:
- `/expand-playlist` — интерактивный workflow
- `/expand-playlist "TECHNO FOR DJ SETS" 100` — расширить до 100 треков

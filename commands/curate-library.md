---
name: curate-library
description: Classify tracks by mood/subgenre, audit quality, distribute to subgenre playlists, get stats
argument-hint: "[action] [playlist_name]"
---

Запусти skill `dj-music:curate-library` со следующими аргументами: $ARGUMENTS

Если аргументы пустые — skill проведёт интерактивный workflow. Иначе используй их так:
- 1-й аргумент — `action` (один из: classify, audit, distribute, stats)
- 2-й аргумент — `playlist_name` (если применимо)

Действия:
- `classify` — классифицировать треки по 15 поджанрам техно
- `audit` — аудит качества плейлиста (BPM, ключ, энергия)
- `distribute` — распределить треки по плейлистам поджанров
- `stats` — общая статистика библиотеки

Примеры:
- `/curate-library` — интерактивный workflow
- `/curate-library classify "Peak Time Techno"` — классификация треков плейлиста
- `/curate-library stats` — статистика библиотеки

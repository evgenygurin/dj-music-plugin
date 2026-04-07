---
name: deliver-set
description: Export and deliver a completed DJ set — M3U8, Rekordbox XML, JSON guide, cheat sheet, YM sync
argument-hint: "[set_name] [format]"
---

Запусти skill `dj-music:deliver-set` со следующими аргументами: $ARGUMENTS

Если аргументы пустые — skill проведёт интерактивный workflow. Иначе используй их так:
- 1-й аргумент — `set_name` (имя сета)
- 2-й аргумент — `format` (m3u8, rekordbox, json, cheatsheet, all)

Примеры:
- `/deliver-set` — интерактивный workflow
- `/deliver-set "Friday Night" rekordbox` — экспорт в Rekordbox XML
- `/deliver-set "Peak Time" all` — все форматы + YM sync

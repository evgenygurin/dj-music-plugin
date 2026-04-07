---
name: build-set
description: Build an optimized DJ set from a playlist using GA or greedy algorithm
argument-hint: "[playlist_name] [template] [duration_min]"
---

Запусти skill `dj-music:build-set` со следующими аргументами: $ARGUMENTS

Если аргументы пустые — skill проведёт интерактивный workflow. Иначе используй их так:
- 1-й аргумент — `playlist_name` (название исходного плейлиста)
- 2-й аргумент — `template` (один из: warm_up_30, classic_60, peak_hour_60, roller_90, progressive_120, wave_120, closing_60, full_library)
- 3-й аргумент — `duration_min` (целевая длительность в минутах)

Примеры:
- `/build-set` — интерактивный workflow
- `/build-set "Peak Time Techno" peak_hour_60` — сборка из плейлиста по шаблону
- `/build-set "My Tracks" classic_60 90` — 90-минутный classic set

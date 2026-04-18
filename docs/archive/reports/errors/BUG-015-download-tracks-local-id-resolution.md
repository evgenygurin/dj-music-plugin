# BUG-015: download_tracks не резолвит local track IDs

**Дата**: 2026-03-27
**Серьёзность**: Medium
**Статус**: Open

## Описание

`download_tracks(track_refs=["1", "2", "3"])` интерпретирует refs как YM track IDs, а не local track IDs. Скачиваются совершенно другие треки (Max Roach, Status Quo вместо Techno 2024).

## Воспроизведение

```text
download_tracks(track_refs=["1", "2", "3", "4", "5"])
→ downloaded: Max Roach - As_Long_as_You're_Living.mp3 (YM ID=1)
→ linked_to_library: 0

download_tracks(track_refs=["135055088", "121211014", "123713038"])
→ downloaded: Strenx - Techno_2024.mp3 (correct)
→ linked_to_library: 3
```

## Ожидаемое поведение

`track_refs` должен поддерживать:
- YM track IDs (строки типа "135055088")
- Local track IDs (числа или "local:1")
- Entity resolution как в других tools (import_tracks, manage_playlist)

## Связанный баг

BUG-016: при скачивании с local IDs → `linked_to_library: 0` (файлы не привязываются).

# BUG-006: Artist-track association not created during import

**Статус**: open
**Обнаружен**: 2026-03-26
**Компонент**: services/import_service.py (или track normalization)
**Severity**: high

## Симптом
После `import_tracks` артисты создаются в таблице `artists` (видны через `search(entity="artists")`), но связь с треками (many-to-many через `track_artists`) не заполняется.

`get_track(id=60)` → `artist_names: []`
`get_playlist(id=11, include_tracks=True)` → все треки с `artist_names: []`

При этом:
- `search(query="Giuliano Rodrigues", entity="artists")` → found (id=1)
- Track 60 — "Miami Underground" by Giuliano Rodrigues (из YM metadata)

## Root Cause
`import_tracks` создаёт Artist records и Track records, но не создаёт записи в `track_artists` (join table). Normalization (PR #24) создала артистов, но не связала их с треками.

## Воспроизведение
```text
import_tracks(track_refs=["139461715"], playlist_id=11)
get_track(id=60)  → artist_names: []
search(query="Giuliano Rodrigues", entity="artists")  → found
```

## Ожидаемое поведение
`get_track(id=60)` → `artist_names: ["Giuliano Rodrigues"]`

## Дополнительно
Track 51 title = "FOLUAL, Luca Antolini - The Race" — артисты встроены в title вместо нормализации в отдельные entity.

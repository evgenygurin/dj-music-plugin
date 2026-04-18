# BUG-014: get_set tracks view не включает artist_names

**Дата**: 2026-03-27
**Серьёзность**: Low (UX issue)
**Статус**: Fixed

## Описание

`get_set(view="tracks")` и `get_set(view="full")` возвращают треки без поля `artist_names`.
В то время как `list_tracks` и `get_playlist(include_tracks=True)` корректно возвращают `artist_names` для каждого трека.

## Воспроизведение

```text
get_set(id=1, view="tracks")
→ tracks[].{position, pinned, id, title, duration_ms}
# artist_names ОТСУТСТВУЕТ

get_playlist(id=1, include_tracks=True)
→ tracks[].{id, title, artist_names, bpm, key_camelot, duration_ms}
# artist_names ПРИСУТСТВУЕТ
```

## Ожидаемое поведение

`get_set` tracks view должен включать `artist_names` — это критичная информация для DJ при просмотре сета.

## Вероятная причина

Set tracks response model не включает `artist_names` в свою схему, или batch query для set items не делает join с artists.

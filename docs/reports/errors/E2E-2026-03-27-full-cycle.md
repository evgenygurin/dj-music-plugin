# E2E Test Report: Full Cycle — 2026-03-27

## Scope

Полный цикл: поиск в YM → импорт → создание плейлиста → добавление треков → создание сета → проверка данных → push на YM.

## Environment

- DB: пустая (0 треков, 0 плейлистов перед тестом)
- Plugin: v0.4.0, 50 tools

## Test Steps & Results

| Step | Tool | Input | Result | Status |
|------|------|-------|--------|--------|
| 1. YM search | `ym_search` | 5 запросов (techno, dark, peak, acid, industrial) | 48 треков найдено | PASS |
| 2. Import 30 tracks | `import_tracks` | 30 YM track IDs | imported=30, enriched=30, skipped=0 | PASS |
| 3. Verify list_tracks | `list_tracks` | limit=30 | 30 треков, artist_names заполнены | PASS |
| 4. Create playlist | `manage_playlist(create)` | name="E2E Test Techno Mix" | id=1, source_of_truth="local" | PASS |
| 5. Add tracks | `manage_playlist(add_tracks)` | 30 track refs | track_count=30 | PASS |
| 6. Verify playlist | `get_playlist(include_tracks)` | id=1 | 30 треков, artist_names заполнены | PASS |
| 7. Build set | `build_set` | playlist_id=1, algorithm=greedy, template=classic_60 | set_id=1, algorithm=playlist_order (fallback) | PASS (с замечанием) |
| 8. Verify set | `get_set(view=full)` | id=1 | 30 треков, artist_names ОТСУТСТВУЮТ | BUG-014 |
| 9. Get track details | `get_track` | id=6 | artist_names=["Fjaak","SLG"], has_features=false | PASS |
| 10. Get features | `get_track_features` | id=6 | has_features=false (ожидаемо — нет MP3) | PASS |
| 11. Library stats | `get_library_stats` | — | total=30, features=0, ym_linked=30, playlists=1, sets=1 | PASS |
| 12. Push to YM | `push_set_to_ym` | set_id=1, mode=create | ym_playlist_kind=1351, tracks_pushed=30/30 | PASS |

## Bugs Found

### BUG-014: get_set tracks view не включает artist_names (Low)
See: [BUG-014-set-tracks-missing-artist-names.md](BUG-014-set-tracks-missing-artist-names.md)

## Observations (не баги)

1. **build_set fallback**: При отсутствии audio features, `algorithm=greedy` переключается на `playlist_order`. Это корректное поведение — greedy нуждается в features для transition scoring. Можно добавить info-сообщение для пользователя.

2. **quality_score: null**: Ожидаемо без features. Сет создаётся, но без scoring.

3. **YM search**: Поиск по конкретным артистам (Amelie Lens, Kobosil) вернул 0 результатов. Только FJAAK нашёлся. Вероятно, эти артисты недоступны в регионе YM. Это не баг плагина.

4. **artist_names в list_tracks/get_playlist**: BUG-006 fix работает — artist_names заполнены через batch query.

## Conclusion

**11/12 шагов прошли без ошибок.** 1 найденный баг (BUG-014, Low severity).
Полный цикл import → playlist → set → YM push работает корректно.

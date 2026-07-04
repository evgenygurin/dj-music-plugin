---
name: expand-playlist
description: "This skill should be used when the user asks to expand a playlist, find similar tracks, add more tracks, discover new tracks, crate digging, import from Yandex Music, or fill gaps in a playlist. Covers seed-based discovery, import, download and analysis."
version: 1.1.0
---

# Expand Playlist / Crate Digging Workflow

Дискавери и импорт через v1-диспетчеры. Жёсткий порядок хвоста пайплайна: **import → download → analyze** (анализ требует скачанный audio_file).

## Steps

1. **Seeds → similar (лучший канал дискавери)**
   - Сиды = YM id ядровых треков стиля (из существующего сета/крейта; id видны в `[<ym_id>]` в именах скачанных файлов или через `track_external_ids`).
   - `provider_read(provider="yandex", entity="track_similar", id=<ym_track_id>)` — один сильный сид даёт ~15–18 релевантных кандидатов (лейбл-соседи, ремиксы). Free-text добор: `provider_search(provider="yandex", query="...", type="tracks", limit=20)`.

2. **Filter candidates по метаданным ответа**
   - Жанр альбома (`albums[0].genre`: techno/electronics — ок; ambient/dance — глазами), длительность (5–9 мин для DJ-tools), год, лейбл (Hypnus/Affin/PoleGroup-класс — сильный сигнал стиля.)
   - `r128.i` в ответе YM ≈ integrated LUFS — грубый энергетический фильтр ещё до импорта.

3. **Import (idempotent, батчем)**
   - `entity_create(entity="track", data={"external_ids": ["<ym_id>", ...], "source": "yandex", "playlist_id": <опц.>})`
   - Ответ: `imported` (новые) / `skipped` (уже в базе — дедуп по (source, external_id)) / `id_mapping` (ym_id → local_id). Не удивляйся высокому skip-проценту: BFS-библиотека уже покрывает много окрестностей.

4. **Download — ДО анализа**
   - `entity_create(entity="audio_file", data={"track_ids": [<local ids>]})` батчами 8–10; на таймауте проверь `entity_list(entity="audio_file", filters={"track_id__in": [...]})` и перевыпусти недостающие. Ключа `persistent` не существует.

5. **Analyze**
   - `entity_create(entity="track_features", data={"track_ids": [...], "level": 2|3})` — mood ляжет в features автоматически; L5 — только для треков, идущих в финальный сет (`entity_update(..., data={"level": 5})`).

6. **Verify coverage + добор до цели**
   - `entity_list(entity="track_features", filters={"track_id__in": [...]}, fields=["track_id","analysis_level","bpm","mood","energy_mean","integrated_lufs","spectral_centroid_hz"])` — и кури новичков feature-first (skill `curate-library`; там же NULL-ловушка L2-колонок при фильтрах).
   - Если `imported < цель` (высокий skip — норма) — вернись к шагу 1 со следующими сидами, пока не наберёшь N новых.

## Prompts

Для интерактивного end-to-end пути — промпты `expand_playlist_workflow` / `crate_digging_workflow` / `full_pipeline` (аргументы смотри в самом промпте через list_prompts, не по памяти).

## Tips

- YM rate budget общий на токен/IP — не запускай дискавери-сессию параллельно с массовой качалкой (реальные 429).
- `track_similar` может вернуть один и тот же трек в разных альбомах (сборники) — дедуп до импорта по `realId`.
- Track-строки статусны: `status=1` (archived) не берём в работу.
- Tool reference: @docs/tool-catalog.md; YM-квирки: @docs/ym-api-guide.md, @.claude/rules/ym.md.

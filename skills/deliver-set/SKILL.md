---
name: deliver-set
description: "This skill should be used when the user asks to deliver a set, export a set, finalize a set, do a rekordbox export, sync a set to YM, or generate a cheat sheet. Covers the generated-sets bundle (MP3 + M3U8 + cheatsheet + rekordbox XML), YM playlist push and backup."
version: 1.1.0
---

# Deliver DJ Set Workflow

Превратить готовую set_version в исполняемый пакет. Продукт доставки — папка `generated-sets/<Set-Name>/`: пронумерованные MP3 + `playlist.m3u8` + `CHEATSHEET.md` + `rekordbox.xml`, плюс YM-плейлист и бэкап.

## Steps

1. **Gate on review of the chosen version**
   - Состав и порядок версии: `local://sets/{id}/tracks` (или `entity_get(entity="set_version", id=<v>, include_relations=["items"])`).
   - `local://sets/{id}/review?version=<v>` — hard conflicts = стоп, чини через skill `build-set`.
   - Треки сета должны быть на **L5**: проверь `entity_list(entity="track_features", filters={"track_id__in": [...], "analysis_level__lt": 5})` — непустой результат = сначала download (шаг 2) + `entity_update(track_features, id, {"level": 5})`, затем **пересобери set_version** (L5 меняет ключи и picker-решения — иначе доставишь устаревший cheatsheet).

2. **Ensure MP3s on disk (до любых YM-push'ей — budget общий)**
   - `entity_create(entity="audio_file", data={"track_ids": [...]})` батчами 8–10; skip = строка есть И файл на диске (v1.6.2 перекачивает stale).
   - На MCP-таймауте UoW откатывается (файлы на диске, строк нет): `entity_list(entity="audio_file", filters={"track_id__in": [...]}, fields=["id","track_id","file_path"])` → перевыпусти `entity_create` только на недостающие ids; повторяй до полного покрытия. Пути бери из этого же ответа — НЕ `ls` по диску.

3. **Assemble the bundle** (`generated-sets/<Set-Name>/`)
   - Копируй MP3 в порядке сета с именами `NN. Artist - Title.mp3` (нумерация = позиция; этот формат обязателен для DB-матчинга rekordbox-экспортёра).
   - `playlist.m3u8` — `#EXTINF:<sec>,Artist - Title` + имя файла, в порядке сета.

4. **CHEATSHEET.md — исполняемый план, не голая таблица**
   - Источник: `local://sets/{id}/cheatsheet?version=<v>` (fx_type, bars, mix_in/out points, ключи с provenance, next_transition.overall).
   - Обязательный состав: шапка (set/version id, quality, длительность, BPM-диапазон, hard rejects), описание арки, таблица треков (BPM / Camelot / LUFS / mix-in / mix-out), и **per-transition план в терминах djay Pro AI (Neural Mix)**: пресет + бары + техника исполнения + на что смотреть (pitch заранее, слабейший стык, пик).
   - Пресеты движка = 7 djay Pro 5 built-ins (`NeuralMixTransition`): DRUM_SWAP / DRUM_CUT / FADE / ECHO_OUT / VOCAL_SUSTAIN / VOCAL_CUT / HARMONIC_SUSTAIN — переноси как есть. `FILTER_SWEEP` в рантайме НЕ существует; встретил его в legacy-cheatsheet старого сета — мапь в DRUM_SWAP, filter-knob подавай как опциональный ручной приём.

5. **Rekordbox XML — через боевой скрипт, не руками**
   - `set -a && . ./.env && set +a && uv run python scripts/export_folder_to_rekordbox_xml.py "generated-sets/<Set-Name>" --playlist-name "<Name>"`
   - Успех = `tracks_enriched == tracks_exported` (обогащение BPM/key/beatgrid/cues из БД матчится по имени файла `NN. Artist - Title.mp3`). Меньше — чини имена файлов, не игнорируй.
   - Импорт: rekordbox → Preferences → Advanced → rekordbox xml → путь к файлу.

6. **Push to Yandex Music (порядок — это продукт)**
   - Create: `provider_write(provider="yandex", entity="playlist", operation="create", params={"title": "<Set Name>"})` → возьми `kind` из ответа.
   - Add: `provider_write(..., operation="add_tracks", params={"playlist_id": "<kind>", "track_ids": [<ym ids в порядке сета>], "at": <текущий trackCount>})` — **без `at` YM вставляет в позицию 0 (prepend) и рушит порядок**; для свежего плейлиста `at=0`. YM id треков — из имён скачанных файлов (`[<ym_id>].mp3`); таблица `track_external_ids` не входит в EntityRegistry — читается только через Supabase MCP/SQL.
   - Верифицируй ответ: `trackCount` == N, `durationMs` ≈ длительность сета.

7. **Backup вне /tmp и вне репо**
   - MP3 живут в `/tmp/dj_audio/` (macOS чистит /tmp), `generated-sets/` в .gitignore. Копируй бандл в `~/Music/DJ-Sets/` (и в `~/DJ_USB_BUILD/_SETS/`, если идёт USB-кампания). Восстановление без бэкапа = полная перекачка под YM rate-limit.

## Tips

- `AudioFileCreate` принимает `track_id` | `track_ids` (ровно один) + опциональный `source` (default `"yandex"`) — ключа `persistent` не существует.
- Rekordbox-экспортёру нужен ffprobe (`/opt/homebrew/bin/ffprobe`) и локальный asyncpg-доступ (локаль/teleport; не облако).
- `deliver_set_workflow` prompt — канонический рецепт с conflict-гейтом, когда нужен интерактивный путь; ручной путь выше — когда собираешь бандл сам.
- YM rate budget общий на токен/IP: не гоняй доставку параллельно с массовой качалкой.

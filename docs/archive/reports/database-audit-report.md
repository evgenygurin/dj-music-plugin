# Database Audit Report

> Аудит SQLite базы `dj_music.db` — 2026-03-25
> 44 таблицы, 29 треков, 11 сетов

---

## Сводка

| Метрика | Значение |
|---------|----------|
| Таблиц всего | 44 |
| Таблиц с данными | 11 (25%) |
| Таблиц пустых | 33 (75%) |
| Треков | 29 (27 active, 2 archived) |
| Треков с features | 2 (7%) |
| Transitions scored | 1 |
| Referential integrity | OK (0 orphans) |

---

## 1. CRITICAL: Отсутствуют reference data

### `keys` — 0 строк (должно быть 24)

**Что:** Camelot wheel — 24 тональности для harmonic mixing.
**Влияние:** `TransitionScorer.harmonic_component()` не может использовать key_edges для точного скоринга. Работает через `camelot.py` (in-memory), но DB-таблица пуста.
**Причина в коде:** Нет seed-функции. Alembic миграция создаёт таблицу, но не заполняет. `app/core/constants.py:CAMELOT_KEYS` содержит данные in-memory, но в DB не записывает.
**Fix:** Добавить data migration или seed в `db_lifespan`.

### `key_edges` — 0 строк

**Что:** Граф совместимости ключей.
**Влияние:** То же — код использует `camelot_distance()` из Python, не из DB.
**Причина:** Не реализована seed-функция.

### `providers` — 0 строк (должно быть 4)

**Что:** yandex_music, spotify, beatport, soundcloud.
**Влияние:** `provider_track_ids` таблица не может ссылаться на providers. `track_external_ids` работает напрямую (строковое поле platform).
**Причина:** Нет seed-функции.

---

## 2. HIGH: Неполные audio features

### Только 2 из 29 треков проанализированы (track_id: 24, 25)

**Заполненные поля (12 из 47):**
- `bpm`, `bpm_confidence`, `bpm_stability` — tempo
- `key_code`, `key_confidence` — тональность
- `integrated_lufs` — громкость
- `energy_mean` — энергия
- `spectral_centroid_hz`, `spectral_flatness` — спектр
- `hp_ratio`, `onset_rate`, `kick_prominence`, `pulse_clarity`, `hnr_db` — ритм

**Пустые поля (35 из 47):**
- Loudness: `short_term_lufs_mean`, `momentary_max`, `rms_dbfs`, `true_peak_db`, `crest_factor_db`, `loudness_range_lu`
- Energy: `energy_max`, `energy_std`, `energy_slope`, 7 band fields, ratios
- Spectral: `rolloff_85`, `rolloff_95`, `flux_mean`, `flux_std`, `slope`, `contrast`
- Key: `atonality`, `chroma_entropy`, `chroma_vector`
- Rhythm: `mfcc_vector`, `variable_tempo`
- Classification: `mood`, `mood_confidence`
- Pipeline: `pipeline_run_id`

**Причина в коде:**
1. `analyze_track` (audio.py) вызывает pipeline, pipeline пускает доступные анализаторы
2. `LoudnessAnalyzer`, `EnergyAnalyzer`, `SpectralAnalyzer` — core analyzers, но они заполняют часть полей. Анализ запускался с неполным набором анализаторов (только librosa-based: BPM, Key, Beat, MFCC)
3. **Loudness/Energy/Spectral analyzers видимо не отработали** — возможно файлы были в /tmp и удалились к моменту core analysis
4. `mood`, `mood_confidence` — **не заполняются analyze_track**. Mood classifier — отдельный tool `classify_one_track` / `classify_mood`. Пайплайн не вызывает классификатор автоматически.

**`feature_extraction_runs` — 0 строк** (хотя 2 трека проанализированы):
- Причина: `analyze_one_track` (audio_atomic.py:84-91) создаёт `FeatureExtractionRun`, но `analyze_track` (audio.py) — нет. Треки 24-25 вероятно были проанализированы через прямую вставку или старый код.

---

## 3. HIGH: Transitions почти не вычислены

### 1 transition из ~800 возможных пар

**Единственный transition:** track 24 → 25, overall_quality = 0.809

**Пустые поля в transition:**
- `from_section_id`, `to_section_id` — NULL (track_sections таблица пуста)
- `overlap_ms` — NULL
- `key_distance_weighted`, `low_conflict_score` — NULL

**Причина:** `score_transitions(mode="set")` не вызывался на полных сетах. Единственный transition создан через `score_transitions(mode="pair")`.

**`transition_candidates` — 0 строк:**
- Pre-computed candidate pairs для быстрого скоринга не генерируются.
- Причина: нет кода для batch candidate generation.

---

## 4. MEDIUM: Set items без transition data

### 72 set_items — все поля mix/transition пустые

| Поле | NULL count | Причина |
|------|-----------|---------|
| `transition_id` | 72/72 | Transitions не вычислены |
| `in_section_id` | 72/72 | Sections не определены |
| `out_section_id` | 72/72 | Sections не определены |
| `mix_in_point_ms` | 72/72 | Mix points не установлены |
| `mix_out_point_ms` | 72/72 | Mix points не установлены |
| `planned_eq` | 72/72 | EQ не планировался |
| `notes` | 72/72 | DJ notes не добавлены |

**Причина:** `build_set` создаёт set_items с ordering, но не вычисляет transitions и mix points. Это отдельный шаг (deliver_set или score_transitions).

---

## 5. MEDIUM: Tracks data quality

### 14 из 29 треков без duration_ms

| track_id | title | duration_ms |
|----------|-------|------------|
| 6-11 | Дубликаты треков 1-5 | NULL |
| 12-23 | Тестовые треки | NULL |
| 24-28 | YM-downloaded | Заполнены |
| 29 | E2E Test Track | 300000 |

**Причина:** Треки 6-23 создавались через `manage_tracks(action=create)` без указания duration. Треки 24-28 импортированы из YM с metadata.

### 5 дубликатов по title

| Оригинал (id) | Дубликат (id) | Title |
|---------------|---------------|-------|
| 1 | 6 | Amelie Lens - Exhale |
| 2 | 7 | 999999999 - Pulse |
| 3 | 8 | FJAAK - Acid Warrior |
| 4 | 9 | Kobosil - 44 |
| 5 | 10 | Dax J - Reign In Blood |

**Причина:** Тестовые вызовы `manage_tracks(create)` без проверки дубликатов. Код `TrackService.create()` не проверяет уникальность title.

### Playlist 1 — sort_index начинается с 1, не с 0

Все другие плейлисты: 0-based. Playlist 1: 1-based.
**Причина:** Ручная вставка или первая версия `add_track()` использовала 1-based индексацию.

### `added_at` — NULL во всех 21 playlist items

**Причина в коде:** `PlaylistRepository.add_track()` (playlist.py:29-33) создаёт `PlaylistItem` без `added_at`. Модель (`PlaylistItem.added_at`) — nullable, без default.

---

## 6. MEDIUM: Set metadata неполная

| Поле | Заполнено | Пусто | Причина |
|------|-----------|-------|---------|
| `template_name` | 2/11 | 9 | Создавались без шаблона |
| `target_duration_ms` | 1/11 | 10 | Не указывался при создании |
| `target_energy_arc` | 0/11 | 11 | Не реализовано в `manage_set(create)` |
| `ym_playlist_id` | 0/11 | 11 | Не синхронизировались |
| `quality_score` (versions) | 0/15 | 15 | Transitions не скорировались |
| `generator_run_meta` (versions) | 0/15 | 15 | `build_set` не сохраняет метаданные алгоритма |

**Причина `generator_run_meta`:** `build_set` (sets.py) создаёт `SetVersion` с `label` и `quality_score`, но `generator_run_meta` (JSON с настройками GA/greedy) не заполняется.

---

## 7. LOW: Пустые таблицы (33 штуки)

### Reference data (3 таблицы)
`keys`, `key_edges`, `providers` — нет seed-функции

### Relationship tables (4 таблицы)
`track_artists`, `track_genres`, `track_labels`, `track_releases` — треки создаются без метаданных (только title)

### DJ library features (4 таблицы)
`dj_beatgrids`, `dj_beatgrid_change_points`, `dj_cue_points`, `dj_saved_loops` — не импортируются из DJ софта

### Audio analysis output (4 таблицы)
`feature_extraction_runs` — analyze_track не создаёт записи (только analyze_one_track)
`track_sections` — StructureAnalyzer не реализован
`embeddings` — не реализовано
`timeseries_references` — не реализовано

### Platform metadata (8 таблиц)
`yandex_metadata`, `spotify_*` (5), `beatport_metadata`, `soundcloud_metadata` — import_tracks не заполняет platform metadata

### Infrastructure (3 таблицы)
`raw_provider_responses`, `provider_track_ids`, `app_exports` — не используются текущим кодом

---

## 8. Referential Integrity — OK

| Проверка | Результат |
|----------|-----------|
| playlist_items → tracks | 0 orphans |
| set_items → tracks | 0 orphans |
| set_items → set_versions | 0 orphans |
| audio_features → tracks | 0 orphans |
| external_ids → tracks | 0 orphans |
| Range: BPM 20-300 | PASS |
| Range: key_code 0-23 | PASS |
| Range: status 0-1 | PASS |

---

## 9. Рекомендации по приоритету

### Приоритет 1 (blocking)
1. **Seed reference data** — добавить в db_lifespan или data migration: 24 keys, key_edges, 4 providers
2. **Заполнить duration_ms** — для 14 треков через YM API (`get_tracks` возвращает `durationMs`)

### Приоритет 2 (data quality)
3. **Добавить `added_at = func.now()`** default в `PlaylistItem` модели или в `add_track()`
4. **Добавить deduplication check** в `TrackService.create()` — проверка по title
5. **`build_set` → сохранять `generator_run_meta`** (algorithm, params, timestamp)

### Приоритет 3 (completeness)
6. **`analyze_track` → auto-classify** — вызывать MoodClassifier после анализа
7. **`import_tracks` → заполнять `yandex_metadata`** таблицу
8. **`feature_extraction_runs`** — создавать записи в composite `analyze_track`

---

*Отчёт сгенерирован 2026-03-25 на основе прямого SQL-аудита + анализа кода.*

# MCP Tools Test Report — После рефакторинга

**Дата**: 2026-04-07
**Worktree**: determined-ellis
**Задача**: Импортировать и проанализировать (L3) 60 треков из плейлиста "TECHNO FOR DJ SETS" пачками по 20

## Цель тестирования

Проверить работоспособность MCP tools после рефакторинга путём прямого вызова в реальном workflow.

## Методология

1. Вызов tools напрямую (без помощи скиллов)
2. Внимательный разбор ответов (даже success-ответы могут содержать предупреждения/ошибки)
3. Запись всех найденных проблем в этот файл

## Обнаруженные ошибки

### АРХИТЕКТУРНАЯ ОШИБКА #0: `import_tracks` лишний шаг

**Серьёзность**: Высокая (UX/архитектура)
**Tool**: `import_tracks`
**Симптом**: Текущий workflow требует двух шагов:
1. `import_tracks(track_refs)` — создаёт пустые `Track` записи (`title="YM:12345"`)
2. `analyze_batch(track_ids)` — скачивает, анализирует, сохраняет фичи

**Что должно быть**: `analyze_batch` должен сам создавать `Track` запись для YM ID если её нет. Тогда workflow:
- `analyze_batch(track_refs=["54486493", ...], level=3)` — всё в один вызов

**Обоснование**: если мы знаем что хотим анализировать трек, нет смысла делать "пустую" запись отдельно. Создание Track + анализ — это одна логическая операция.

**Файлы**: `app/mcp/tools/audio.py`, `app/services/tiered_pipeline.py`

---

### ОШИБКА #1: `ym_playlists action=get_tracks` не имеет limit/offset

**Серьёзность**: Высокая
**Tool**: `ym_playlists`
**Action**: `get_tracks`
**Симптом**: При вызове на большой плейлист (1377 треков) ответ занимает 106206 символов и превышает лимит токенов MCP-клиента, требуя сохранения в файл.

**Воспроизведение**:
```json
{"action": "get_tracks", "kind": 1280}
```

**Что должно быть**:
- Параметры `limit: int = 50` и `offset: int = 0` или `cursor`
- Или: возвращать только `track_ids` без полных метаданных по умолчанию (через `view: "ids" | "full"`)
- Или: пагинация по умолчанию

**Файл**: `app/mcp/tools/yandex/playlists.py`

**Workaround**: Сохранить весь ответ в файл и парсить через jq.

---

### ОШИБКА #2 (КРИТИЧНАЯ): `import_tracks` параметры `playlist_id` и `auto_analyze` — фейк

**Серьёзность**: Критическая (silent failure / dead code)
**Tool**: `import_tracks`
**Файл**: `app/mcp/tools/import_download.py:51-54`

**Симптом**: Параметры `playlist_id` и `auto_analyze` декларированы в схеме, но НЕ ВЫЗЫВАЮТ никакой логики:

```python
if playlist_id:
    result["playlist_note"] = "Use manage_playlist(add_tracks) to add to playlist"
if auto_analyze:
    result["auto_analyze_note"] = "Use analyze_batch to trigger audio analysis"
```

Они просто добавляют note в результат. Это вводит в заблуждение пользователя — он передаёт `playlist_id=N` ожидая что треки добавятся в плейлист, но ничего не происходит.

**Что должно быть**:
- Либо удалить эти параметры из tool signature
- Либо реализовать реальную логику: при playlist_id вызывать `manage_playlist.add_tracks`, при auto_analyze запускать `analyze_batch`

---

### ОШИБКА #3: `import_tracks` не возвращает локальные track IDs

**Серьёзность**: Средняя (UX)
**Tool**: `import_tracks`
**Файл**: `app/services/import_service.py:46-83`

**Симптом**: `ImportService.import_tracks` строит `id_mapping: dict[str, int]` (YM → local), но НЕ возвращает его. Возвращается только статистика: `{imported, skipped, enriched, total_refs}`.

**Последствия**: после импорта невозможно узнать какие локальные ID соответствуют импортированным трекам. Приходится делать дополнительные запросы (filter_tracks, search).

**Что должно быть**: возвращать `id_mapping` или массив `imported_tracks: [{ym_id, local_id}]`.

---

### ОШИБКА #4: `get_track` не находит трек по `query="YM:54486493"`

**Серьёзность**: Средняя
**Tool**: `get_track`
**Симптом**: Хотя `import_tracks` создаёт треки с `title="YM:{ym_id}"`, поиск через `get_track(query="YM:54486493")` возвращает "not found". Search не находит треки по их title.

**Причина**: вероятно search ищет по более «человеческим» полям (title после enrichment, artist), и literal "YM:" prefix не индексируется.

**Что должно быть**: либо search должен находить такие треки, либо отдельный параметр `external_id` для поиска по yandex_music.

---

### ОШИБКА #5 (ПОДТВЕРЖДЕНА): BPM clusterized в две константы 123.05 и 129.2

**Серьёзность**: КРИТИЧНАЯ (data quality)
**Tool**: `BPMDetector` analyzer (`app/audio/analyzers/bpm.py` или библиотека librosa wrapper)
**Симптом**: Из 20 проанализированных треков:

- **8 треков с BPM = 123.05** (точно):
  - 147 Maksim Dark — Modest
  - 148 Maksim Dark — Boogeyman
  - 150 Maksim Dark — Routine
  - 151 Maksim Dark — Andromeda
  - 157 SDK — Minimal Terror
  - 158 Cognak — 126
  - 160 Digital Pulse — Saturno
  - 166 Vinicius Honorio — Dreamcatcher

- **12 треков с BPM = 129.2** (точно):
  - 146 DRVSH — Soul Spiritism
  - 152 Pelly Benassi — 528
  - 153 Chriss Jay — Danger
  - 154 Klanglos — Dance All Night
  - 155 Lowerzone — Spectrum Probe
  - 156 Dino Maggiorana — Pendular
  - 159 Akdoxx — Belatrix
  - 161 Min & Mal — This Is Hot
  - 162 David Sellers — Shot To Nothing
  - 163 Kreisel & Monococ — Protocol
  - 164 Martin Costas — Timeless
  - 165 Konstantinus — Pachatata

**Анализ**: BPM детектор выдаёт всего 2 значения для 20 разных треков от разных артистов. Это **детерминированный fallback** или **сломанный analyzer**. Реальные значения BPM техно треков должны быть разбросаны в диапазоне 120-140 с десятыми долями.

**Гипотеза причины**:
1. BPM detector использует stub/fallback логику и возвращает константу
2. Или: bpm_detector работает на коротком клипе (60 sec) который содержит только metronome click
3. Или: librosa BeatTrack вызвается с дефолтными параметрами и хитит local minimum

**Что должно быть**: BPM значения должны быть уникальными для разных треков с погрешностью ±0.5 BPM. Например: 124.3, 126.7, 128.1, 132.4, ...

**Требует расследования**:
- `app/audio/analyzers/bpm.py` — реализация
- `app/audio/level_config.py` — какие analyzers L3 включает
- Проверить librosa version и параметры (`hop_length`, `start_bpm`, `tightness`)

#### КОРНЕВАЯ ПРИЧИНА (НАЙДЕНА): Frame quantization

После полного анализа 60 треков (3 пачки), наблюдаемое распределение BPM:
| BPM | Кол-во треков | % |
|-----|---------------|---|
| 83.35 | 1 | 1.7% |
| 123.05 | 27 | 45% |
| 129.2 | 29 | 48.3% |
| 136.00 | 3 | 5% |

**Всего 4 уникальных BPM на 60 треков** в плейлисте Techno (где должны быть 124-138 BPM).

Все 4 значения **точно совпадают** с формулой `60 * sr / (hop_length * frames_per_beat)` для целого числа `frames_per_beat`:

```text
sr=22050, hop_length=512:
  19 frames/beat → 136.00 BPM (наблюдается, 3 трека)
  20 frames/beat → 129.20 BPM (наблюдается, 29 треков)
  21 frames/beat → 123.05 BPM (наблюдается, 27 треков)
  22 frames/beat → 117.45 BPM (не наблюдается)
  31 frames/beat →  83.35 BPM (наблюдается, 1 трек, half-time)
```

**Источник**: `librosa.beat.beat_track()` возвращает темп с точностью до целого числа `frames_per_beat`. С текущими настройками `app/config.py:96-97` (`audio_hop_length=512`, `audio_sample_rate=22050`) в техно-диапазоне 120-140 BPM существует **всего 4 возможных значения** BPM:

| frames | BPM |
|--------|-----|
| 19 | 136.00 |
| 20 | 129.20 |
| 21 | 123.05 |
| 22 | 117.45 |

**Между 123.05 и 129.2 разрыв 6.15 BPM** — все реальные треки в этом диапазоне будут округлены к одному из этих двух значений.

#### Последствия для DJ scoring

1. **Hard reject порог `bpm_diff > 10`** становится бессмысленным:
   - 123 vs 129 = 6.15 BPM (всегда compatible)
   - 123 vs 136 = 12.95 BPM (всегда reject)
   - Нет промежуточных вариантов

2. **Soft scoring через Gaussian** теряет всю детальность — все треки кластеризуются.

3. **47 тонких BPM features** в `track_audio_features_computed.bpm` фактически бинарные/тернарные.

4. **Все анализаторы зависящие от BPM** (groove, beat_histogram, transition_intent) получают мусорные данные.

#### Возможные исправления

| Решение | Плюсы | Минусы |
|---------|-------|--------|
| `audio_hop_length: 256` | 2x больше точек, меньше изменений | 2x медленнее, больше памяти |
| `audio_sample_rate: 44100` | Стандартный, ещё точнее | 2-4x медленнее, больше памяти |
| `librosa.feature.tempo()` | Sub-frame precision | Может быть медленнее |
| `essentia.RhythmExtractor2013` | Industry standard, ±0.05 BPM | Доп. dependency, требует essentia |
| Comb-filter post-processing | Без изменения hop | Доп. сложность |

**Рекомендация**: проверить с `essentia.RhythmExtractor2013` (уже есть в P2 analyzers по CLAUDE.md). Возможно, нужно перенести его в L3.

#### Воспроизведение

```python
# Confirm via CLI:
python3 -c "
sr, hop = 22050, 512
for f in range(15, 35):
    print(f'{f} frames → {60*sr/(hop*f):.2f} BPM')
"
# Output matches exactly:
# 19 → 136.00
# 20 → 129.20
# 21 → 123.05
# 31 →  83.35
```

#### Дополнительные подозрительные сигналы

- `bpm_confidence = 1.0` (точно) для всех 60 треков — fallback значение
- `bpm_stability = 0.94-0.95` (узкий разброс) — детерминированный
- L3 анализ 20 треков моментальный (~10 сек) — подозрительно быстро для librosa beat_track + key + spectral на полных файлах

---

## Лог вызовов

### Шаг 1: Подготовка

- `list_platforms`: ✅ OK. Yandex Music available, 60 linked tracks (от прошлого тестирования)
- `list_playlists`: ✅ OK. 1 локальный плейлист (`__test_v4__`)
- `ym_playlists action=list`: ✅ OK. Найден `TECHNO FOR DJ SETS` kind=1280 (1377 треков)
- `ym_playlists action=get_tracks kind=1280`: ⚠️ Ошибка #1 (oversized response)

### 60 треков для теста (первые из плейлиста)

```text
Пачка 1: 54486493, 65856581, 128409358, 56896321, 89160317, 56994334, 95604567, 63588001, 58697078, 53973295, 56971107, 4387122, 141085558, 110749980, 4639919, 68065043, 63964931, 59609701, 61297756, 55531573
Пачка 2: 147877083, 56347213, 31192058, 71130869, 35304068, 54118999, 54826851, 55470424, 56746386, 56764516, 54481897, 96534206, 70922942, 71570074, 83452767, 55304403, 43830177, 56937615, 82183857, 55724429
Пачка 3: 42427889, 71723009, 100370149, 110286759, 148457263, 58255074, 56239886, 56186267, 54905893, 140467678, 89299080, 56438654, 64637189, 91436751, 73369228, 68923352, 113698674, 97466396, 54256640, 57259873
```

### Шаг 2: Workflow без import_tracks

После замечания пользователя — `import_tracks` лишний шаг, основной workflow это `analyze_batch` пачками.
В БД уже было 60 связанных YM треков (`linked_tracks=60`), из них 20 с features и 40 без.

Использовал реальные локальные ID:
- **Пачка 1**: треки 167-186 (20 без features)
- **Пачка 2**: треки 187-206 (20 без features)
- **Пачка 3**: треки 146-148, 150-166 (20 уже с features, force=true)

Tools работают:
- `unlock_tools(action="unlock", category="audio")` → ✅ OK
- `unlock_tools(action="status")` → ✅ shows audio enabled

### Шаг 3: analyze_batch (3 пачки × 20)

| Пачка | Параметры | Результат | Время |
|-------|-----------|-----------|-------|
| 1 | track_ids=[167..186], level=3, batch_size=20 | `total=20 completed=20 failed=0` | ~10с |
| 2 | track_ids=[187..206], level=3, batch_size=20 | `total=20 completed=20 failed=0` | ~10с |
| 3 | track_ids=[146..166 без 149], level=3, force=true | `total=20 completed=20 failed=0` | ~10с |

**Все 60/60 успешно**, но (см. ОШИБКА #5/КОРНЕВАЯ ПРИЧИНА) BPM дискретизирован на 4 значения, и время выполнения подозрительно низкое для librosa анализа 60 треков с download.

### Что РАБОТАЕТ ✓

1. **`unlock_tools`** — корректно разблокирует категории, status показывает effective state
2. **`get_track_features`** — возвращает структурированный ответ с tempo/loudness/energy/spectral/key/rhythm/mood
3. **`analysis_level: 3`** — корректно проставлен в БД после analyze_batch
4. **MoodClassifier** — работает: разные треки получают разный mood (`detroit`, `progressive`, `melodic_deep`, etc.)
5. **Key detector** — даёт разные key_codes (5, 14, 19, ...) и confidence (0.7-0.83), не fallback
6. **Loudness, energy, spectral** — значения уникальны для каждого трека (LUFS -11..-13, energy 0.29..0.51, centroid 2200..2700 Hz)
7. **`analyze_batch`** через TieredPipeline — корректно использует temp_download (lifecycle через async context manager)
8. **`force=true`** — пересчитывает уже проанализированные треки

### Что НЕ РАБОТАЕТ ✗

1. **BPM detector** — frame quantization, всего 4 значения BPM на 60 треков
2. **`bpm_confidence` всегда 1.0** — fallback, не реальный confidence
3. **`import_tracks` playlist_id/auto_analyze** — фейковые параметры
4. **`import_tracks`** не возвращает локальные ID
5. **`ym_playlists action=get_tracks`** — нет limit/offset (oversized для больших плейлистов)
6. **`get_track(query="YM:...")`** — не находит трек по external_id формату
7. **`filter_tracks sort_by="id_desc"`** — параметр игнорируется, всегда сортирует по id_asc

---

## Сводная таблица багов

| # | Tool | Серьёзность | Симптом |
|---|------|-------------|---------|
| 0 | `import_tracks` (архитектура) | Высокая | Лишний шаг — `analyze_batch` должен сам создавать Track |
| 1 | `ym_playlists` | Высокая | `get_tracks` без limit/offset → oversized response |
| 2 | `import_tracks` | КРИТИЧЕСКАЯ | `playlist_id` и `auto_analyze` параметры — фейк |
| 3 | `import_tracks` | Средняя | Не возвращает локальные `track_id` |
| 4 | `get_track` | Средняя | Не ищет по `query="YM:12345"` |
| 5 | **BPMDetector** | **КРИТИЧЕСКАЯ** | **Frame quantization → 4 значения BPM на 60 треков** |
| 6 | `filter_tracks` | Низкая | `sort_by` параметр игнорируется |

---

## Финальные выводы

**Хорошее**:
- MCP tools архитектурно работают: dispatch, unlock, DI, structured output
- `analyze_batch` + TieredPipeline корректно интегрированы
- Mood classifier, key detector, loudness, energy, spectral — все работают
- Pagination, filter, get_track_features структурированы

**Критическое (требует немедленного внимания)**:
1. **BPM detector frame quantization** (ОШИБКА #5) — все scoring/sorting/transition tools работают на garbage BPM. Это блокер для production использования (123 vs 129 BPM diff = 6.15, всегда compatible; 123 vs 136 = 12.95, всегда reject).
2. **`import_tracks` фейковые параметры** (ОШИБКА #2) — silent failure, нужно либо реализовать, либо удалить.

**Архитектура**:
- `analyze_batch` должен принимать YM track refs напрямую и сам создавать Track запись (ОШИБКА #0).

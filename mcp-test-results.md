# MCP Tools — результаты тестирования после рефакторинга

Дата: 2026-04-07
Задача: получить 60 треков из TECHNO FOR DJ SETS (YM), добавить в БД, проанализировать до L3 → L4 → L5.

---

## Статус инструментов

| Инструмент | Статус | Примечания |
|-----------|--------|-----------|
| `unlock_tools` | ✅ OK | audio категория разблокирована |
| `ym_playlists action=list` | ✅ OK | Вернул полный список плейлистов |
| `ym_playlists action=get_tracks` | ⚠️ Нет limit | Не поддерживает параметр `limit` — вернул все 1377 треков, результат обрезан (106k символов), сохранён во временный файл |
| `ym_playlists action=get_tracks limit=60` | ❌ Ошибка | `Unexpected keyword argument` — параметр `limit` не предусмотрен |
| `import_tracks` | ✅ OK | Все 60 треков уже были в БД (`skipped=60`) |
| `analyze_batch` с YM ID (строки) | ❌ Ошибка | `Internal error` — инструмент ожидает локальные integer ID, не YM string ID |
| `analyze_batch` L3 с local IDs | ✅ OK | `skipped=60` — все треки уже были на `analysis_level=4` |
| `analyze_batch` L4 пачка 1 | ✅ OK | `completed=18, skipped=2` |
| `analyze_batch` L4 пачка 2 | ✅ OK | `completed=20` |
| `analyze_batch` L4 пачка 3 | ✅ OK | `completed=20` |
| `analyze_batch` L5 пачка 1 | ✅ OK | `completed=19, skipped=1` |
| `analyze_batch` L5 пачка 2 | ✅ OK | `completed=20` |
| `analyze_batch` L5 пачка 3 | ✅ OK | `completed=20` |
| `get_track_features` | ✅ OK | Возвращает корректные данные |
| `build_set` | ✅ OK | GA, quality_score=0.69, 60 треков |
| `score_transitions` | ✅ OK | avg=0.77, hard_conflicts=4→2 после rebuild |
| `rebuild_set` | ✅ OK | Уменьшил hard_conflicts с 4 до 2 |
| `suggest_next_track` | ❌ pool=0 | Пул пуст — все треки в сете, кандидатов нет |

---

## Вызовы

### 1. unlock_tools (audio)

```json
{"action": "unlock", "category": "audio"}
→ {"action":"unlocked","categories":["audio"]}
```

**Результат:** OK
**Ошибки:** нет

---

### 2. ym_playlists action=list

```json
{"action": "list"}
→ Массив 200+ плейлистов
```

**Результат:** OK — найден TECHNO FOR DJ SETS `kind=1280`, 1377 треков
**Ошибки:** нет

---

### 3. ym_playlists action=get_tracks (TECHNO FOR DJ SETS)

```json
{"action": "get_tracks", "kind": 1280}
→ 106,206 символов — превышает лимит токенов
→ Сохранён в tool-results/*.txt
```

**Результат:** ⚠️ Данные получены, но ответ слишком большой
**Ошибки:** нет (обходной путь: jq на сохранённом файле)

#### Попытка с limit:

```json
{"action": "get_tracks", "kind": 1280, "limit": 60}
→ Internal error: Unexpected keyword argument [limit]
```

**Ошибка:** Параметр `limit` не поддерживается в `ym_playlists action=get_tracks`
**Решение:** Использовать `jq '.track_ids[0:60]'` на сохранённом файле результата

---

### 4–6. import_tracks (пачки по 20)

```json
{"track_refs": ["54486493", ...20 YM IDs...], "auto_analyze": false}
→ {"imported":0,"skipped":20,"enriched":0,"total_refs":20}
```

**Результат:** Все 60 треков уже в БД
**Ошибки:** нет

---

### 7. analyze_batch с YM IDs (первая попытка)

```json
{"track_ids": ["54486493","65856581",...], "level": 3, "batch_size": 20}
→ Internal error: Error calling tool 'analyze_batch'
```

**Ошибка:** `analyze_batch` принимает только локальные integer ID, не YM string ID.
**Решение:** SQL-запрос к БД для резолвинга YM ID → local ID

```python
SELECT track_id FROM yandex_metadata WHERE yandex_track_id = ANY($1::text[])
→ [146, 147, 148, 150, ..., 206]  # 60 треков, пропуск: 149
```

---

### 8–10. analyze_batch L3/L4/L5

| Уровень | Пачка | IDs | completed | skipped | failed |
|---------|-------|-----|-----------|---------|--------|
| L3 | 1-3 | все 60 | 0 | 60 | 0 |
| L4 | 1 | 146-166 | 18 | 2 | 0 |
| L4 | 2 | 167-186 | 20 | 0 | 0 |
| L4 | 3 | 187-206 | 20 | 0 | 0 |
| L5 | 1 | 146-166 | 19 | 1 | 0 |
| L5 | 2 | 167-186 | 20 | 0 | 0 |
| L5 | 3 | 187-206 | 20 | 0 | 0 |

L3 пропущены — треки уже были на L4. L5 добавил P3 DSP анализаторы (essentia).

---

### 11. build_set + score_transitions + rebuild_set

```json
build_set: playlist_id=5, template=classic_60, algorithm=ga
→ quality_score=0.6938, 60 tracks

score_transitions v1: avg=0.767, hard_conflicts=4
  pos 54: Mark Reeve→Akdoxx   — Camelot dist 7
  pos 55: Akdoxx→Dok&Martin   — Energy gap 8.7 LUFS
  pos 57: Don Weber→Erso      — Camelot dist 6
  pos 58: Erso→Carbon         — BPM diff 30.7 (!)

rebuild_set v2: avg=0.761, hard_conflicts=2
  pos 56: Erso→Dok&Martin     — Camelot dist 7
  pos 58: Don Weber→Carbon    — BPM diff 30.7 (BPM outlier)
```

**Наблюдение:** Carbon (track 197) — BPM outlier, постоянно вызывает hard conflict. Нужно исключить.

---

### 12. suggest_next_track

```json
{"set_id": 5, "after_position": 10, "energy_direction": "up"}
→ {"suggestions":[],"pool_size":0,"scored":0}
```

**Ошибка:** pool_size=0 — все треки плейлиста уже добавлены в сет, кандидатов нет.
**Корень проблемы:** Неправильная архитектура — нельзя класть всю библиотеку в сет и потом спрашивать "что дальше".
**Решение:** Нужен новый инструмент `get_next_options` (см. design ниже).

---

## Сводка ошибок / проблем

| # | Инструмент | Проблема | Severity | Предлагаемый фикс |
|---|-----------|---------|---------|-------------------|
| 1 | `ym_playlists get_tracks` | Нет `limit`/`offset` — возвращает ВСЕ треки | Medium | Добавить пагинацию в action=get_tracks |
| 2 | `analyze_batch` | Не принимает YM string IDs | Medium | Авто-резолвинг через yandex_metadata |
| 3 | `suggest_next_track` | pool=0 когда все треки уже в сете | High | Заменить/дополнить новым `get_next_options` |
| 4 | `analyze_batch` с task=True | Возможна проблема с run_tool прокси | Low | Проверить |

---

## L5 данные (пример — track 146 Soul Spiritism)

```json
{
  "analysis_level": 5,
  "advanced": {
    "danceability": 1.027,           // essentia DFA (unbounded)
    "dissonance_mean": 0.498,
    "dynamic_complexity": 4.186,
    "spectral_complexity_mean": 43.16,
    "pitch_salience_mean": 0.813
  },
  "phrase": {
    "boundaries_ms": [69, 7291, 8452, ...],  // 18 границ фраз
    "dominant_phrase_bars": 8
  },
  "bpm_histogram": {
    "first_peak_weight": 0.432,
    "second_peak_bpm": 235,
    "second_peak_weight": 0.189
  },
  "tonnetz": [-0.024, 0.002, -0.017, 0.003, -0.002, 0.003]
}
```

---

## Design: get_next_options (новый инструмент)

Основной API для интерактивного Automix-билдера.

### Параметры

```python
get_next_options(
    from_track_id: int,
    playlist_id: int | None = None,      # пул = треки из плейлиста
    track_ids: list[int] | None = None,  # или явный список ID
    exclude_set_id: int | None = None,   # исключить треки уже в сете
    count: int = 5,                      # кандидатов на группу
    bpm_tolerance: float = 15.0,         # окно pre-filter
)
```

### Алгоритм

```bash
1. Загрузить features from_track              → 1 SQL
2. Загрузить IDs пула (из playlist или list)  → 1 SQL
3. Если exclude_set_id: убрать уже в сете     → 1 SQL
4. Pre-filter BPM: |delta| ≤ bpm_tolerance    → in-memory
5. Pre-filter Camelot: dist ≤ 4               → in-memory
6. Batch-загрузить features пула              → 1 SQL batch
7. Скорить пары (TransitionScorer)            → CPU ~10ms
8. Группировать по delta_lufs + mood          → in-memory
9. Sort DESC by overall_score в каждой группе
10. Вернуть top-N на группу
```

### Логика групп

| Группа | Условие | Дополнительно |
|--------|---------|--------------|
| UP | delta_lufs > +1.5 | score > 0 (не hard reject) |
| HOLD | \|delta_lufs\| ≤ 1.5 | score > 0 |
| DOWN | delta_lufs < -1.5 | score > 0 |
| CONTRAST | mood ≠ from_mood OR camelot_dist ≥ 3 | независимо от энергии, может пересекаться с UP/HOLD/DOWN |

### Response

```json
{
  "current": {
    "track_id": 146, "title": "Soul Spiritism",
    "bpm": 129.2, "camelot": "8A", "lufs": -12.32, "mood": "detroit"
  },
  "pool_size": 59,
  "candidates_scored": 41,
  "up": {
    "direction": "up", "threshold": "> +1.5 LUFS",
    "tracks": [{
      "track_id": 195, "title": "Backwards",
      "bpm": 131.0, "camelot": "9A", "lufs": -10.2, "mood": "peak_time",
      "overall_score": 0.847,
      "scores": {"bpm": 0.92, "harmonic": 0.89, "energy": 0.78, ...},
      "delta_lufs": +2.12, "delta_bpm": +1.8,
      "camelot_distance": 1, "mood_change": true
    }]
  },
  "hold": { "tracks": [...] },
  "down": { "tracks": [...] },
  "contrast": { "tracks": [...] }
}
```

### Edge cases

| Ситуация | Поведение |
|---|---|
| from_track без features | ToolError |
| Пул пуст | ToolError |
| Все hard reject | Группа = [] |
| count > кандидатов | Вернуть сколько есть |
| from_track в пуле | Автоматически исключить |
| Camelot = null у кандидата | Пропустить camelot pre-filter |
| LUFS = null у from_track | UP/HOLD/DOWN недоступны, только CONTRAST (по mood/key) |

---

## Итоги

- Треков добавлено: 60 (все были импортированы ранее)
- Треков проанализировано L4: 58 (2 уже были)
- Треков проанализировано L5: 59 (1 уже был)
- Ошибок анализа: 0
- Критических багов: 0
- Проблем UX: 3 (limit в get_tracks, YM ID в analyze_batch, suggest_next_track pool=0)
- Сет собран: 60 треков, quality=0.69, 2 hard conflicts после rebuild

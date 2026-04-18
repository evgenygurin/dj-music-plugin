# E2E Test Prompt — DJ Music Plugin

> Скопируй этот промпт в новую сессию Claude Code для полной проверки системы.

---

## Задача

Проведи полный E2E тест DJ Music Plugin. Используй **ТОЛЬКО MCP tools** (dj-music-*), никаких Python-скриптов. Все найденные ошибки записывай в отдельные файлы `docs/reports/errors/BUG-NNN-short-name.md` в формате:

```markdown
# BUG-NNN: Краткое описание

**Статус**: open
**Обнаружен**: YYYY-MM-DD
**Компонент**: tool/service/analyzer name
**Severity**: critical/high/medium/low

## Симптом
Что произошло.

## Root Cause
Почему произошло (если удалось определить).

## Воспроизведение
Шаги для воспроизведения.

## Ожидаемое поведение
Что должно быть.
```

Нумерация BUG с 004 (001-003 уже существуют).

---

## Шаги тестирования

### 1. Проверка инфраструктуры

```text
get_library_stats          → должен вернуть статистику
list_playlists             → список существующих
list_sets                  → список существующих
list_platforms             → 4 платформы
```

### 2. Поиск и импорт 10 треков из YM

```text
ym_search(query="techno underground 2025", type="tracks", limit=10)
```

Запиши YM track IDs (10 штук).

### 3. Создать плейлист

```text
manage_playlist(action="create", data={"name": "E2E Test YYYY-MM-DD"})
```

Запиши playlist_id.

### 4. Импортировать треки

```text
import_tracks(track_refs=[...10 YM IDs...], playlist_id=<id>)
```

### 5. Добавить треки в плейлист (проверка resolve_track_refs)

```text
manage_playlist(action="add_tracks", data={"id": <playlist_id>}, track_refs=[...10 YM IDs как строки...])
```

**Проверь**: `track_count` должен быть 10.

### 6. Проверить get_playlist с треками

```text
get_playlist(id=<playlist_id>, include_tracks=True)
```

**Проверь**: `tracks` массив должен содержать 10 элементов с `id`, `title`, `duration_ms`. Если есть `error: true` — записать BUG.

### 7. Скачать MP3

```text
download_tracks(track_refs=[...10 YM IDs...])
```

**Проверь**: `downloaded: 10`, `failed: 0`.

### 8. Аудио-анализ

```text
analyze_batch(playlist_id=<playlist_id>)
```

**Проверь**: `completed: 10`, `failed: 0`, `skipped: 0`.

Если analyze_batch/analyze_track не найдены в tool list — записать BUG (BUG-001 регрессия).

### 9. Проверить features

Для каждого из 3 случайных треков:
```text
get_track_features(id=<track_id>)
```

**Проверь** что заполнены:
- `tempo.bpm` (120-155 для техно)
- `tempo.confidence` (> 0)
- `loudness.integrated_lufs` (не null)
- `energy.mean` (> 0)
- `key.key_code` (0-23)
- `rhythm.kick_prominence` (> 0)
- `mood` (не null — должен быть после analyze_track с classify)

Если `mood` = null — записать BUG.

### 10. Аудит плейлиста

```text
audit_playlist(playlist_id=<playlist_id>)
```

**Проверь**:
- `with_features: 10`, `without_features: 0`
- `errors: 0`
- `bpm_range` в пределах 60-160

### 11. Классификация

```text
classify_mood(playlist_id=<playlist_id>)
```

**Проверь**: все 10 треков классифицированы, каждый имеет `mood` и `confidence`.

### 12. Построить сет

```text
build_set(playlist_id=<playlist_id>, name="E2E Test Set", algorithm="greedy")
```

**Проверь**:
- `set_id` и `version_id` получены
- `quality_score` не null (BUG fix #27 — раньше был null)
- `track_count: 10`

### 13. Проверить сет

```text
get_set(id=<set_id>, view="full")
quick_set_review(set_id=<set_id>)
get_set_cheat_sheet(set_id=<set_id>)
```

**Проверь**: transitions есть, scores не все 0.0.

### 14. Создать плейлист на YM

```text
push_set_to_ym(set_id=<set_id>, ym_playlist_name="E2E Test Set", mode="create")
```

**Проверь**: `tracks_pushed: 10`, `ym_playlist_kind` получен.

### 15. Проверить метаданные нормализованы (PR #24)

```text
search(query=<один из артистов из импорта>, entity="artists")
```

**Проверь**: артист найден в DB (если нет — metadata normalization не сработала при import).

### 16. Score transitions (проверка MFCC + energy bands)

```text
score_transitions(mode="pair", from_track_id=<first>, to_track_id=<second>)
```

**Проверь**: `spectral` компонент > 0 (раньше был 0.0 из-за отсутствия mfcc_vector).

### 17. Cleanup (опционально)

```text
manage_playlist(action="delete", data={"id": <playlist_id>})
```

---

## Итоговый отчёт

В конце выведи таблицу:

| Шаг | Тест | Результат | Баги |
|-----|------|-----------|------|
| 1 | Инфраструктура | ✅/❌ | — |
| 2 | Поиск YM | ✅/❌ | — |
| ... | ... | ... | ... |

И список всех созданных BUG-файлов.

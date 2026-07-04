---
name: curate-library
description: "This skill should be used when the user asks to classify tracks, audit playlist, get library stats, distribute to subgenres, run mood classification, curate a crate, or review library quality. Covers feature-first curation, mood classification, audits, dedup and stats."
version: 1.1.0
---

# Curate DJ Library Workflow

Классификация, аудит и отбор через v1-диспетчеры (@docs/tool-catalog.md). Главный принцип: **curate FEATURE-FIRST** — `mood` это хинт, не ground truth.

## Curation Rules (усвоено на этой библиотеке)

- **`mood` — слабый сигнал** (median confidence ≈0.05; `driving`/`hypnotic` — catch-all с пенальти). `mood_source="beatport"` надёжнее audio-классификатора. Используй `mood__in` для сужения, решение принимай по фичам.
- **Фичи с реальным разбросом** (по ним фильтруй/ранжируй): `integrated_lufs`, `spectral_centroid_hz` (лучший спектральный дискриминатор), `energy_mean`, `bpm`, `key_code`, `hp_ratio`, `energy_low`.
- **Near-constant фичи** (НЕ разделяют треки здесь): `dissonance_mean`, `spectral_contrast`, `spectral_flux_*`, `bpm_stability`, `onset_rate`, `energy_std`, `chroma_entropy`.
- **NULL-ловушка L2**: `bpm_confidence`, `true_peak_db`, `danceability`, `dynamic_complexity`, `pitch_salience_mean` в основном NULL до L3+/L5 — `__gte/__lte` по ним тихо опустошает выборку.
- **Калибруй пороги по факту, не по табличке**: перед фильтрацией построй гистограммы — `entity_aggregate(entity="track_features", operation="histogram", field="bpm"|"integrated_lufs"|"spectral_centroid_hz", filters={...})` — и ставь границы по реальному распределению.
- **Гигиена финального списка**: выкинь архивные (`entity_list(entity="track", filters={"id__in": [...]}, fields="summary")` → `status=1`), дубликаты (одинаковый нормализованный title при разных id — в BFS-библиотеке их десятки) и треки недавних сетов того же стиля (`local://sets/{id}/tracks` соседей — не рециклим).
- **Проверка сводимости крейта**: `transition_score_pool(track_ids=[...], top_k=3, components=false)` — компактно даже на большом пуле; хабы hard rejects меняй до сдачи крейта.

## Actions

### Classify (mood lands via analyze handler)
- Анализ **требует скачанный audio_file** (строка в БД + файл на диске) — сначала `entity_create(entity="audio_file", data={"track_ids": [...]})` батчами 8–10 (на MCP-таймауте проверь `entity_list(entity="audio_file", filters={"track_id__in": [...]})` и дошли недостающие), потом:
  `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
- Более высокий уровень: `entity_update(entity="track_features", id=<track_id>, data={"level": 3|5})` (update-схема strict: только `level`).
- 15 поджанров (low → high): ambient_dub → dub_techno → minimal → detroit → melodic_deep → progressive → hypnotic → driving → tribal → breakbeat → peak_time → acid → raw → industrial → hard_techno. Профили: `reference://subgenres`.

### Audit
- Плейлист: `local://playlists/{id}/audit`; правила: `reference://audit_rules`; сет: `local://sets/{id}/review?version=<v>`.

### Stats
- `entity_aggregate` — `operation ∈ count|distinct|histogram|min_max|sum|avg`, `group_by` — параметр: `entity_aggregate(entity="track_features", operation="count", group_by="mood")`.
- Prefab UI: `ui_library_dashboard()`, `ui_library_audit(playlist_id?)`, `ui_camelot_wheel(playlist_id?)`.

### Select a crate (пример feature-first отбора)
```text
entity_list(entity="track_features",
  filters={"mood__in": ["hypnotic","driving"], "bpm__range": [126,133],
           "energy_mean__gte": 0.4, "spectral_centroid_hz__lte": 2400,
           "integrated_lufs__range": [-13,-9], "variable_tempo__eq": false},
  fields="scoring", sort=["energy_mean__desc","track_id"], limit=150)
```
Ранжируй внутри выборки по `integrated_lufs`/`energy_mean`/`spectral_centroid_hz` под роль слота. `track` не имеет фичевых фильтров — BPM/mood/LUFS живут на `track_features`; плейлистного фильтра там нет — резолвь ids через `local://playlists/{id}?include_tracks=true` → `track_id__in`.

## Tips

- `energy_mean` нормирован per-track — ранжируй им интенсивность, а шаг громкости меряй `integrated_lufs` (hard reject > 6 LUFS).
- Filter DSL: `__gte/__lte/__range/__in/__eq/__isnull`; лукапа `__between` не существует.
- Пуш крейта в YM — skill `ym-sync` (помни `at=<trackCount>` при add_tracks).
- Tool reference: @docs/tool-catalog.md; фичевый справочник: @.claude/rules/audio.md § Сигнальное качество фич.

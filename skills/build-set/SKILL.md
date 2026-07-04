---
name: build-set
description: "This skill should be used when the user asks to build a DJ set, create a set from playlist or library, optimize track order, rebuild set, reorder tracks, or make a set. Covers candidate curation, GA/greedy optimization, L5 finalization, review and iteration."
version: 1.1.0
---

# Build DJ Set Workflow

Build an optimized DJ set via the v1 polymorphic dispatchers (см. @docs/tool-catalog.md). Порядок фаз ниже — жёсткий: curate → download → optimize → L5 → re-optimize → version → review.

## Steps

1. **Curate the candidate pool FEATURE-FIRST (from the whole library, not just a playlist)**
   - `mood` — слабый сигнал (median confidence ≈0.05); используй его как грубый хинт (`mood__in`), а отбор веди по фичам с реальным разбросом:
     `entity_list(entity="track_features", filters={"bpm__range": [126, 133], "energy_mean__gte": 0.4, "spectral_centroid_hz__lte": 2400, "integrated_lufs__range": [-13, -9], "variable_tempo__eq": false}, fields="scoring", sort=["energy_mean__desc", "track_id"], limit=150)`
   - Профиль стиля (ideal/tolerance по фичам) — из `reference://subgenres`.
   - **НЕ фильтруй `__gte/__lte` по NULL-heavy L2-колонкам** (`bpm_confidence`, `true_peak_db`, `danceability`) — NULL проваливает сравнение и тихо опустошает выборку. У `pitch_salience_mean`/`dynamic_complexity`/`spectral_complexity_mean` числовых лукапов нет вовсе (только `__isnull`; чужой лукап = типизированный ValidationError).
   - Держи BPM-коридор пула ≤ 8–10 (hard reject на Δ>10) и LUFS-разброс ≤ 5–6.

2. **Exclude recycled and dead tracks**
   - Треки недавних сетов того же стиля: прочитай `local://sets/{id}/tracks` соседей (найди их через `entity_list(entity="set", fields="summary")`) и выкини пересечения.
   - Архивные: `entity_list(entity="track", filters={"id__in": [...]}, fields="summary")` → выкинь `status=1`. Заодно возьми `duration_ms` и уложи суммарный хронометраж в целевой слот ДО оптимизации (~6.5 мин/трек для техно).

3. **Score the pool and cull conflict hubs**
   - `transition_score_pool(track_ids=[...], top_k=3, components=false)` — компактный ответ (N·top_k пар вместо N·(N−1); полный матричный ответ на 18+ треках пробивает лимит MCP-клиента). `total_scored_pairs` показывает объём до усечения; `overall == 0.0` = hard reject.
   - Треки, собирающие бо́льшую часть hard rejects (хабы), выкинь из пула; добери кандидатов и повтори. Куратор доводит пул ровно до N финальных треков — `sequence_optimize` с `ga`/`greedy` упорядочивает ВЕСЬ пул (сабсетит только `algorithm="constructive"` под template).

4. **Download audio BEFORE any (re)analysis**
   - Анализ (даже L2/L3 reanalyze) требует зарегистрированный `audio_file` с файлом на диске: `entity_create(entity="audio_file", data={"track_ids": [...]})` батчами 8–10 (каждый трек 20–40 с; на MCP-таймауте UoW откатывается — проверь `entity_list(entity="audio_file", filters={"track_id__in": [...]})` и перевыпусти только недостающие).
   - Stale-строки (файл стёрт из /tmp) с v1.6.2 перекачиваются автоматически (`refreshed_stale_row`).

5. **L5 (ADVANCED) before finalization**
   - `entity_update(entity="track_features", id=<track_id>, data={"level": 5})` — по 4–5 параллельно, ~5–10 с/трек. Успех = `level: 5, feature_count: ~62–64` в ответе; сомневаешься — перепроверь `entity_list(entity="track_features", filters={"track_id__in": [...], "analysis_level__gte": 5})`.
   - L5 переопределяет `key_code` и фичи относительно L2 → всё, что построено до L5, черновик. После L5 **перечитай фичи и пере-скорь пул** (`transition_score_pool` заново) — hard-reject картина на надёжных ключах меняется.

6. **Optimize on L5 features — two candidate orders**
   - Контейнер: `entity_create(entity="set", data={"name": "...", "template_name": "roller_90", "target_duration_ms": ...})`.
   - GA: `sequence_optimize(track_ids=[...], algorithm="ga", template=<из reference://templates>)`. Учти: GA максимизирует pairwise и **любит восходящую громкость** (energy-скорер предпочитает +0.5 LUFS) — для closing/descent-арок его порядок будет перевёрнут.
   - Ручная арка: BPM-ramp + LUFS-пик на ~0.6–0.7 длины (two-thirds rule), для closing — монотонный спуск от handoff-BPM.

7. **Persist BOTH as versions, compare section-aware scores**
   - `entity_create(entity="set_version", data={"set_id": <id>, "label": "v1-ga", "track_order": [...]})` и `"v2-arc"` (schema strict: только `set_id`, `label`, `track_order`, `quality_score?`, `generator_run_meta?`).
   - Сравнивай по `quality_score` версий (section-aware, обычно выше сырого GA-скора). Разрыв ≤ ~0.05 в пользу GA — бери арку: это цена намеренного энергетического контраста. Camelot-конфликты на L5-ключах бьют арку сильнее — смотри review.

8. **Review the CHOSEN version, not the latest**
   - `local://sets/{id}/review?version=<version_id>` — hard conflicts + weak transitions именно выбранной версии (без `?version` показывается последняя созданная).
   - Слабый слот: `local://tracks/{track_id}/suggest_replacement/{set_id}/{position}` — кандидаты берутся по BPM-близости, стиль-лок проверяй руками по их фичам.
   - Финал: `local://sets/{id}/cheatsheet?version=<v>` (несёт fx_type/bars/mix-points per transition) → дальше skill `deliver-set`.

## Tips

- Дубликаты в библиотеке реальны (одинаковый нормализованный title, разные track_id) — прогони финальный список глазами.
- GA 100+ треков — 30–120 с; `transition_score_pool` имеет собственный таймаут 300 с.
- `local://sets/{id}/transitions` несёт только overall/hard_reject; per-pair пресеты — в cheatsheet-ресурсе или `entity_list(entity="transition", filters={"from_track_id__in": [...], "to_track_id__in": [...]})`.
- Tool reference: @docs/tool-catalog.md; set-build правила: @.claude/rules/tools.md § Set-build flow.

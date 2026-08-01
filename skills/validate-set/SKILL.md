---
name: validate-set
description: "This skill should be used when the user asks to validate a rendered set, check grid alignment, verify kick phase, check beatgrid, QA a mix, debug tempo drift, or verify that a mix plays on beat. Covers the render_validate_grid tool, pre-render checklists (Camelot/BPM/phase), bpm_measured correctness and the never-re-render-without-DSP-change rule."
version: 1.0.0
---

# Validate Set Grid & Render

Проверить, что отрендеренный микс стоит на гриде: каждый трек играет ровно на `target_bpm`, кик-фаза выровнена, и ничего не «плывёт» от времени-стретча. Продукт — `grid_check.json` с per-track BPM-отклонением и статусами ok/warn/fail.

## Когда

- после `render_mixdown` — перед diagnose/delivery как обязательный QA-гейт;
- при «сет рассинхронен», «бит плывёт», «трек играет быстрее/медленнее»;
- после смены beatgrid (refresh) или ручного правильного `bpm_measured`.

## Steps

1. **Чеклист ДО рендера (не рендерь сет с заведомыми конфликтами)**
   - Camelot: для каждой пары соседей `_camelot_distance(a.key, b.key)` > 2 → конфликт; изолированный трек (dist=99 со всеми) — удали или замени.
   - BPM discrepancy: `|stored_bpm - audio_bpm| > 0.5` → для time-stretch используй **audio_bpm**, не stored (ошибка 1 BPM на 60-секундном переходе = drift ~1 beat).
   - Phase: проверяй на **оригинальном** файле (`/tmp/dj_audio/NN. Artist - Title [ym_id].mp3`), НИКОГДА на demucs-стемах (сдвигают транзиенты на 30–100ms). `librosa.beat.beat_track` → `phase_ms = beats[0]*1000`; расхождение с beatgrid-фазой >30ms — пересчитай grid.
   - Phase offset между соседями: `abs(phase_a - phase_b) * target_bpm / 60` > 0.25 beat → проблема.

2. **Проверь grid (source-level, после render_beatgrid)**
   - `local://render/{version_id}/beatgrid` — per-track `trim_start_s` / `phase_ms` / `bpm_measured`.
   - `bpm_measured` (длинное окно ~100s kick-detector) — источник истины для `tempo_ratio = bpm_measured/target`. Если `phase_ms: 0.0` и `flags: []` — алгоритм не нашёл первый удар (тихое интро) — загляни в трек.

3. **Запусти валидатор микса (главный гейт)**
   - `dj_render_validate_grid(version_id={id})` → результат в `local://render/{id}/grid_check`.
   - `tracks[].bpm_measured` = реальный BPM каждого боди-сегмента в MIX; `bpm_dev` = отклонение от `target_bpm`. Это доказывает, что rubberband честно применил `tempo_ratio`.
   - `plan_checks[]` — pre-render: `bpm_measured` (из grid) против `stored_bpm` (из БД) — ловит класс бага «неверный stored BPM» (реальный кейс: трек играл +1.6 BPM, mean |dev| 0.34; после фикса — max 0.40, mean 0.09).

4. **Интерпретируй по гейтам** (`reference://render/validation`)
   | |bpm_dev| | статус | действие |
   |----------|--------|----------|
   | ≤ 0.5     | ok   | иди к diagnose/deliver |
   | 0.5–1.0   | warn | слышимо на длинных переходах — прими или чини |
   | > 1.0     | fail | реальный баг движка — чини по шагу 5 |

5. **Дерево решений при warn/fail**
   a. Причину ищи на **оригинальном аудио**, не на стемах.
   b. Пересравни `audio_bpm` (track_features) vs stored — если >0.5, рендер обязан был взять audio_bpm.
   c. `dj_render_beatgrid(version_id={id}, refresh=True)` — пересчитай trim/phase/bpm_measured.
   d. Повтори `dj_render_validate_grid`. Если plan_checks ok, а микс всё ещё плывёт — баг в рендерере (репортни).
   e. **Перерендер ТОЛЬКО если реально изменились DSP-параметры** (subgenre, transition_bars/body_bars, эффекты, уровни). Смена порядка треков или refresh grid не требует demucs/rubberband заново — переиспользуй кешированные стемы (`cp` из `generated-sets/render/`).

6. **Зафиксируй результат**
   - `local://render/{version_id}/grid_check` — summary: «grid OK» / «grid WARN (документировано)».
   - В отчёте укажи `worst_dev_bpm` и какие треки требуют внимания.

## Tips

- Дефолтные эффекты рендера (filter_sweep/echo/reverb) работают некорректно — всегда передавай `None`, иначе фильтр «захлёбывается» быстрее бита и засоряет grid-фазу.
- `render_validate_grid` меряет BPM автокорреляцией огибающей (фаза-нечувствительно) — надёжно на demucs-миксе; измерение фазы киков в миксе ненадёжно (стемы), поэтому тул его не делает.
- Наибольшая погрешность rubberband ≈ 0.4 BPM — остаточный `warn` на одном треке принимай, если боди короткое (<60s) и соседи ок.
- Полный рецепт: промпт `validate_grid_workflow`; устаревший каталог: `docs/tool-catalog.md`; правила рендера: `AGENTS.md` → Render Lessons.

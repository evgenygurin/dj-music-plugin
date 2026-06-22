# Техно глубоко: поджанры, построение сетов, школы диджеев и расширение каталога MCP-промтов (v2)

> Углублённое исследование предметной области (техно-поджанры, оси
> построения сета, школы и фишки диджеев, проекция на данные БД) +
> дизайн **7 новых workflow-промтов**, доводящих каталог до **26**.
>
> Дата: 2026-06-22. Продолжение
> [2026-06-22-techno-set-construction-and-mcp-prompts.md](2026-06-22-techno-set-construction-and-mcp-prompts.md)
> (тот док вывел 19 промтов; этот добавляет 7 и закрывает оставшиеся
> «оси» и сценарии). Связано с
> [transition-scoring.md](../transition-scoring.md),
> [domain-glossary.md](../domain-glossary.md),
> [audio-schema.md](../audio-schema.md), [tool-catalog.md](../tool-catalog.md).

---

## 0. TL;DR

- Прошлый каталог (19 промтов) покрывал **гармоническую** и **поджанровую**
  оси журналов, но не **темповую**; покрывал критику/ремонт одной пары и
  одного слота, но не **тяжёлый ремонт** сета с россыпью hard-reject'ов;
  строил сеты сверху-вниз от шаблона, но не **снизу-вверх** от кластеров
  совместимости; не давал **перформанс-артефакта** (чит-щит для игры) и
  **actionable-очистки** библиотеки; и не кодировал **школы диджеев** как
  пресеты намерения.
- Эти 7 пробелов закрыты новыми промтами: `tempo_journey_workflow`,
  `dj_persona_workflow`, `style_lock_set_workflow`, `mix_cluster_workflow`,
  `rescue_set_workflow`, `set_cheatsheet_workflow`,
  `library_cleanup_workflow`.
- Все 7 прогнаны через content-correctness guard
  (`tests/prompts/test_prompt_content_correctness.py`) — каждое имя
  сущности/пресета/фильтра/операции реально существует в рантайме.

---

## 1. Три оси построения сета (почему появилась темповая)

Техно-сет — это движение одновременно по нескольким независимым осям.
Толпа «читает» сет как одну дугу, но диджей рулит ею через несколько
ортогональных параметров. Наш движок измеряет все три, но промты до сих
пор кодировали только две:

| Ось | Что меняется | Фича в БД | Промт (был / стал) |
|---|---|---|---|
| **Гармония** | тональность (Camelot) | `key_code` + `keys` | `harmonic_journey_workflow` ✅ |
| **Поджанр/настроение** | характер (energy axis) | `mood` / `mood_confidence` | `subgenre_journey_workflow` ✅ |
| **Темп** | BPM-разгон/спад | `bpm` / `bpm_stability` | **`tempo_journey_workflow`** ← новый |

**Почему темп — отдельная ось.** Гармонический и поджанровый журналы
двигают *характер*, но могут оставить BPM плоским; и наоборот — можно
держать один ключ и один поджанр, плавно разгоняя темп. Профессиональная
практика: **+1–2 BPM за транзишен** через 5+ треков даёт разгон, который
дансфлор *чувствует, но не слышит* (Mixgraph, Digital DJ Tips). Большие
прыжки прячут в брейкдаун, half/double-time или reset-трек. Наш
hard-constraint `|ΔBPM| > 10 → hard_reject` и `S_bpm` Gauss (σ=10) делают
эту ось напрямую вычислимой; `tempo_journey_workflow` фильтрует пул по
`bpm__gte/__lte`, помечает `variable_tempo` треки (они дрожат рампу) и
заказывает у `sequence_optimize` монотонный ход с пиннингом самого
медленного/быстрого якоря.

> Источники по темповому менеджменту:
> [Mixgraph — Energy Flow Guide](https://www.mixgraph.io/learn/energy-flow-guide),
> [Vibes — Techno BPM Chart](https://vibesdj.io/dj-tools/techno-bpm-chart),
> [Harmonyset — DJ Set Energy Flow & BPM](https://www.harmonyset.com/guides/dj-set-energy-flow).

---

## 2. Поджанры техно — уточнённая карта (energy axis)

Наши **15 поджанров** (`reference://subgenres`,
`app/audio/classification/profiles.py`, enum в
`app/shared/constants.py`), упорядоченные по энергии:

```text
ambient_dub → dub_techno → minimal → detroit → melodic_deep →
progressive → hypnotic → driving → tribal → breakbeat →
peak_time → acid → raw → industrial → hard_techno
```

Сверено с внешними обзорами 2025 (характер + типичный BPM):

| Семейство | BPM | Характер (внешние источники) | Наши поджанры |
|---|---|---|---|
| **Dub / ambient** | 118–126 | эхо-аккорды, реверберация, «дрейф», открывашки/закрывашки | `ambient_dub`, `dub_techno` |
| **Minimal / Detroit** | 124–134 | редукция, микро-вариации, машинная душевность, струнные стэбы | `minimal`, `detroit` |
| **Melodic / progressive** | 122–132 | эмоциональные пэды, долгие билды, «закатовый» | `melodic_deep`, `progressive` |
| **Hypnotic / driving** | 130–140 | циклический транс, фильтр-движения, «локомотив» | `hypnotic`, `driving` |
| **Tribal / breakbeat** | 130–145 | перкуссия/полиритмия, ломаный бит | `tribal`, `breakbeat` |
| **Peak / acid** | 134–146 | мейнфлор-бэнгеры, резонанс TB-303 | `peak_time`, `acid` |
| **Raw / industrial / hard** | 138–160 | сырость, дисторшн, металл, рейв-интенсивность, шранц | `raw`, `industrial`, `hard_techno` |

Ключевые выводы для промтов:

- **`driving` и `hypnotic` — catch-all**: классификатор штрафует их
  (`catch_all_penalty`), поэтому при `style_lock`/`subgenre_journey`
  нельзя якориться на них как на устойчивых маркерах — отсюда «соседние
  моды» в `style_lock_set_workflow` (±1 шаг по оси).
- **Дискриминирующие фичи** (mood-классификатор): `hp_ratio`
  (ambient↑/industrial↓), `spectral_centroid` (melodic↓/acid↑),
  `energy_mean` (ambient↓/hard↑), `kick_prominence` (minimal↓/peak↑),
  `loudness_range` (dub_techno шире/industrial уже),
  `spectral_flux_std` (hypnotic↓ повторяемость / breakbeat↑).

> Источники:
> [Techno UK — Top Techno Subgenres 2025](https://techno.org.uk/top-techno-subgenres-explained-2025/),
> [Samplesound — Techno Explained](https://www.samplesoundmusic.com/blogs/news/techno-explained-styles-sounds-and-subgenres-you-should-know),
> [Sound of Life — From Detroit to Berlin](https://www.soundoflife.com/blogs/mixtape/techno-subgenres),
> [Technomusicnews — 7 Essential Subgenres](https://technomusicnews.com/2025/03/05/7-essential-techno-subgenres-you-need-to-know/),
> [Grokipedia — Dub Techno](https://grokipedia.com/page/Dub_techno).

---

## 3. Анатомия сета — каноны (сведено и уточнено)

### 3.1 Пять классических форм дуги

Профи рисуют сет как **3-актную структуру**: warm-up (energy 3–5) →
journey (5–7, модуляции ключа) → peak & release (8–10 → 4–6). Пять
канонических форм (SetFlow, DJ.Studio, Mixgraph):

1. **Journey** — медленный build и release на длинной дистанции.
2. **Peak time** — релентлесс высокая энергия.
3. **Warm-up** — начать низко, передать «тёплым».
4. **Cool-down / Closing** — свести энергию вниз.
5. **Chill / Roller** — устойчивый ровный кач.

Наши 8 шаблонов (`reference://templates`) кодируют эти формы как набор
слотов `(position, mood, target_lufs, bpm_min, bpm_max, duration,
tolerance)`; `infer_intent()` использует per-template таблицу фаз
`(warmup_end, peak_start, peak_end)`. **Промт обязан передавать
`template`** — иначе интент считается по дефолту 0.20/0.50/0.85.

### 3.2 Энергия блоками, не каждый транзишен

Важный канон, который кодируют новые промты: **энергию двигают блоками
по 3–4 трека** на одном уровне, затем шаг вверх — не «+энергия каждый
транзишен». Внутри блока **варьируют текстуру**: за светлым/воздушным
треком — тёмный/басовый при той же энергии; интенсивность держится, а
характер меняется, и сет не звучит плоско. Это прямой смысл
`style_lock_set_workflow` (моно-жанр через текстуру, не через смену
поджанра).

> «Crowds respond to narrative, not individual songs — a well-shaped arc
> with average tracks beats a random run of bangers» — общий тезис
> SetFlow / Mixgraph / DJ.Studio.

### 3.3 Фразировка 32/64

Танцевальная музыка строится фразами по 32 (и 64) бита; переходы
выравниваются по границам фраз. У нас границы секций — `track_sections`
(~70/трек); фаза даунбита (`dj_beatgrids.first_downbeat_ms`) покрывает
~0.1%, поэтому mix-point detector использует fallback `0`. Для 4/4 техно
с интро на `t=0` это приемлемо. `set_cheatsheet_workflow` **честно
помечает** этот degrade в самом чит-щите (фразировать по уху на ночь).

### 3.4 Гармонический микс (Camelot) — без изменений

`CAMELOT_BASE_SCORES = {0:1.0, 1:0.9, 2:0.6, 3:0.3, 4:0.1}`, hard-reject
при `camelot_distance ≥ 5`. Безопасные ходы: тот же ключ, ±1 по колесу,
A↔B (minor↔major), +2 как приём нагнетания. См. прошлый док §3.4.

---

## 4. Школы диджеев → пресеты намерения (`dj_persona_workflow`)

Прошлый док описал школы в §5 как прозу. Новый промт **кодирует их как
исполняемые пресеты**: persona → `(template, mood-band, ethos)`. Это самый
«доменный» промт каталога — он переводит эстетику конкретной школы в
наш движок честно (без обещаний live-FX, которых движок не умеет).

| Persona | Школа / фишка | Шаблон | Mood-band | Транзишен-этос |
|---|---|---|---|---|
| `klock` | Ben Klock / Berghain — гипнотика, warehouse-глубина, элементы как «кирпичики», треки дразнятся in/out | `roller_90` | dub_techno, hypnotic, driving | длинные 32-бар блэнды, `HARMONIC_SUSTAIN` |
| `dettmann` | Marcel Dettmann — raw, стальной, перкуссивный | `peak_hour_60` | driving, raw, industrial | drum-led (`DRUM_SWAP`/`DRUM_CUT`) |
| `lens` | Amelie Lens — acid-leaning peak, фестивальный драйв | `peak_hour_60` | peak_time, acid, hard_techno | tight bass-swap, hands-up cuts |
| `dewitte` | Charlotte de Witte — тёмный driving acid | `peak_hour_60` | peak_time, acid, hard_techno | релентлесс, минимум гармонии |
| `mills` | Jeff Mills — Detroit machine-soul, три деки | `classic_60` | detroit, driving, peak_time | короткие плотные блэнды |
| `hawtin` | Richie Hawtin / Plastikman — minimal, микро-детали | `roller_90` | minimal, dub_techno, hypnotic | очень длинные блэнды, EQ/filter |
| `kraviz` | Nina Kraviz — гипнотика, leftfield, acid-grit | `roller_90` | hypnotic, acid, raw | filter-driven tension |

**Честность контракта.** Persona-промт прямо предупреждает LLM: движок
не имеет реального stem-separation и пресетов `FILTER_SWEEP`/`LOOP_ROLL`
— filter/loop-приёмы аппроксимируются доступными пресетами и длинными
блэндами. Это требование `.claude/rules/prompts.md` § «Honesty about
engine limits».

> Источники по школам: прошлый док §5 + RA / Google Arts (Klock &
> Dettmann), Mixmag/Red Bull (warm-up & B2B этика).

---

## 5. Техники переходов — без новых пресетов

Сводка из прошлого дока §4 остаётся в силе: 7 Neural Mix пресетов
(`FADE`, `ECHO_OUT`, `DRUM_SWAP`, `DRUM_CUT`, `VOCAL_SUSTAIN`,
`VOCAL_CUT`, `HARMONIC_SUSTAIN`), picker — first-match-wins. Новые промты
**ничего не добавляют в движок** — они только по-новому *компонуют*
существующий surface. `set_cheatsheet_workflow` читает `fx_type` из
персистнутых `transitions` и переводит каждый пресет в человеческую
подсказку у пульта:

| `fx_type` | Подсказка диджею |
|---|---|
| `HARMONIC_SUSTAIN` / `FADE` | длинный 32-бар блэнд, ключи держатся |
| `DRUM_SWAP` / `DRUM_CUT` | убрать бас EQ, обмен на барабанах |
| `ECHO_OUT` | эхо-хвост на последнем баре, увести фейдер |
| `VOCAL_SUSTAIN` / `VOCAL_CUT` | вести вокал поверх входящего грува |

---

## 6. Снизу-вверх: кластеры совместимости (`mix_cluster_workflow`)

Все прошлые set-building промты строят **сверху-вниз**: берут шаблон/дугу
и подгоняют треки. Реальные диджеи часто работают **снизу-вверх**: «что в
моём крейте вообще хорошо ложится друг к другу?» — и сет вырастает из
найденных affinities.

`mix_cluster_workflow` использует `transition_score_pool` (попарная
матрица N×N) + `ui_score_pool_matrix` (визуальный heatmap):

- **Кластер** — группа треков, взаимно скорящих высоко (>0.7): общий
  BPM-band + совместимые Camelot-ключи + близкая энергия.
- **Цепочка** — упорядоченный путь через высокоскорные пары без
  hard-reject шага; самая длинная чистая цепочка = спайн сета.
- **Орфаны** — треки, не мигающиеся ни с кем; парковать.

Затем `sequence_optimize(algorithm="greedy")` (пул уже взаимно
совместим — nearest-neighbour сохраняет кластеры) и персист как ядро,
которое можно растить через `extend_set_workflow` или
`crate_digging_workflow`. Кросс-чек с `transition_history/best_pairs` и
`track_affinity (avg_score__gte 0.7)` — учесть исторически удачные пары.

---

## 7. Тяжёлый ремонт (`rescue_set_workflow`)

Прошлый ремонт-блок покрывал критику (`set_review`), одну пару
(`fix_transition`), один слот (`replace_track`). Не было сценария
«сет — каша из hard-reject'ов». `rescue_set_workflow` — heavy-repair:

1. **Замер ущерба** — `local://sets/{id}/review` + `entity_list(transition,
   filters={hard_reject: true})`, доминирующий `reject_reason`.
2. **Сначала ре-ордер** (большинство hard-reject'ов — проблема порядка,
   не трека): `sequence_optimize` с шаблоном сета, trial-версия, ре-чек.
3. **Изоляция неисправимых** — трек, который hard-reject'ит против
   большинства пула, это чужак (не тот BPM-band / одинокий ключ / energy
   outlier); дропнуть или заменить.
4. **Мост для оставшихся** — `fix_transition_workflow` поштучно; крайнее
   средство — `ECHO_OUT`.
5. **Финальный персист + diff** (`versions/compare`), hard_reject → 0.
6. Если пул **принципиально несвязный** (три разрозненных BPM-band) —
   честно сказать и предложить разбить на два сета.

---

## 8. Перформанс и гигиена

### 8.1 `set_cheatsheet_workflow` — read-only артефакт для игры

Сборка из `local://sets/{id}/cheatsheet` + `transitions.fx_type` +
`track_features` (BPM/Camelot/LUFS/mood) в **одну таблицу на трек в
порядке игры** + «watch-outs» (hard/weak пары наверх). Никаких ре-ордеров
/ новых версий — это терминальный шаг для печати/телефона. Честно
помечает degrade (mix-точки из секций, не из hot-cue; downbeat fallback).

### 8.2 `library_cleanup_workflow` — actionable-гигиена

В отличие от `library_health_workflow` (репортит распределения), этот
находит **конкретные проблемы и прописывает фикс на каждую**:

| Проблема | Фильтр | Фикс |
|---|---|---|
| Непроанализированные | `track has_features=false` | `analyze_library_workflow` |
| Под-анализированные (<L3) | `track_features analysis_level__lt 3` | `entity_update(track_features, data={level:3})` |
| Low-confidence mood | `mood_confidence__lte 0.35` | реанализ выше / mood untrusted |
| Tempo-suspect | `variable_tempo=true`, `bpm_confidence__lte 0.5` | проверить BPM по уху, держать от крутых шагов |
| Архивные | `status__in [1]` | вне пулов / delete (необратимо!) |
| Loudness-outliers | `min_max/histogram(integrated_lufs)` | парковать / planned reset |

**Безопасность:** промт явно запрещает mass-delete (необратимо,
каскадит features/sections) — предпочесть реанализ и исключение из пула.

### 8.3 Лайв и точный слот (v3-батч, +4 → 30 промтов)

Четыре промта закрывают **живые/перформанс-ситуации**, которых не было ни
в одном из прошлых — все строили сет *заранее*:

- **`live_next_track_workflow`** — единственный **лайв**-промт: вызывается
  по ходу сета (петля «что играть дальше?»), читает `session://set-draft`
  (сыграно + `target_duration_ms`) и `session://energy-trend?limit=N`
  (последние LUFS → направление), берёт кандидатов из
  `local://tracks/{last}/suggest_next?energy_direction=...`, отсеивает
  banned, верифицирует пару через `local://transition/{a}/{b}/score` и
  называет **один** следующий трек + технику + бэкап. Без персиста — это
  решение момента, а не построение сета.
- **`set_duration_fit_workflow`** — подгонка готового сета под точный
  тайм-слот: `sum(duration_ms)` через `entity_aggregate(operation="sum")`
  vs `target_minutes`; длинно → trim хвоста/`replace_track_workflow`,
  коротко → `extend_set_workflow`; ре-ордер с пиннингом опенера и клозера.
  Движок не энфорсит длительность как hard-constraint — это ручная
  подгонка с сохранением дуги.
- **`track_prep_workflow`** — end-to-end готовность **одного** трека:
  `local://tracks/{id}` + `/features` + `/audit` (11 правил → passed/
  violations), гарантия L3, совместимые соседи через `suggest_next`.
  Гранулярность ниже сета: «подготовь трек к миксу».
- **`lineup_handoff_workflow`** — последовательная **передача слота** в
  лайнапе (warm-up → хедлайнер → closer): хвост сета инженерится на
  целевой `handoff_bpm`/энергию, закрывающий трек пиннится последним.
  Расширяет `b2b_planning_workflow` (2 DJ попеременно) до однонаправленной
  передачи — самый недооценённый навык (warm-up этика: не превышать темп
  хедлайнера, оставить вменяемый BPM).

---

## 9. Полнота каталога — 30 промтов × ситуации

| Ситуация | Промт |
|---|---|
| Прайм доменным знанием | `dj_expert_session` |
| Сет под шаблон end-to-end | `build_set_workflow` |
| Экспорт/доставка (+YM) | `deliver_set_workflow` |
| Рост плейлиста через discovery | `expand_playlist_workflow` |
| Полный конвейер | `full_pipeline` |
| Быстрая проверка пары | `quick_mix_check` |
| Здоровье библиотеки (репорт) | `library_health_workflow` |
| Пакетный анализ/апгрейд тира | `analyze_library_workflow` |
| **Подготовка одного трека** | **`track_prep_workflow`** |
| Журнал по ключу (Camelot) | `harmonic_journey_workflow` |
| Журнал по поджанру | `subgenre_journey_workflow` |
| **Журнал по темпу (BPM)** | **`tempo_journey_workflow`** |
| Сценарий-пресет дуги | `scenario_set_workflow` |
| **Стиль школы диджея** | **`dj_persona_workflow`** |
| **Моно-жанровый сет** | **`style_lock_set_workflow`** |
| **Кластеры совместимости (снизу-вверх)** | **`mix_cluster_workflow`** |
| **Передача слота в лайнапе** | **`lineup_handoff_workflow`** |
| B2B на двух крейтах | `b2b_planning_workflow` |
| Удлинить сет, сохранив дугу | `extend_set_workflow` |
| Критика сета + фиксы | `set_review_workflow` |
| **Тяжёлый ремонт (каша hard-reject)** | **`rescue_set_workflow`** |
| Ремонт одной пары | `fix_transition_workflow` |
| Замена одного слота | `replace_track_workflow` |
| **Чит-щит для игры** | **`set_cheatsheet_workflow`** |
| **Подгонка под тайм-слот** | **`set_duration_fit_workflow`** |
| **Лайв: следующий трек по ходу** | **`live_next_track_workflow`** |
| Крейт-дайвинг + курирование | `crate_digging_workflow` |
| Управление вкусом | `taste_profile_workflow` |
| Синк с YM (pull/push/diff) | `playlist_sync_workflow` |
| **Actionable-очистка библиотеки** | **`library_cleanup_workflow`** |

Жирным — 11 новых (7 в v2-батче + 4 в v3 live/perf-батче). Покрыты все три
оси журналов (ключ/поджанр/темп), оба направления построения (сверху-вниз
шаблон / снизу-вверх кластеры), полный спектр ремонта (пара / слот / весь
сет), эстетика школ, перформанс-артефакт, **лайв-петля**, **подгонка под
слот**, **подготовка трека**, **передача слота** и гигиена.

---

## 10. Лучшие практики FastMCP v3+ (применены ко всем новым промтам)

Из официальной документации (gofastmcp.com/servers/prompts) и нашего
канона (`.claude/rules/prompts.md`):

1. **Standalone `@prompt`** из `fastmcp.prompts`; один промт на файл, имя
   файла = имя промта (FileSystemProvider auto-discovery).
2. **Сигнатуры — простые типы** (`int`, `str`, `int | None`), без
   `*args`/`**kwargs`; параметры без дефолта = required, с дефолтом =
   optional. FastMCP сам конвертит JSON-строки аргументов.
3. **Тело — приватный `_body(...)` f-string helper.** Чистый text-builder:
   никаких импортов repositories/tools/providers/DB/domain (enforced
   `import-linter`).
4. **Возврат `PromptResult(messages=[Message(...)], description=...)`** +
   `meta=PROMPT_META` (version stamping). `description` ≤ полезно кратко.
5. **Tags = `{"namespace:workflow", "<category>"}`** — категории:
   `journey`, `persona`, `style`, `analysis`, `review`, `performance`,
   `maintenance`.
6. **Честность контракта (HARD).** Каждое имя `entity=`/`fields=`/
   `filters={}`/`data={}`/`provider_write op` в теле реально существует в
   рантайме — пинится `test_prompt_content_correctness.py`. Регистрация —
   `EXPECTED_PROMPTS`, `PROMPTS` tuple, `_render` dispatcher,
   `test_all_prompts_return_prompt_result`.
7. **Честность движка.** Не обещать stem-separation, `FILTER_SWEEP`/
   `LOOP_ROLL`, hot-cue/loop-таблицы, mass-download MP3 — degrade'ы
   помечены прямо в телах промтов.

> Новые промты **не меняют** tool/resource surface (20 tools, 27
> resources) — чисто аддитивны, как и предыдущее расширение 6 → 18 → 19.

---

## 11. Источники

Поджанры и BPM:
- [Techno UK — Top Techno Subgenres 2025](https://techno.org.uk/top-techno-subgenres-explained-2025/)
- [Samplesound — Techno Explained](https://www.samplesoundmusic.com/blogs/news/techno-explained-styles-sounds-and-subgenres-you-should-know)
- [Sound of Life — From Detroit to Berlin](https://www.soundoflife.com/blogs/mixtape/techno-subgenres)
- [Technomusicnews — 7 Essential Subgenres](https://technomusicnews.com/2025/03/05/7-essential-techno-subgenres-you-need-to-know/)
- [Grokipedia — Dub Techno](https://grokipedia.com/page/Dub_techno)
- [Vibes — Techno BPM Chart](https://vibesdj.io/dj-tools/techno-bpm-chart)

Построение сетов и энергия:
- [SetFlow — DJ Set Energy Flow](https://www.setflow.app/blog/dj-set-energy-flow)
- [Mixgraph — Energy Flow Guide](https://www.mixgraph.io/learn/energy-flow-guide)
- [Mixgraph — DJ Set Planning Guide](https://www.mixgraph.io/learn/dj-set-planning-guide)
- [DJ.Studio — Anatomy of a Great DJ Mix](https://dj.studio/blog/anatomy-great-dj-mix-structure-energy-flow-transition-logic)
- [Vibes — Set Composition](https://vibesdj.io/learn/techniques/set-composition)
- [Harmonyset — DJ Set Energy Flow & BPM](https://www.harmonyset.com/guides/dj-set-energy-flow)
- [Digital DJ Tips — Warm Up Sets](https://www.digitaldjtips.com/how-to-dj-warm-up-sets/)

FastMCP:
- [FastMCP — Prompts (servers/prompts)](https://gofastmcp.com/servers/prompts)

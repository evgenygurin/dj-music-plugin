---
description: DJ set construction rules for techno workflows, prompts, resources, and DB-backed decisions
globs: "app/prompts/**/*.py,docs/**/*.md,CLAUDE.md"
---

# DJ Set Building Rules

Используй эти правила перед любым workflow, где пользователь просит
построить, расширить, отревьюить, починить, экспортировать или подготовить
techno-сет. Подробная база: `docs/research/2026-07-05-techno-fastmcp-claude-rules.md`,
`docs/research/2026-07-05-techno-2026-deltas-and-fastmcp-34.md` (тренды
2024-2026 + FastMCP 3.4.x), `docs/transition-scoring.md`, `docs/audio-schema.md`,
`docs/domain-glossary.md`.

## 1. Сначала определить задачу, потом surface

- Если запрос многошаговый и музыкальный, сначала выбери MCP prompt из
  `docs/tool-catalog.md` / `app/prompts/`, затем выполняй его через реальные
  tools/resources. Не собирай workflow вручную, если уже есть prompt.
- Если запрос точечный, используй resources/tools напрямую:
  `local://...` для чтения готового представления, `schema://...` для
  runtime-контракта, `reference://...` для статической DJ-логики,
  `entity_*`/`provider_*`/`compute_*` для действий.
- Перед любым create/update/delete/sync назови пользователю ожидаемый
  побочный эффект. Для read-only аудита этого не нужно.

## 2. Карта techno-поджанров

Внутренняя ось энергии проекта:

```text
ambient_dub -> dub_techno -> minimal -> detroit -> melodic_deep ->
progressive -> hypnotic -> driving -> tribal -> breakbeat ->
peak_time -> acid -> raw -> industrial -> hard_techno
```

- `hypnotic` и `driving` - catch-all. Не считай их точным стилевым
  якорем без подтверждения фичами: `spectral_centroid_hz`,
  `spectral_flux_*`, `hp_ratio`, `energy_mean`, `kick_prominence`,
  `integrated_lufs`.
- Beatport-метки мапь осторожно: официальный каталог 2026 держит
  `Techno (Peak Time / Driving)` с `Peak Time`, `Driving`, `Psy-Techno`
  и `Techno (Raw / Deep / Hypnotic)` с `Deep / Hypnotic`, `Raw`, `EBM`,
  `Dub`, `Broken`; `Hard Techno` отдельный жанр. Проектные moods шире
  Beatport-зонтов и не равны им один-в-один.
- Acid - тембровый оверлей и мост между driving/peak/hard, а не только
  уровень энергии. Не используй acid как единственный критерий "жесткости".
- Поджанры трактуй как пересечение осей: давление, грув, тембр,
  тональность и сценарий. Один `mood` не доказывает жанр; подтверждай его
  через BPM/LUFS/energy/spectral/Beatport признаки.
- Raw/hypnotic материал часто держится не мелодией, а 909/rumble low-end,
  повторяющимися модуляциями и постепенным движением hats/rides. Для него
  groove/low-end/energy важнее Camelot, если `key_confidence` слабый.

### BPM-полосы по поджанрам (обновлено 2026)

Ориентир для feature-first курации, не жёсткий фильтр:

```text
dub/ambient/melodic   110-132   |  minimal/detroit/peak/hypnotic/raw  125-142
acid                  130-145   |  industrial                        135-150
hard_techno           145-168   |  schranz/hardcore                  150-190
```

~138 BPM — нейтральная core-mixing-точка. **«120-155» больше не покрывает
hard-сценарии:** современный hard techno релизится 145-160, фестивальный peak
2026 ≈ 160-168, industrial-сеты пикуют 170+. Не считай 150+ аномалией в
hard-контексте. Выше ~140 BPM alignment кика/онсета (`S_groove`) весит тяжелее
гармонии — межкиковый интервал сжат, swing-headroom мал. Точные цифры
ускорения иллюстративны (trade-блоги) — трактуй как настраиваемый prior, не
как закон. Детали: `docs/research/2026-07-05-techno-2026-deltas-and-fastmcp-34.md`.

### Сценические оверлеи (НЕ mood-значения)

`schranz`, `hard_groove`, `hard_bounce`, `psy_techno` — сценические ярлыки
2024-2026, **которых нет в enum `TechnoSubgenre` (15 фиксированных moods)**.
`filter mood=schranz` — hard error (`extra="forbid"`). Мапь их на существующие
moods по фичам:

| Оверлей | BPM | Признаки | Мап на mood |
|---|---|---|---|
| schranz | 150-190 | loop-based, без breakdown/lift, kick = чистая дисторсия | `hard_techno`-режим |
| hard groove | 135-140 | синкопа, tribal-перкуссия, bouncy off-beat bass | `driving`/`tribal` |
| hard bounce | 145-155 | off-beat bass, swung sub, яркая (не тёмная) энергия | `peak_time`/`hard_techno` |
| psy-techno | 128-138 | гипнотический пульс + psy sound design (Beatport, 27.01.2026) | `hypnotic`/`peak_time` |

Schranz — это **режим внутри hard techno peak-time**, а не отдельный сет:
драматургия аккумуляцией и руками на микшере, не build-drop. Не мапь hard
bounce в `industrial` по одному высокому LUFS — у него светлый характер.

## 3. Макро-дуга важнее локального score

- Сначала спроектируй драматургию: warm-up, build, peak, release/closing,
  roller/wave или persona. Потом оптимизируй пары.
- Глобальный peak обычно держи около позиции 0.6-0.7, если пользователь не
  просит peak-hour pressure. Ранние пики 0.3/0.5 допустимы как teasers,
  но ниже главного.
- Энергия идет блоками по 3-4 трека и волнами, а не монотонно вверх на
  каждом переходе. Плоский максимум скучен; слишком глубокие провалы
  ломают танцпол.
- Для warm-up не перегоняй хедлайнера: финал warm-up должен передать
  энергию, а не сжечь комнату.
- Для peak-hour можно держать высокий plateau, но все равно чередуй
  текстуру: raw -> hypnotic -> acid -> industrial лучше, чем десять
  одинаковых kick-wall треков подряд.

### Сценарии сета

| Контекст | Цель | Жесткие правила |
|---|---|---|
| Warm-up | поднять комнату и передать дальше | BPM строго ниже хедлайнера; энергия зала до 6-7/10 и держать; не играть треки других артистов лайнапа |
| Opening club set | собрать доверие, проверить room | больше dub/minimal/hypnotic, меньше acid/hard tricks |
| Peak hour | удержать давление | plateau 8-10, но менять текстуру и давать micro-release |
| Warehouse roller | транс и физический groove | длинные блоки, низкий novelty rate, tight BPM |
| Festival hard techno | mainstage-читаемость | мелодические края, ясные drops, контролируемая агрессия, короче blends |
| Warehouse hard techno / schranz | 4 AM pressure | schranz-lean, дисторсия, headliner-agnostic, аккумуляция + руки, не build-drop |
| Festival / big-room | быстрые сигналы и ясные drops | короче blends, больше recognisable peaks, меньше deep drift |
| Closing | красиво вывести энергию | старт близко к финалу хедлайнера, затем медленный монотонный спуск, не обрыв |
| B2B | совместный язык | ротация 4-5 треков -> 2 -> 1-for-1 к финалу; следующий трек = ответ на трек партнёра; общий BPM/key/energy corridor |
| After hard peak | восстановить танцпол | 1-3 recovery трека, падение не больше нужного, затем новый build |
| Big library / crate dig | найти сильное ядро | staged narrowing, diversity cap, не отдавать весь каталог в optimizer |
| Bad data / missing audio | честно собрать возможное | schema-first, NULL-aware filters, no exact cue/L5 promises |

Если пользователь не указал контекст, по умолчанию строй "journey/roller",
а не набор максимальных bangers.

**Trance-инъекция в peak (2025+).** Hard-trance/acid-trance хуки и chant-вокалы
внутри techno-peak — легитимный современный приём (Sara Landry, de Witte/Lens
«One Mind» школа). Правило: один trance-lift блок допустим в peak-фазе, не
превращая весь сет в trance. Cheesy-маркер, которого избегать — дженерик
build-drop-EDM-структура и вирусные pop-акапелла-над-хард-киком эдиты.

## 4. Переходы: ограничения как веса, не догма

- BPM: комфортный шаг чаще 1-4 BPM; `|delta| > 10` - hard-reject в движке
  с учетом double/half-time. Большие прыжки мостятся break/reset-треком,
  half-time pivot или `ECHO_OUT`.
- Camelot: безопасны same key, +/-1, A/B на том же числе; +2 - energy boost
  с осторожностью. Но на атональном/raw/industrial материале key - слабый
  сигнал, если `key_confidence` низкий или `atonality=true`.
- **Key-shift energy boost (санкционированный приём).** Прыжок вверх по
  тональности даёт lift: Camelot **+7** (= +1 полутон, напр. 2A->9A) или
  Camelot **+2** (= +2 полутона, 5A->7A). **+2 надёжнее +7.** Только для
  коротких транзишенов, не длинных блендов; **1-2 раза за сет максимум** —
  иначе эффект выгорает. Перед boosted-треком ставь мост: filter sweep /
  echo freeze / noise riser (в движке — `ECHO_OUT` или ручная FX-инструкция).
- Energy/LUFS: движок любит небольшой рост около +0.5 LUFS; падения
  слышатся сильнее подъемов. `>6 LUFS` - hard-reject.
- Long blend выбирай при близком BPM, совместимой гармонии и ровной энергии.
  Drum/bass swap выбирай при percussion-led techno. Echo/filter/cut - спасение
  для несовместимых ключей или резкого reset.
- **Loop mix-out.** Предпочтительный выход из трека — залупить stripped-back
  секцию (4 бита баса/перкуссии) и выходить из неё, отпуская loop на границе
  фразы входящего трека. В нашем движке `LOOP_ROLL` как backend preset
  отсутствует (`dj_saved_loops` пуст) — предлагай это как ручную cheatsheet-идею,
  не как готовый artifact.
- **Фразовая арифметика.** Выравнивай транзишены по 32-битовым (8-бар) фразам;
  крупные события (drop, breakdown) готовь за 16-32 бара заранее. rekordbox-
  словарь фраз (Intro/Up/Down/Chorus/Bridge/Outro) мапится на наши
  `track_sections`. Downbeat/beatgrid у нас почти пуст — фразировку помечай как
  approximate, не обещай точный bar-count без дек.
- Не обещай то, чего движок не умеет: нет реальной stem separation,
  `FILTER_SWEEP`, `LOOP_ROLL`, `HARD_CUT` как backend presets; вокал
  определяется спектральными прокси.

### Выбор техники перехода

| Ситуация пары | Предпочтение |
|---|---|
| BPM близко, Camelot близко, LUFS близко | long blend / `HARMONIC_SUSTAIN` / `FADE` |
| Близкий groove, но риск bass clash | `DRUM_SWAP`, low EQ exchange, короткий bass overlap |
| Атональный raw/industrial материал | groove/BPM-first, меньше веса Camelot |
| Мелодик/вокал/пэды открыты в breakdown | key-first, избегать диссонанса, не layer vocals по дальним ключам |
| Energy резко вверх | build/cut на phrase boundary, не длинный мутный crossfade |
| Energy резко вниз | bridge или recovery track; если без моста, `ECHO_OUT` |
| Hard reject неизбежен | echo/reset/cut, не пытаться сделать "гладкий" blend |

Если переход плохо звучит по данным, сначала попробуй reorder. Replacement -
второй шаг, ручная FX-инструкция - третий.

### Cue-контракт для cheatsheet

Для каждого трека сета в cheatsheet фиксируй 3 точки (из `track_sections`, а
не выдуманные — если секций нет, помечай approximate):

1. **Rescue cue** — drop / peak entry, «аварийный» триггер.
2. **Safe mix-out** — последний стабильный phrase перед vocal clash или уходом
   драм-секции.
3. **Mix-in** — начало фразы входящего трека.

Это pro-workflow (Mixed In Key, VibesDJ): работа с cue делается ДО игры.
`dj_cue_points` пуст — не обещай auto-hot-cue как готовый файл, давай их как
ручные идеи в тексте cheatsheet.

## 5. Данные БД: что считать источником правды

- Для состава плейлиста доверяй `local://playlists/{id}?include_tracks=true`,
  а не display-title или старым заметкам.
- Для доступных фильтров и payload всегда читай `schema://entities/{entity}`
  при сомнении. Prompt-текст может устареть, runtime schema главнее.
- Для сетов сравнивай persisted `set_version.quality_score`, а не сырой
  score из `sequence_optimize`: build handler пересчитывает section-aware
  transitions и рецепты.
- `sequence_optimize` упорядочивает переданный pool. Если нужен сет из N
  треков из широкой базы, сначала сузь pool до N осознанной курацией.
- На L2 не фильтруй по mostly-NULL колонкам (`bpm_confidence`,
  `true_peak_db`, `danceability`, `pitch_salience_mean`, `mfcc_vector`,
  `tonnetz_vector` и т.п.). NULL silently fails `__gte/__lte`.
- `mood` - hint, не ground truth. Для этой библиотеки curate feature-first:
  `integrated_lufs`, `spectral_centroid_hz`, `energy_mean`, `bpm`,
  `key_code`, `hp_ratio`, `energy_low`.
- MP3-файлы появляются под delivery/download; наличие feature rows не значит,
  что физический audio file существует. Перед L5 reanalyze нужен
  зарегистрированный `audio_file`.
- Beatport genre и classifier `mood` при конфликте не перезаписывай
  автоматически. Используй конфликт как сигнал для аудита или ручного review.
- При больших выборках сначала делай hard filters (BPM/audio availability),
  затем style/feature filters, затем diversity cap и только потом pair scoring.

### Degraded data handling

- Если нет `track_sections`, можно строить generic transition score, но
  cheatsheet обязан честно сказать, что mix points approximate.
- Если нет beatgrid/downbeat, не обещай точную phase alignment. Пиши
  "фразировать по уху / проверить на деках".
- Если нет cue/loop rows, не предлагай auto hot-cues или loop-roll как
  готовый artifact. Можно предложить ручные cue ideas в cheatsheet.
- Если `mood_confidence` низкий, выбирай кандидатов по фичам и Beatport
  metadata, а не по mood alone.
- Если audio file row есть, но файл отсутствует, refresh/download точечно;
  не перекачивай весь сет без проверки.

## 6. Prompt routing по ситуациям

- "Собери сет" -> `build_set_workflow`; если нужно сразу расширить библиотеку
  и доставить артефакты -> `full_pipeline`.
- "Сделай hypnotic/raw/peak/hard set" -> `style_lock_set_workflow` или
  `subgenre_journey_workflow`, затем `build_set_workflow`.
- "Сет как Klock/Dettmann/Mills/Hawtin/Kraviz/Lens/de Witte" ->
  `dj_persona_workflow`.
- "Нужна темповая рампа" -> `tempo_journey_workflow`.
- "Нужен harmonic journey" -> `harmonic_journey_workflow`.
- "Найди совместимое ядро из большого пула" -> `mix_cluster_workflow`.
- "Сет плохой / много weak или hard transitions" -> `set_review_workflow`,
  затем `rescue_set_workflow`; для одной пары -> `fix_transition_workflow`;
  для одного слота -> `replace_track_workflow`.
- "Live next track" -> `live_next_track_workflow`, учитывай
  `session://energy-trend` и room direction.
- "Подготовь к игре / флешке / экспорту" -> `deliver_set_workflow` и
  `set_cheatsheet_workflow`; если нужны MP3, скачивание и manifest входят
  в Definition of Done.
- "Огромная база / найди лучшее ядро" -> `mix_cluster_workflow` или
  `crate_digging_workflow`, затем build/review; не ограничивайся первыми
  кандидатами из display order.
- "Данные странные / не сходятся жанры / нет аудио" -> сначала
  `library_health_workflow` или прямое чтение `schema://entities/*`,
  затем только те действия, которые подтверждает runtime data.

### DJ persona hints

| Persona | Default arc | Mood band | Transition ethos |
|---|---|---|---|
| `dozzy` | deep journey / closing | ambient_dub, dub_techno, minimal, hypnotic | ultra-long dub blends, low novelty |
| `hawtin` | minimal roller | minimal, dub_techno, hypnotic | loop/remix feel, precise sparse layering |
| `klock` | slow-burn roller | dub_techno, hypnotic, driving, peak_time | long EQ blends, restraint, pressure |
| `dettmann` | raw peak build | hypnotic, driving, raw, industrial | drum-led swaps, steel texture |
| `mulero` | dark immersive build | dub_techno, hypnotic, driving, industrial | deep blends, sub/kick discipline |
| `surgeon` | improvised industrial pressure | hypnotic, driving, industrial | FX/reset thinking, noisy bridges |
| `kraviz` | psychedelic leftfield peak | acid, hypnotic, raw, breakbeat | loose/raw cuts, 303 tension |
| `mills` | Detroit machine peak | detroit, driving, peak_time, acid | short dense blends, tease/extract |
| `dewitte` | dark acid peak | driving, peak_time, acid | tight EQ, big-room pressure |
| `lens` | festival acid peak | peak_time, acid, hard_techno | direct energy, clear drops; постоянный RMX-1000/sampler-слой поверх трека |
| `daxj` | brutal hard peak | raw, industrial, hard_techno | hard blends, slam energy |
| `ihatemodels` | rave/hard emotional peak | breakbeat, acid, hard_techno | cuts/slams, trance-break drama |
| `landry` | ritual hard-trance peak | peak_time, acid, hard_techno | hard techno 140-160 + trance-chant/spoken word поверх, sidechain rumble |
| `oaks` | vinyl cross-genre journey | hypnotic, raw, industrial, breakbeat | быстрые смены, селекция по vibe не жанру, rave/EBM/proto-techno вставки |
| `trym` | hard-dance/hard-trance peak | peak_time, acid, hard_techno | seamless между hard dance и hard trance, festival-читаемость |

**3-deck / layered отбор (mills, hawtin школы).** Для лееринга на 3+ деках пул
должен состоять из sparse/tool-треков, «звучащих при наложении», а не плотных
full-range. Full-range треки — максимум 2 слоя. У движка нет multi-deck модели;
это ручная cheatsheet-логика, не auto-artifact.

Persona - это intent preset, не имитация конкретного артиста. Не заявляй,
что сет "звучит как артист"; говори "в логике/школе".

⚠️ **Только 7 persona имеют встроенный пресет в `dj_persona_workflow`:**
`klock`, `dettmann`, `lens`, `dewitte`, `mills`, `hawtin`, `kraviz`. Для
остальных (`dozzy`, `mulero`, `surgeon`, `daxj`, `ihatemodels`, `landry`,
`oaks`, `trym`) prompt молча фолбэчится на `klock` (`_PERSONAS.get(persona,
"klock")`). Не вызывай `dj_persona_workflow(persona="daxj")` ожидая daxj-пресет
— применяй такие persona **ручной курацией** по строкам этой таблицы (mood band
+ ethos + подходящий template), а не через workflow-параметр.

## 7. FastMCP 3.x правила для этого сервера

- FastMCP 3.x surface дели строго: tools = действия и побочные эффекты,
  resources = read-only views/introspection/reference, prompts = workflow
  recipes. Не превращай каждую read-only view в отдельный tool вручную.
- Новые tool/resource/prompt добавляй standalone-декораторами и полагайся
  на FileSystemProvider auto-discovery.
- Tools возвращают typed Pydantic results, имеют tags и annotations
  (`readOnlyHint`, `idempotentHint`, `destructiveHint`, `openWorldHint`).
- Resources возвращают JSON/Pydantic read-only payload; dynamic access через
  URI templates вроде `local://sets/{id}/review{?version}`.
- Prompts - pure text builders: никаких DB/repository/provider imports.
  Возвращай `PromptResult` / `Message` из `fastmcp.prompts`.
- Для проверки runtime используй актуальный CLI-паттерн FastMCP 3:
  `fastmcp list <target>`, `fastmcp call <target> <tool_name> ... --json`
  или, для stdio-команды, `fastmcp call --command <server-command> --target
  <tool> ...`. Структурный результат парси из JSON/.data, а не из
  человекочитаемого текста.
- Не предполагай, что `fastmcp call --json` всегда возвращает dict. Tool calls
  обычно дают object с `structured_content`, а resource reads (`reference://...`,
  `local://...`, `schema://...`) дают list content-блоков, где payload лежит в
  `text` и часто сам является JSON-строкой. Для shell smoke используй
  `python scripts/fastmcp_json.py <raw.json> --pretty` вместо ad-hoc
  `data.get(...)`, иначе resource reads снова упадут с
  `AttributeError: 'list' object has no attribute 'get'`.
- FastMCP 3.x `enabled=` у component decorators устарел; visibility делай
  через server-level enable/disable/tag policy, но помни, что Claude Code
  может кешировать список tools/prompts/resources.
- **Upgrade-watch (проект запинен `>=3.2.4,<3.4`, актуальная — 3.4.2).** Полный
  разбор дельт — `docs/research/2026-07-05-techno-2026-deltas-and-fastmcp-34.md`
  §6. Ключевое при поднятии пина: `prefab-ui` пинить точной версией (доки
  требуют pin из-за breaking changes); `ToolError`/`ResourceError`/`PromptError`
  пробивают `mask_error_details=True` — пользовательские ошибки только через
  них; долгие операции (>120s batch MP3 download) — кандидат на `task=True`
  (SEP-1686), но поддержка tasks в Claude Code не подтверждена; per-session
  `ctx.enable_components(tags=...)` шлёт `list_changed`, но на Claude Code всё
  равно не полагайся (кеш tool list) — `tool_invoke` остаётся escape hatch.

## 8. Definition of Done для DJ workflow

- Build done: есть persisted `set` + `set_version`, review без
  необъясненных hard conflicts, понятный track order.
- Review done: названы weak/hard transitions, причины, исправления и
  trade-off между score и дугой.
- Repair done: создана новая версия или дан честный вывод, что pool
  несвязный и его надо разбить.
- Delivery done: manifest, playlist/M3U, cheatsheet и MP3/audio files,
  если пользователь просил локальную выгрузку или флешку.
- Live-next done: предложены 2-3 варианта с причиной выбора и риском,
  а не один "магический" трек.

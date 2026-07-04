# Techno + FastMCP 3.x: правила Claude Code для DJ Music Plugin

> Дата: 2026-07-05. Назначение: связать исследование техно-сетов,
> текущую модель данных `dj-music-plugin` и практики FastMCP 3.x в
> исполняемые правила для Claude Code. Краткая версия правил:
> `.claude/rules/dj-set-building.md`.

## 1. Что изменилось относительно старых research-доков

В репозитории уже есть глубокие исследования:

- `docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md`
- `docs/research/2026-06-22-techno-deep-dive-and-prompt-expansion.md`
- `docs/research/2026-06-23-techno-deep-research-and-set-construction.md`
- `docs/research/2026-06-23-track-feature-reference-and-set-construction.md`

Этот документ не заменяет их. Он фиксирует слой "как должен действовать
агент": какие данные считать источником правды, когда выбирать prompt,
когда читать resource, как не переобещать возможности движка и как
проектировать новые FastMCP artifacts в версии 3.x.

## 2. Внешняя карта techno-рынка

### Beatport как промышленная таксономия

Beatport в 2020 разделил общий techno-каталог на два больших зонта:
`Techno [Peak Time/Driving/Hard]` и `Techno [Raw/Deep/Hypnotic]`, объяснив
это широтой жанра и необходимостью дать нишевым стилям отдельную
навигацию. В актуальном списке доставляемых жанров Beatport Greenroom
(обновлен 2026-04-10) структура уточнена:

- `Techno (Peak Time / Driving)` -> `Peak Time`, `Driving`, `Psy-Techno`
- `Techno (Raw / Deep / Hypnotic)` -> `Deep / Hypnotic`, `Raw`, `EBM`,
  `Dub`, `Broken`
- `Hard Techno` вынесен отдельным жанром.

Вывод для плагина: поля Beatport полезны как внешний marketplace-сигнал,
но не должны подменять внутренний `mood` classifier. Внутренняя ось
проекта шире и музыкально детальнее:

```text
ambient_dub -> dub_techno -> minimal -> detroit -> melodic_deep ->
progressive -> hypnotic -> driving -> tribal -> breakbeat ->
peak_time -> acid -> raw -> industrial -> hard_techno
```

`hypnotic` и `driving` надо считать зонтичными / catch-all метками:
проверять их по фичам, а не только по строковому label.

### Harmonic и energy mixing

Pioneer DJ описывает harmonic mixing как выбор треков по совместимым
ключам, но отдельно подчеркивает, что диджеи могут намеренно использовать
диссонанс или играть с энергией комнаты. Mixed In Key формализует Camelot
и energy-level подход: ключи помогают избегать clash, а energy-level
помогает выбирать warm-up, peak и finale материал.

Вывод для движка: Camelot - сильный критерий для tonal/melodic/vocal
материала, но не абсолютный закон для raw, industrial, percussive и
atonal techno. Поэтому правила агента должны говорить "вес/ограничение",
а не "никогда".

## 3. Музыкальные правила, которые агент обязан применять

### Макро-дуга

1. Сначала выбрать форму: warm-up, classic journey, peak-hour, roller,
   wave/progressive, closing, persona или live-next.
2. Глобальный пик обычно ставить около 0.6-0.7 позиции сета; исключение -
   явный peak-hour pressure.
3. Энергию двигать блоками 3-4 трека, а не поднимать на каждом переходе.
4. После пика давать recovery 1-3 трека, иначе сет звучит плоско и
   утомительно.
5. Для warm-up соблюдать потолок: не играть хедлайнерский peak раньше
   следующего диджея.

### Микро-переходы

1. BPM: 1-4 BPM - нормальный шаг; >10 BPM - hard boundary в движке с
   учетом double/half-time.
2. Camelot: same key, +/-1, A/B same number - safe; +2 - energy boost;
   дальние прыжки возможны как короткий или cut/echo прием.
3. Energy: предпочтителен небольшой рост около +0.5 LUFS; падения
   слышатся сильнее подъемов; >6 LUFS - hard reject.
4. Low-end: два полноценных баса вместе почти всегда мутят микс; bass swap
   важнее красивого crossfade.
5. Long blend требует совместимости по BPM/key/energy; несовместимость
   спасается `ECHO_OUT`, drum cut/swap, break/reset или ручной filter idea.

## 4. Привязка к данным БД

| DJ-решение | Источник данных | Как использовать |
|---|---|---|
| Состав плейлиста | `local://playlists/{id}?include_tracks=true` | Считать canonical перед сборкой |
| BPM ramp | `track_audio_features_computed.bpm`, `bpm_stability`, `variable_tempo` | Фильтровать по стабильным темпам, избегать variable для long blend |
| Harmonic path | `key_code`, `key_confidence`, `atonality`, `reference://camelot` | Camelot как weight; снижать важность на atonal/low confidence |
| Energy arc | `integrated_lufs`, `energy_mean`, `mood`, `track_sections.energy` | LUFS для переходов, energy/mood для макро-дуги |
| Subgenre journey | `mood`, `mood_confidence`, Beatport metadata | Feature-first curation, mood как hint |
| Pair compatibility | `transition_score_pool`, `local://transition/{a}/{b}/score` | Проверять weak/hard pairs до persist |
| Persisted quality | `entity_create(entity="set_version")`, `local://sets/{id}/review` | Сравнивать persisted section-aware score |
| Performance hints | `local://sets/{id}/cheatsheet`, `transition.fx_type` | Делать cue sheet, не придумывать недоступные FX |
| Физические файлы | `audio_file` / `dj_library_items` | Download перед L5 и delivery; features не равны MP3 |

Ключевой operational rule: `sequence_optimize` упорядочивает уже выбранный
pool. Он не должен получать 100 кандидатов, если пользователь попросил
15-трековый сет. Сначала курация, потом оптимизация.

## 5. Как Claude Code должен выбирать prompt

| Ситуация | Prompt |
|---|---|
| Общая сложная DJ-сессия | `dj_expert_session` |
| Собрать сет из плейлиста | `build_set_workflow` |
| Expand -> build -> deliver | `full_pipeline` |
| Экспорт / MP3 / cue sheet / YM delivery | `deliver_set_workflow`, затем `set_cheatsheet_workflow` |
| Harmonic path | `harmonic_journey_workflow` |
| BPM ramp | `tempo_journey_workflow` |
| Subgenre/style journey | `subgenre_journey_workflow`, `style_lock_set_workflow` |
| DJ persona | `dj_persona_workflow` |
| Кластер совместимых треков | `mix_cluster_workflow` |
| Ревью существующего сета | `set_review_workflow` |
| Много плохих переходов | `rescue_set_workflow` |
| Одна плохая пара | `fix_transition_workflow` |
| Один слабый слот | `replace_track_workflow` |
| Live next track | `live_next_track_workflow` |
| Library health / cleanup | `library_health_workflow`, `library_cleanup_workflow` |

Правило: если prompt покрывает ситуацию, использовать prompt. Ручные
`entity_*` / `provider_*` / `compute_*` цепочки допустимы для точечной
диагностики, проверки схемы, одиночного CRUD/action или когда prompt явно
не подходит.

## 6. FastMCP 3.x практики для этого проекта

По актуальной документации FastMCP 3.2.4:

- `@mcp.tool` / standalone `@tool`: действия, вычисления и побочные эффекты.
  Возвращать plain Python / typed structured content; в проекте - Pydantic
  response models.
- `@mcp.resource("scheme://...")` / standalone `@resource`: read-only data,
  static reference, DB-backed views, schema introspection. Dynamic access -
  URI templates с параметрами.
- `@mcp.prompt` / standalone `@prompt`: workflow instructions. FastMCP 3
  использует `fastmcp.prompts.Message` и `PromptResult`; допустимые return
  types - `str`, `list[Message | str]`, `PromptResult`.
- Для server runtime `mcp.run()` покрывает stdio/http/sse boilerplate; в этом
  проекте auto-discovery идет через FileSystemProvider и standalone
  decorators.
- CLI-проверка должна использовать `fastmcp call ... --json` для
  структурного результата, а не парсить human output.
- Tool annotations важны для клиентов: `readOnlyHint`, `idempotentHint`,
  `destructiveHint`, `openWorldHint`.

Вывод для будущих изменений: не плодить узкие tools для read-only
представлений и workflow. Read-only view - resource, повторяемый рецепт -
prompt, действие - tool.

## 7. Агентские playbook-и

### Построить сет с нуля

1. Уточнить или вывести из запроса: context, duration, energy target,
   subgenre/persona, source playlist/library, delivery needs.
2. Прочитать `reference://templates`, `reference://subgenres` и canonical
   playlist resource.
3. Сузить pool feature-first: BPM corridor, LUFS corridor, usable keys,
   style band, exclusions/likes.
4. Проверить coverage: analysis level, missing features, physical audio
   requirements.
5. Выбрать macro order: anchors, peak at 0.6-0.7 unless peak-hour, recovery
   windows, final handoff/closing.
6. Запустить optimization только на curated pool.
7. Persist `set` + `set_version`, затем читать review/cheatsheet.
8. Исправить weak/hard transitions reorder-first, replacement-second.
9. Если нужен deliverable, download MP3, refresh stale files, write manifest
   and M3U.

### Отревьюить сет

1. Читать `local://sets/{id}/review`, `full`, `narrative`, `cheatsheet`.
2. Разделить проблемы на macro и micro:
   - macro: плохая дуга, ранний peak, плоский plateau, wrong handoff;
   - micro: BPM/key/LUFS hard reject, bass clash, weak groove, bad section.
3. Не чинить macro-проблему заменой одной пары. Сначала reorder/arc.
4. Для micro-проблемы: explain pair -> bridge/reorder -> replacement ->
   emergency FX note.

### Live next track

1. Читать текущий track features и `session://energy-trend`.
2. Учитывать room direction: `up`, `flat`, `down`.
3. Давать 2-3 кандидата: safe, pressure, reset.
4. Для каждого назвать risk: key, LUFS drop/rise, BPM pull, bass overlap.
5. Не персистить без явного запроса; live-next обычно read-only.

### Delivery / USB / local export

1. Проверить persisted set/version, а не только draft order.
2. Скачать или refresh только отсутствующие/stale audio files.
3. Не считать `track_audio_features_computed` доказательством наличия MP3.
4. Финальный artifact должен включать manifest, ordered playlist/M3U,
   cheatsheet и audio directory, если пользователь просил файлы.
5. Отчет пользователю должен содержать конкретный filesystem path.

## 8. Anti-patterns

- **"GA все решит".** GA оптимизирует локальные пары; он может испортить
  macro arc. Дугу задает агент/шаблон/курация.
- **"Чем выше score, тем лучше сет".** Score pairwise; хороший set может
  уступить максимальному score ради tension/release.
- **"Mood label = жанр".** В этой библиотеке mood confidence часто слабый.
  Использовать как hint, не как единственный фильтр.
- **"Beatport genre = внутренний mood".** Beatport - marketplace taxonomy,
  проектный `mood` - аудио-классификация. Их надо мапить, не отождествлять.
- **"Harmonic mixing всегда обязателен".** Для melodic/vocal да; для
  atonal raw/industrial важнее groove/BPM/energy.
- **"Файлы есть, потому что features есть".** Features rows и physical MP3 -
  разные сущности.
- **"Prompt можно переписать произвольными именами".** Prompt content
  проверяется runtime schema tests; новые entity/filter/provider names без
  схемы - hard failure.
- **"Read-only view надо сделать tool".** В FastMCP 3.x read-only view -
  resource; workflow - prompt; tool - side effect/action.

## 9. Persona presets для `dj_persona_workflow`

Persona должна задавать intent, а не обещать копирование артиста.

| Persona | BPM feel | Palette | Agent instruction |
|---|---|---|---|
| Dozzy | 122-130 | ambient/dub/minimal/hypnotic | long low-pressure journey, avoid obvious peak drops |
| Hawtin | 125-132 | minimal/dub/hypnotic | sparse rolling structure, micro-variation, no crowded low-end |
| Klock | 128-134 | dub/hypnotic/driving/peak | restrained pressure, long EQ blends, late peak |
| Dettmann | 128-136 | hypnotic/driving/raw/industrial | raw metal texture, drum-led transitions |
| Mulero | 130-140 | dub/hypnotic/driving/industrial | dark immersive pressure, sub discipline |
| Surgeon | 130-145 | hypnotic/driving/industrial/noise | intentional resets, noisy bridges, avoid smoothness fetish |
| Kraviz | 130-145 | acid/hypnotic/raw/breakbeat | psychedelic disruptions, 303 tension, controlled looseness |
| Mills | 135-150 | detroit/driving/peak/acid | fast machine soul, short tease/extract transitions |
| de Witte | 134-145 | driving/peak/acid | direct dark acid pressure, clean EQ blends |
| Lens | 134-145 | peak/acid/hard | festival-readable energy, clear drops |
| Dax J | 140-155 | raw/industrial/hard | high-impact hard blends, no delicate melodic assumptions |
| I Hate Models | 145-160 | breakbeat/acid/hard/rave | emotional hard-rave contrast, cuts and break drama |

## 10. FastMCP artifact checklist

When adding or changing the MCP server surface:

| Artifact | Use when | Must satisfy |
|---|---|---|
| Tool | mutates state, calls provider, computes expensive result, persists artifact | typed args, Pydantic result, tags, annotations, no manual commit |
| Resource | reads entity view, schema, session state, static reference | read-only, URI template, JSON/Pydantic, typed errors |
| Prompt | instructs an LLM through a repeatable workflow | pure text builder, `PromptResult`/`Message`, real tool/resource names only |
| Handler | entity create/update/delete has side effect | registered through EntityRegistry, UoW-managed |
| Transform | expose resources/prompts for limited clients | centralized in server transforms, no duplicate business logic |

Validation rule: a documentation-only change can use grep/diff checks.
Changing prompt text should run `tests/prompts/test_prompt_content_correctness.py`.
Changing tools/resources/prompts code should also run registration tests and
`make check` when feasible.

## 11. Источники

- Beatport Greenroom, актуальный список жанров и поджанров:
  https://greenroomsupport.beatport.com/hc/en-us/articles/41043520429076-Beatport-Genres-Including-NEW-Open-Format-Genres
- Beatportal, объяснение split Techno categories:
  https://www.beatportal.com/articles/440314-beatport-is-expanding-its-techno-categories
- DJ Mag, краткое отраслевое резюме split:
  https://djmag.com/news/beatport-expands-its-techno-categories-peak-raw-hypnotic-and-more
- Pioneer DJ, harmonic mixing as practice, not hard law:
  https://blog.pioneerdj.com/djtips/how-do-djs-approach-harmonic-mixing/
- Mixed In Key, Camelot and energy-level workflow:
  https://mixedinkey.com/harmonic-mixing-guide/
- FastMCP 3.2.4 docs queried via Context7, canonical docs:
  https://gofastmcp.com/

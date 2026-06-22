# Techno, построение сетов и проектирование MCP-промтов

> Глубокое исследование предметной области (техно-поджанры, правила
> построения сетов, техники диджеев) + проекция на данные в БД проекта
> + дизайн нового каталога workflow-промтов для MCP-сервера.
>
> Дата: 2026-06-22. Связано с: [transition-scoring.md](../transition-scoring.md),
> [domain-glossary.md](../domain-glossary.md),
> [audio-schema.md](../audio-schema.md), [tool-catalog.md](../tool-catalog.md).

---

## 1. Зачем это исследование

MCP-сервер DJ Music Plugin — это «движок», который умеет считать
транзишены, оптимизировать порядок треков, аудитить библиотеку и
синхронизироваться с Яндекс Музыкой. Но **движок не равен мастерству
диджея**. Реальная ценность появляется, когда LLM (Claude Code как
основной клиент) понимает *как именно* профессиональные техно-диджеи
строят сеты, и умеет переводить это в последовательность вызовов
`entity_*` / `provider_*` / `compute_*` / `*_sync` инструментов и чтений
`local://` / `reference://` ресурсов.

Промты в FastMCP — это именно тот слой, где доменное знание превращается
в воспроизводимый рецепт. Этот документ:

1. систематизирует знание о техно (поджанры, энергетика, гармония, фразировка);
2. описывает каноны построения сетов и фишки конкретных школ диджеинга;
3. показывает, какие данные в нашей БД за что отвечают;
4. выводит каталог из 19 промтов (6 старых + 13 новых), покрывающих
   «все ситуации».

---

## 2. Поджанры техно (карта энергии)

Проект использует **15 поджанров**, упорядоченных по энергии (low → high)
— см. `reference://subgenres` и `app/audio/classification/profiles.py`:

```text
ambient_dub → dub_techno → minimal → detroit → melodic_deep →
progressive → hypnotic → driving → tribal → breakbeat →
peak_time → acid → raw → industrial → hard_techno
```

Краткая характеристика ключевых семейств (сведено из источников §10 и
сверено с дискриминирующими фичами mood-классификатора):

| Поджанр | Темп (BPM) | Звуковая подпись | Дискриминирующие фичи (наши) |
|---|---|---|---|
| **ambient_dub** | 118–124 | бестактовые текстуры, реверберация, «дрейф» | `energy_mean` low, `hp_ratio` high |
| **dub_techno** | 120–126 | Basic Channel: эхо-аккорды, широкий LRA, погружение | `loudness_range_lu` wide |
| **minimal** | 124–130 | редукция, микро-вариации, тихий кик | `kick_prominence` low |
| **detroit** | 128–134 | машинная душевность, струнные стэбы (Mills/UR) | сбалансированный спектр |
| **melodic_deep** | 122–128 | эмоциональные пэды, мелодика | `spectral_centroid` low |
| **progressive** | 126–132 | долгие билды, плавный набор | медленный `energy_slope` |
| **hypnotic** | 130–138 | циклический транс, фильтр-движения (Kraviz/Klock) | `spectral_flux_std` low (повторяемость) |
| **driving** | 132–140 | прямой кач, «локомотив» | catch-all, штрафуется |
| **tribal** | 132–140 | перкуссия, полиритмия | onset density high |
| **breakbeat** | 130–145 | ломаный бит | `spectral_flux_std` high |
| **peak_time** | 134–144 | мейнфлор-бэнгеры, мощный кик | `kick_prominence` high |
| **acid** | 136–146 | резонанс TB-303, «сквелч» | `spectral_centroid` high, `pitch_salience` high |
| **raw** | 138–148 | лоу-фай, сырость, хардвер-джемы | `crest_factor` нестабилен |
| **industrial** | 140–150 | дисторшн, металл, агрессия (Klock/Perc) | `hp_ratio` low, узкий LRA |
| **hard_techno** | 145–160 | бруталистский кач, рейв-интенсивность | `energy_mean` max |

`driving` и `hypnotic` — **catch-all**: классификатор штрафует их
(`catch_all_penalty`), чтобы они не «съедали» всё подряд. Это важно для
промтов: при планировании журнала по поджанрам нельзя опираться на эти
два как на устойчивые «якоря».

**Ключевой вывод для промтов:** порядок поджанров = ось энергии. Журнал
по поджанрам (subgenre journey) должен двигаться по этому списку плавно
(±1–2 шага) либо делать *осознанный* контраст-прыжок как драматургический
приём.

---

## 3. Анатомия техно-сета

### 3.1 Энергетическая дуга

Классическая форма — **warm up → build → peak → cool down**. Толпа
реагирует на *нарратив*, а не на отдельные бэнгеры: грамотно выстроенная
дуга из средних треков бьёт случайный набор хитов (§5, §6).

Наши 8 шаблонов (`reference://templates`, `app/domain/template/registry.py`)
кодируют эту дугу как набор слотов `(position, mood, target_lufs,
bpm_min, bpm_max, duration, tolerance)`:

| Шаблон | Длит. | Дуга |
|---|---|---|
| `warm_up_30` | 30 | пологий опенер, ambient_dub → melodic_deep |
| `classic_60` | 60 | build-peak-release, minimal → peak_time → cool |
| `peak_hour_60` | 60 | релентлесс, driving/acid/industrial |
| `roller_90` | 90 | устойчивый кач, minimal/driving/hypnotic |
| `progressive_120` | 120 | медленный 2-часовой набор |
| `wave_120` | 120 | несколько волн build-release |
| `closing_60` | 60 | свёртка энергии, driving → ambient_dub |
| `full_library` | — | без mood-якорей, только оптимизация порядка |

`infer_intent()` (`app/domain/transition/intent.py`) использует
**per-template таблицу фаз** `(warmup_end, peak_start, peak_end)` — один и
тот же `set_position=0.15` трактуется как «уже пик» в `peak_hour_60` и как
«ещё разогрев» в `closing_60`. Промты обязаны передавать `template`, иначе
интент считается по дефолтным 0.20/0.50/0.85.

### 3.2 Фразировка (phrasing)

Танцевальная музыка строится фразами по **32 (и 64) бита**. Переходы
выравниваются по границам фраз; «дроп поверх куплета» — только намеренно
(§2, §6). В нашей БД границы секций живут в `track_sections`
(~70 секций/трек), а `dj_beatgrids.first_downbeat_ms` дал бы фазу даунбита
— но покрытие ~0.1%, поэтому mix-point detector использует fallback `0`
(см. [audio-schema.md](../audio-schema.md)). Для 4/4 техно с интро на
`t=0` это приемлемо.

### 3.3 Темповый менеджмент

Небольшие плановые сдвиги (±2–4 BPM) незаметны, но дают кумулятивное
ускорение: +1 BPM за транзишен через 10 треков = разгон 122→132, который
дансфлор *чувствует*, но не *слышит* (§2). Большие прыжки прячут в
брейкдауны, half/double-time или «reset»-трек.

Наш hard-constraint: `|ΔBPM| > 10` → `hard_reject` (с double/half-time
awareness). Gaussian `S_bpm` с `σ=10` даёт 0.88 на Δ=5 (нормальный
sync-workflow), 0.61 на Δ=10 (граница).

### 3.4 Гармонический микс (Camelot)

Колесо Camelot: 24 ключа, A=minor (внутр.), B=major (внешн.). Безопасные
ходы из любого ключа (§2, §9):

- **тот же ключ** (8A→8A) — идеально;
- **±1 по колесу** (8A→7A / 9A) — соседние ключи;
- **A↔B на том же числе** (8A→8B) — смена настроения minor↔major
  (minor=темнее/драйвовее, major=светлее/выше);
- **+2 (energy boost)** (8A→10A) — больше гармонической дистанции, делается
  *быстро*, как приём нагнетания.

Наши `CAMELOT_BASE_SCORES = {0:1.0, 1:0.9, 2:0.6, 3:0.3, 4:0.1}`,
hard-reject при `camelot_distance ≥ 5`. Драматургия ключа: держать 2–3
трека в одном ключе, потом сдвиг — толпа не слышит смену ключа осознанно,
но *чувствует* смену настроения.

### 3.5 Энергетические уровни

Mixed In Key популяризировал шкалу energy 1–10 на трек — инструмент для
выбора «трека-кульминации» против «трека-разогрева» (§9). У нас аналог —
`integrated_lufs` + 7-полосный energy breakdown + `mood`/`mood_confidence`;
предпочтительный подъём +0.5 LUFS на транзишене (`ENERGY_PREFERRED_RISE`),
hard-reject при разрыве >6 LUFS.

---

## 4. Техники переходов (и как они отражены в движке)

Сведено из источников §7, §8 и спроецировано на наши 7 Neural Mix пресетов
(`app/domain/transition/neural_mix.py`, picker в `picker.py`):

| Техника (индустрия) | Суть | Наш пресет |
|---|---|---|
| **Bassline swap / EQ trade** | вход с убранным low, обмен басом по EQ | `DRUM_SWAP` / bass-stem routing |
| **Long blend (32 бара)** | музыкальное наложение при высокой гармонии | `FADE` / `HARMONIC_SUSTAIN` |
| **Echo out** | эхо-хвост на последнем бите, увод фейдера | `ECHO_OUT` (rescue для hard_reject) |
| **Filter fade** | LP/HP-фильтр спасает несовместимый микс | *планируется* `FILTER_SWEEP` (Phase 2) |
| **Loop roll / tension build** | луп + нарастающий фильтр/реверб | аппрокс. `DRUM_CUT bars=1` |
| **Double drop** | два дропа сходятся на даунбите | ручной приём, не автоматизирован |
| **Acapella layering** | вокал поверх чужого бита | `VOCAL_SUSTAIN` / `VOCAL_CUT` |

Picker — чистая функция на `TransitionScore` + `TrackFeatures` + контекст
секций: 7 правил, first-match-wins (hard_reject→ECHO_OUT, drum-only→
DRUM_SWAP/CUT/FADE, vocal-active→VOCAL_*, harmonic motif→HARMONIC_SUSTAIN,
energy-slam→DRUM_CUT, ambient/cooldown→FADE, default→ECHO_OUT). Каждый
персист-транзишен несёт материализованный 32-баровый рецепт
(`NeuralMixRecipe`).

**Известные пробелы (важно для честности промтов):** нет реального
stem-separation (вокал детектится тремя спектральными прокси), нет
`FILTER_SWEEP`/`LOOP_ROLL`/`HARD_CUT` как отдельных пресетов, Camelot-веса
статичны по поджанрам. Промты не должны обещать того, чего движок не умеет.

---

## 5. Школы и фишки диджеев

Спроецировано на наши шаблоны/настройки — это «персоны», которые промты
могут предлагать как пресеты намерения:

- **Берлинская школа (Ben Klock / Marcel Dettmann, Berghain).** Гипнотика
  и постепенные билды; мастерство *селекции* не меньше техники; элементы
  трека как кирпичики — басы/вокал/хэты вводятся быстро и плавно, треки
  «дразнятся» in/out. Зернистый warehouse-саунд (Basic Channel depth +
  loopy repetition). → наши `hypnotic`/`driving`/`roller_90`,
  `HARMONIC_SUSTAIN`, длинные блэнды.
- **Acid/hard школа (Amelie Lens, Charlotte de Witte).** Резонанс 303,
  высокий темп, прямолинейный кач. → `acid`/`peak_time`/`hard_techno`,
  `peak_hour_60`.
- **Detroit/UR (Jeff Mills).** Скоростная вёртушка, три деки, машинная
  душевность. → `detroit`, плотная фразировка.
- **Warm-up philosophy.** Сдержанность, «не играй все бэнгеры», никогда не
  превышай BPM хедлайнера, не оставляй следующего диджея в безумном темпе
  (§3, §4). → `warm_up_30`, role=opener.
- **B2B этика.** Договориться заранее: кто открывает/закрывает, как
  чередовать, кто рулит FX; читать энергию *вместе*; библиотека должна быть
  размечена по BPM/key/energy для быстрой реакции (§3, §4). → b2b-промт.

---

## 6. Как данные в БД связаны с построением сетов

| Задача диджея | Данные/слой | Инструмент/ресурс |
|---|---|---|
| Каталог треков | `tracks` (23.9k) | `entity_list(entity="track")` |
| Скоринг-фичи (BPM/key/LUFS/энергия) | `track_audio_features_computed` (~99%) | `entity_list(entity="track_features", fields="scoring")` |
| Поджанр трека | `mood`/`mood_confidence` | те же фичи |
| Границы секций (интро/дроп/брейк) | `track_sections` | `local://tracks/{id}/audit`, mix-points |
| Camelot-совместимость | `key_code` + static `keys` | `reference://camelot`, `local://transition/.../score` |
| Совместимость пары | расчёт | `transition_score_pool`, `local://transition/{a}/{b}/score` |
| Порядок под дугу | GA/greedy + template | `sequence_optimize`, `entity_create(entity="set_version")` |
| Аудит качества | audit rules | `local://playlists/{id}/audit`, `local://tracks/{id}/audit` |
| Память вкуса | `track_feedback`, `track_affinity` | `entity_*` |
| История переходов | `transition_history` | `local://transition_history/best_pairs` |
| Физические MP3 | `dj_library_items` (97!) | `entity_*(entity="audio_file")` |
| Синк с YM | provider + sync | `playlist_sync`, `provider_*` |
| Адаптивная подсказка | расчёт | `local://tracks/{id}/suggest_next`, `session://energy-trend` |
| Замена слота | расчёт | `local://tracks/{id}/suggest_replacement/{set_id}/{position}` |

**Degraded зоны (промты должны учитывать):** downbeat alignment, cue-points,
loops — пустые таблицы; MP3 качаются только под `deliver_set_workflow`.

---

## 7. Каталог промтов (дизайн)

Принцип: **один промт = один воспроизводимый сценарий**, текстовый рецепт,
цепляющий tool-surface. Промты не импортируют репозитории/провайдеры
(чистые text-builders), возвращают `fastmcp.prompts.PromptResult`.

### 7.1 Существующие (6)

`dj_expert_session`, `build_set_workflow`, `deliver_set_workflow`,
`expand_playlist_workflow`, `full_pipeline`, `quick_mix_check`.

### 7.2 Новые (13) — покрытие «всех ситуаций»

| Промт | Сценарий | Главные инструменты |
|---|---|---|
| `library_health_workflow` | здоровье библиотеки: покрытие анализом, распределение BPM/key/mood, мусор | `entity_aggregate`, `ui_library_dashboard`, audit |
| `analyze_library_workflow` | пакетный анализ непроанализированных / апгрейд тира | `entity_list(has_features)`, `entity_create(track_features)` |
| `harmonic_journey_workflow` | гармонический журнал по Camelot | `reference://camelot`, `entity_aggregate(key_code)` |
| `subgenre_journey_workflow` | журнал по поджанрам (энергетическая ось) | `reference://subgenres`, `entity_aggregate(mood)` |
| `scenario_set_workflow` | пресет-сценарий: warmup / peak / closing / roller / wave | role-guidance + `sequence_optimize` |
| `set_review_workflow` | критика готового сета + фиксы | `local://sets/{id}/review`, `narrative`, `ui_set_view` |
| `fix_transition_workflow` | диагноз и ремонт слабого/hard-reject перехода | `transition/.../explain`, `suggest_next`, `ui_transition_score` |
| `replace_track_workflow` | замена слабого слота лучшим кандидатом | `suggest_replacement`, `entity_create(set_version)` |
| `extend_set_workflow` | удлинить готовый сет, сохранив дугу | `suggest_next`, `sequence_optimize` |
| `b2b_planning_workflow` | back-to-back: раздел дуги, чередование, FX-договор | template-split + audit |
| `crate_digging_workflow` | discovery-first дайвинг + курирование | `provider_search/read`, `track_affinity` |
| `taste_profile_workflow` | управление вкусом: feedback/affinity, бан/лайк | `entity_*(track_feedback/affinity)` |
| `playlist_sync_workflow` | pull/push/diff с YM + conflict-gate | `playlist_sync`, `provider_read` |

Итого **19 промтов**. Каждый новый промт прогоняется через
content-correctness guard (`tests/prompts/test_prompt_content_correctness.py`):
все `entity=` ссылки — зарегистрированные сущности либо адаптерные
provider-сущности; все `fields=` пресеты существуют.

---

## 8. Лучшие практики FastMCP v3+ для промтов (применены)

Из официальной документации (gofastmcp.com/servers/prompts) и нашего
канона (`.claude/rules/`):

1. **Декоратор + сигнатура.** Standalone `@prompt` из `fastmcp.prompts`;
   без `*args`/`**kwargs` — нужна полная схема параметров. Параметры без
   дефолта = required, с дефолтом = optional.
2. **Типы простые.** `str`, `int`, `bool`, `list[int]`, `dict[str,str]` —
   FastMCP сам конвертит JSON-строки аргументов; избегать вложенных
   структур/классов.
3. **Документация аргументов** — docstring (Google/NumPy/Sphinx) или
   `Field(description=...)`; explicit annotations перекрывают docstring.
4. **Возвращаемые типы.** `str` (один user-message), `list[Message]`
   (диалог с ролями user/assistant), либо `PromptResult` для полного
   контроля (`messages` + `description` + `meta`). Мы используем
   `PromptResult` + `Message` ради `description`/`meta` (version stamping).
5. **Метаданные.** `name`, `description` (≤ полезно кратко), `tags`
   (`namespace:workflow` + категория), `meta` (`PROMPT_META` с version).
6. **FSP auto-discovery.** Один промт на файл, имя файла = имя промта;
   FileSystemProvider находит рекурсивно — никакой ручной регистрации.
7. **Чистота.** Промты не импортируют repositories/tools/providers — только
   собирают текст, который ведёт LLM по tool-surface.
8. **Честность контракта.** Каждое имя сущности/провайдера/пресета в теле
   промта реально существует в рантайме (pinned guard-тестами) — это
   прямой урок аудита 2026-04-27 (4 промта врали про контракты).

---

## 9. Источники

- [Techno UK — Top Techno Subgenres 2025](https://techno.org.uk/top-techno-subgenres-explained-2025/)
- [Samplesound — Techno Explained: Styles & Subgenres](https://www.samplesoundmusic.com/blogs/news/techno-explained-styles-sounds-and-subgenres-you-should-know)
- [Playful Mag — Techno Subgenres: Acid, Minimal, Industrial](https://www.playfulmag.com/post/techno-subgenres-understanding-acid-minimal-industrial-and-more)
- [SetFlow — DJ Set Energy Flow](https://www.setflow.app/blog/dj-set-energy-flow)
- [Mixed In Key — Control The Energy Level](https://mixedinkey.com/book/control-the-energy-level-of-your-dj-sets/)
- [Mixed In Key — Harmonic Mixing Guide](https://mixedinkey.com/harmonic-mixing-guide/)
- [DJ.Studio — The DJ's Guide to the Camelot Wheel](https://dj.studio/blog/camelot-wheel)
- [Music City SF — The Camelot Wheel Explained (2025)](https://musiccitysf.com/accelerator-blog/camelot-wheel-dj-mixing-guide/)
- [Mixgraph — DJ Set Planning Guide](https://www.mixgraph.io/learn/dj-set-planning-guide)
- [Mixgraph — DJ Transition Techniques](https://www.mixgraph.io/learn/dj-transition-techniques)
- [DJ.Studio — The DJ Transitions Playbook](https://dj.studio/blog/the-dj-transitions-playbook)
- [Digital DJ Tips — How To DJ Warm Up Sets](https://www.digitaldjtips.com/how-to-dj-warm-up-sets/)
- [Red Bull — How to play a warm-up DJ set](https://www.redbull.com/gb-en/warm-up-dj-sets)
- [Mixmag — B2B etiquette](https://mixmag.net/feature/b2b-etiquette-a-guide-to-the-subtle-art-of-sharing-a-dj-booth-1)
- [The DJ Mixtape — How To DJ Back To Back (B2B)](https://thedjmixtape.com/b2b-djing/)
- [RA — Ben Klock & Marcel Dettmann at Panorama Bar](https://ra.co/reviews/19850)
- [Google Arts & Culture — Dettmann & Klock: The DJs of Berghain](https://artsandculture.google.com/story/marcel-dettmann-amp-ben-klock-the-djs-of-berghain-groove/fgUROS35yB6j-g)
- [FastMCP — Prompts (servers/prompts)](https://gofastmcp.com/servers/prompts)
</content>
</invoke>

# Techno 2024–2026 deltas + FastMCP 3.4.x: обновление правил Claude Code

> Дата: 2026-07-05. Назначение: зафиксировать то, что появилось/изменилось
> ПОСЛЕ предыдущих research-доков — сценические тренды 2024–2026, крафт-детали
> подготовки сетов, именные техники диджеев и практики FastMCP 3.3–3.4.x.
> Исполняемая выжимка — в `.claude/rules/dj-set-building.md` (музыка) и
> `.claude/rules/tools.md` / `.claude/rules/prompts.md` (FastMCP surface).
>
> Базовые доки, которые этот файл НЕ заменяет, а дополняет:
> - `docs/research/2026-06-23-techno-deep-research-and-set-construction.md`
> - `docs/research/2026-06-23-track-feature-reference-and-set-construction.md`
> - `docs/research/2026-07-05-techno-fastmcp-claude-rules.md`
> - `docs/transition-scoring.md`, `docs/audio-schema.md`

## 0. TL;DR — что реально новое

1. **BPM-потолок жанра пополз вверх.** Современный hard techno — релизы
   145–160, фестивальный peak 2026 ≈ 160–168, industrial 170+. «120–155»
   больше не покрывает hard-сценарии.
2. **Schranz как режим, не поджанр.** Loop-based, без breakdown/мелодического
   lift, kick = чистая дисторсия. Драматургия — аккумуляцией и руками, не
   build-drop. Используется как peak-time tools внутри hard techno.
3. **Новые сценические ярлыки:** hard groove (135–140, синкопа/tribal, bouncy
   bass), hard bounce (145–155, off-beat bass, яркая энергия), trance-инъекция
   в peak (2025+). Beatport добавил **Psy-Techno** (27.01.2026).
4. **Санкционированные крафт-приёмы:** key-shift energy boost (Camelot +7 / +2),
   loop mix-out (4-битовый залуп stripped-back секции), фразовая арифметика
   (32-бита/8 баров), cue-контракт из 3 точек на трек.
5. **Warm-up/closing/B2B квантифицированы** (BPM-потолки, целевая энергия зала,
   ротация B2B).
6. **Data-driven якоря сошлись** с движком: Mixed In Key Energy 1–10 ↔
   `energy_mean`, rekordbox phrase labels ↔ `track_sections`, stem-first
   транзишены подтверждены академически (Mosaikbox, ISMIR 2024) и продуктово
   (Engine DJ 4.2, djay Pro 5).
7. **FastMCP — актуальная 3.4.2** (проект пока запинен `>=3.2.4,<3.4`). Дельты
   — apps/tasks/visibility/versioning; см. §6, все помечены как upgrade-watch.

Все ⚠️-цифры трендов — направление достоверно, точные числа иллюстративны
(SEO/trade-блоги), хардкодить как **настраиваемый prior**, не как допущение.

---

## 1. Сцена 2024–2026: hard techno / schranz / hard groove / trance / bounce

### BPM ушёл вверх

- Релизная норма hard techno — 145–160 BPM; в 2024 фестивальный «рабочий
  центр» ≈150, к 2026 sweet spot 160–168, industrial-сеты пикуют 170+.
  ([Hardcultr: Hard Techno vs Schranz](https://www.hardcultr.com/news/hard-techno-vs-schranz-explained-2026/),
  [Hardcultr: 10 artists 2026](https://www.hardcultr.com/news/10-hard-techno-hard-trance-artists-set-to-dominate/))
- **Следствие для скоринга:** на 145+ BPM межкиковый интервал сжимается,
  swing-headroom коллапсирует → «вертикальный, militaristic» звук; alignment
  кика/онсета (`S_groove`) надо весить тяжелее гармонии выше ~140 BPM.

### Schranz — режим, а не mood

- Loop-based, **без breakdown, без мелодического lift**; энергия из
  аккумуляции и работы руками на микшере. Kick: hard techno = дисторшн +
  тональный counter/sub под ним; schranz = чистая дисторсия без тонального
  контента. Sara Landry, Charlotte de Witte, I Hate Models, Kobosil «рутинно
  бросают schranz-tools в peak-time».
  ([Hardcultr](https://www.hardcultr.com/news/hard-techno-vs-schranz-explained-2026/))
- Измеримость волны: **+83% schranz-загрузок на SoundCloud за 2025**
  (IMS Electronic Music Business Report 2025/26).
  ([weraveyou / IMS Ibiza 2026](https://weraveyou.com/2026/04/schranz-soundcloud-83-percent-ims-2026/))
- **Две сценические ветки hard techno (2026):** «Festival Hard Techno»
  (mainstage, мелодические края, контролируемая агрессия, читаемые drops) vs
  «Warehouse Hard Techno» (schranz-lean, дисторсия, 4 AM rooms).

### Hard groove и hard bounce

- **Hard groove:** ревайвл 90-х (Ben Sims-школа) — 135–140 BPM, синкопированные
  фанковые грувы, tribal-перкуссия, bouncy bassline; FJAAK — ~137 BPM
  (SPANDAU20). Живёт как грувовая альтернатива между driving и hard techno.
  ([4D4M](https://4d4m.com/the-ultimate-guide-to-hard-techno-subgenres-whats-hot-in-2024/),
  [RYM: Hardgroove Techno](https://rateyourmusic.com/genre/hardgroove-techno/))
- **Hard bounce (новый стиль 2025):** stomping 4/4 kick ~145–155 BPM,
  **off-beat bass**, редкие vocal stabs, swung sub-bass; «яркий, хаотичный»
  контраст тёмному industrial hard techno.
  ([Nerve](https://www.nervemelb.com/nerve-news/blog-post-title-one-9xa55),
  [Feral](https://www.feralclo.com/blogs/news/the-rise-of-hard-bounce-how-it-changed-europes-hard-techno-scene))
- Как отдельные Beatport-категории hard groove/bounce **не подтверждены**
  (bounce живёт только тегом).

### Trance-инъекция и новый Beatport-саб-жанр

- 2025 — массовый trance-revival; acid/hard-trance/eurodance реинтерпретации
  — определяющая черта года; Sara Landry миксует hard techno основу (140–160,
  rumble, sidechain) с trance-хуками и chant-вокалами.
  ([Trancehistory 2025](https://trancehistory.com/2025/12/30/trance-music-in-2025-and-first-look-at-2026/),
  [Billboard: Sara Landry](https://www.billboard.com/music/music-news/sara-landry-hard-techno-spiritual-driveby-1235810498/))
- **Psy-Techno** запущен Beatport **27.01.2026** внутри Techno (Peak Time /
  Driving): гипнотический пульс techno + психоделический sound design
  psy-trance; ранние итерации 128–138 BPM.
  ([Beatportal](https://www.beatportal.com/articles/1257068-beatport-launches-new-sub-genre-psy-techno))

> Ни один из этих ярлыков (schranz / hard_groove / hard_bounce / psy_techno) не
> является значением enum `TechnoSubgenre` (15 фиксированных moods). В плагине
> это **сценические оверлеи поверх существующих moods** — мапить по фичам:
> schranz→hard_techno-режим; hard groove→driving/tribal @135–140; hard
> bounce→peak_time/hard_techno с off-beat bass; psy-techno→hypnotic/peak_time
> с psy sound design. `filter mood=schranz` — hard error (`extra="forbid"`).

---

## 2. Крафт-детали построения сета

### Фразировка (32 бита / 8 баров)

- Танцевальная музыка структурирована фразами по 32 бита (8 баров); новый
  элемент — на границе фразы; для major-событий (drop, breakdown) выравнивать
  за 16–32 бара заранее.
  ([DJ.Studio: Phrasing](https://dj.studio/blog/phrasing-dj-mixing))
- rekordbox Phrase Analysis размечает **Intro / Up / Down / Chorus / Bridge /
  Verse / Outro**, набор меток зависит от определённого «Mood» трека (HIGH:
  Intro/Up/Chorus/Down/Outro — типично для techno).
  ([Disc DJ Store](https://www.thediscdjstore.com/blog/phrase-analysis.html),
  [rekordbox Phrase Edit PDF](https://cdn.rekordbox.com/files/20200312172204/rekordbox5.1.0_Phrase_Edit_operation_guide_EN.pdf))
- **Плагин-мэппинг:** rekordbox-словарь мапится на наши `track_sections` типы
  (intro/build/drop/peak/breakdown/outro). Downbeat/beatgrid у нас почти пуст —
  фразировку помечать как approximate, не обещать точный bar-count.

### Cue-точки: pro-workflow

- Основная работа — до выступления: crates по mood/energy, beatgrid, key-теги.
  Именованные/цветные hot cues на: (a) drop/peak entry — «аварийный» триггер,
  (b) последний стабильный phrase перед vocal clash / уходом драм-секции —
  safe mix-out, (c) mix-in на начале фразы.
  ([VibesDJ: Cue Point Management](https://vibesdj.io/learn/techniques/cue-point-management),
  [DJ.Studio: Set Preparation](https://dj.studio/blog/dj-set-preparation))

### Key-shift «energy boost» (подтверждено)

- +1 полутон = Camelot **+7** (2A→9A); +2 полутона = Camelot **+2** (5A→7A).
  Двухполутоновый прыжок (**+2**) надёжнее однополутонового (**+7**). Техника
  для коротких транзишенов, не длинных блендов; **1–2 раза за сет максимум**.
  Мосты перед boosted-треком: filter sweep / echo freeze / noise riser.
  ([DJ TechTools: Advanced Key Mixing](https://djtechtools.com/2013/12/20/advanced-key-mixing-techniques-for-djs/),
  [Mixed In Key: Advanced Harmonic](https://mixedinkey.com/book/use-advanced-harmonic-mixing-techniques/))
- Из того же канона: relative major/minor = тот же номер, смена буквы (7A↔7B);
  короткий 1-count loop на совместимой ноте = мост между треками с общими
  нотами, но конфликтующими прогрессиями.

### Loop-транзишены и acapella-bridge

- Loop 1/2/4/8 баров; ключевой mix-out — залупить **stripped-back секцию
  (4 бита баса/перкуссии)** и выходить из неё; ошибки — loop без quantize
  (сползает с грида) и не отпущенный вовремя loop, ломающий фразировку входа.
  CDJ не поддерживают active loops → готовить заранее.
  ([We Are Crossfader](https://wearecrossfader.co.uk/blog/dj-looping-guide/),
  [Digital DJ Tips: Loops](https://www.digitaldjtips.com/three-ways-to-use-loops-without-annoying-everyone/))
- Acapella-bridge: акапелла поверх играющего → увести старый → подложить новый
  под голую акапеллу → убрать акапеллу. Требует совместимый key + BPM.
  ([Digital DJ Tips: Acapellas](https://www.digitaldjtips.com/how-to-dj-with-acapellas/))
- «Doubles» (две копии одного трека) — свежего надёжного источника нет
  (не подтверждено).

### 3-deck отбор

- Для лееринга на 3+ деках нужны треки «постоянно меняющиеся и хорошо звучащие
  при наложении» — sparse/tool-образный материал, а не плотные full-range.
  ([Attack Magazine: Jeff Mills 'The Bells'](https://www.attackmagazine.com/technique/deconstructed/jeff-mills-the-bells/))

---

## 3. Warm-up / closing / after-hours / B2B

- **Warm-up (квантификация):** не превышать BPM хедлайнера; ~90–95% громкости
  системы; довести зал до **6–7/10** и оставить там; не играть треки
  хедлайнера и других артистов лайнапа. Нарушение = blacklist.
  ([DJ Playbook](https://djplaybook.com/craft/dj-etiquette/),
  [Digital DJ Tips: Warm Up](https://www.digitaldjtips.com/how-to-dj-warm-up-sets/))
- **Closing = warm-up наоборот:** стартовать высоко (близко к финалу
  хедлайнера) и **медленно** спускать по мере редения зала — не обрыв.
  ([DJ Times](https://www.djtimes.com/2020/05/dj-etiquette-advice-for-openers-and-closers-from-a-club-owner/))
- **B2B pre-flight (5 минут):** кто открывает/закрывает, BPM-коридор, какие
  направления «off the table».
  ([Ticket Fairy](https://www.ticketfairy.com/blog/back-to-back-festival-dj-etiquette-agreements-that-save-the-set),
  [Pioneer DJ](https://blog.pioneerdj.com/djtips/how-to-dj-back-to-back/))
- **B2B ротация сужается:** старт длинными очередями (15 мин / 4–5 треков),
  через час — по 2, финал — one-for-one. Следующий трек = **ответ** на трек
  партнёра; «дать треку дышать», не обрубать ради своего.
  ([The DJ Mixtape](https://thedjmixtape.com/b2b-djing/),
  [Mixmag](https://mixmag.net/feature/b2b-back-to-back-dj-set-artist-wisdom-sharing-decks))

---

## 4. Именные техники (citable)

- **Jeff Mills** — 3-deck mixing с начала 90-х; DVD **Exhibitionist (2004)** —
  канон (3 вертушки + CD, layering, narrative-driven). «The Bells» устроен в
  2 движения (мелодия → бас) — спроектирован под наложение.
  ([RA Films](https://ra.co/films/3451), [Attack Magazine](https://www.attackmagazine.com/technique/deconstructed/jeff-mills-the-bells/))
- **Richie Hawtin** — **Decks, EFX & 909 (1999)**: 3 вертушки + FX + TR-909,
  местами 4 пластинки; переработка треков в «новую массу», не juxtaposition.
  ([Wikipedia](https://en.wikipedia.org/wiki/Decks,_EFX_%26_909), [RA Rewind](https://ra.co/features/4422))
- **Klock / Dettmann** — вытянутые бесшовные бленды с «неожиданным щелчком
  фильтра/изолятора/фейдера»; Klock максимально hands-off; марафон 8+ часов
  Berghain как long-form narrative. Dettmann тянет в EBM/new wave, Klock
  ярче/хаузовее.
  ([RA review](https://ra.co/reviews/19850), [XLR8R: Klock](https://xlr8r.com/features/20-questions-ben-klock-talks-berlin-marathon-dj-sets-and-his-desire-to-ride-horses-and-become-a-zen-monk/))
- **Amelie Lens** — CDJ + **Pioneer RMX-1000** как постоянный слой: встроенный
  сэмплер и FX «полностью переформатируют играющий трек».
  ([Equipboard](https://equipboard.com/pros/amelie-lens))
- **Héctor Oaks** — vinyl-only, очень быстрые смены, селекция по «vibe и style,
  не жанру»: wave/EBM/proto-techno вперемешку с rave-классикой.
  ([RA bio](https://ra.co/dj/hectoroaks/biography))
- **Sara Landry** — hard techno 140–160 с trance-chant/spoken word поверх
  («ритуальная» подача); центральная фигура волны 2024–2026.
  ([Billboard](https://www.billboard.com/music/music-news/sara-landry-hard-techno-spiritual-driveby-1235810498/))
- **Trym** — режет «seamlessly between hard dance and hard trance» — hard
  trance как штатный компонент hard techno сета.
  ([Hardcultr](https://www.hardcultr.com/news/10-hard-techno-hard-trance-artists-set-to-dominate/))
- Конкретики по Kobosil/Dax J/I Hate Models set-механике сверх «peak-time
  schranz tools» — не нашлось (не подтверждено).

---

## 5. Data-driven DJing / research 2023–2026

- **Mixed In Key:** Energy Level 1–10 на трек; workflow — сортировка по Energy
  и кросс-референс Energy×Key для планирования warm-up/peak; MIK 11 ставит до
  8 авто-cue на transition points (Intros/Outros/Breakdowns/Drops/Bridges).
  ([MIK: Energy Level](https://mixedinkey.com/harmonic-mixing-guide/sorting-playlists-by-energy-level/))
  → Прямой аналог наших `energy_mean` + `track_sections`.
- **Engine DJ 4.2 (ноя 2024):** первым принёс **stem separation на standalone**
  (vocals/melody/bass/drums без компьютера).
  ([DJ.Studio: Stem Separation](https://dj.studio/blog/evidence-based-guide-dj-stem-separation))
- **djay Pro 5 (Algoriddim):** Neural Mix обновлён (AudioShake); Crossfader
  Fusion — пофейдерный своп отдельных стемов; 2–4-stem конфигурации; native с
  CDJ-3000X.
  ([Algoriddim press](https://www.algoriddim.com/press_releases/447-algoriddim-unveils-djay-pro-5-with-next-generation-neural-mix-crossfader-fusion-and-fluid-beatgrid-))
- **ISMIR 2024 — Mosaikbox** (Sowula & Knees, TU Wien): fully-automatic DJ
  mixing через **rule-based stem modification + precise beat-grid estimation**
  — академическое подтверждение stem-first подхода.
  ([PDF](https://repositum.tuwien.at/bitstream/20.500.12708/212628/1/Sowula-2024-Mosaikbox%20Improving%20Fully%20Automatic%20DJ%20Mixing%20Through%20Rule-ba...-vor.pdf))
- **ISMIR 2023 — DJ StructFreak** (Kim & Nam): automatic DJ на music structure
  embeddings (структурная совместимость секций, не только фичи пары).
  ([ISMIR 2023 LBD](https://ismir2023program.ismir.net/lbd_328.html))
- **Cue Point Estimation using Object Detection** (arXiv 2407.06823, 2024):
  cue-точки по спектрограмме computer-vision — путь к заполнению пустой
  `dj_cue_points`.
  ([arXiv](https://arxiv.org/pdf/2407.06823))
- **TIME 2025** — обзор темпоральной стороны DJ-mix generation.
  ([LIPIcs PDF](https://drops.dagstuhl.de/storage/00lipics/lipics-vol355-time2025/LIPIcs.TIME.2025.20/LIPIcs.TIME.2025.20.pdf))

**Вывод для движка:** наш stem-aware 6-компонентный scorer + Neural-Mix
recipe engine — на правильной стороне тренда (stem-first, structure-aware).
Известные пробелы (пустые `dj_cue_points`/`dj_saved_loops`, почти пустой
beatgrid, вокал = спектральные прокси) — теперь имеют конкретные research-пути
закрытия (object-detection cue estimation, structure embeddings).

---

## 6. FastMCP 3.3–3.4.x — upgrade-watch

Актуальная версия — **3.4.2 «Heads Up» (2026-06-06)**. Проект запинен
`fastmcp[tasks,apps]>=3.2.4,<3.4` → всё ниже помечено **UPGRADE-WATCH**:
это не про текущий рантайм, а про то, что учесть при поднятии пина.
([releases](https://github.com/jlowin/fastmcp/releases),
[changelog](https://gofastmcp.com/changelog.md))

| Версия | Ключевое |
|---|---|
| 3.3.0 «Slim Reaper» (05-15) | `fastmcp-slim` (client-only), `run_in_thread=False` opt-out, OAuth hardening |
| 3.4.0 «Remote Control» (06-02) | `fastmcp-remote` (bridge stdio↔HTTP + auto-OAuth), `ToolResult(is_error=True)`, safer CodeMode, proxy «fails loudly» |
| 3.4.1/3.4.2 (06-05/06) | Security: Starlette ≥1.0.1 (CVE-2026-48710), JWT/JWS header compat |

**Дельты, релевантные этому серверу:**

1. **Breaking в 3.2.4:** background tasks скоупятся к **authorization context**,
   не к сессии. Учесть при апгрейде (текущий пин уже включает 3.2.4).
2. **`prefab-ui` пинить точной версией** — доки прямо требуют pin (частые
   breaking changes); текущий транзитивный `>=0.19` этому противоречит.
   ([apps/prefab](https://gofastmcp.com/apps/prefab.md))
3. **`@tool(app=True)`** — канонический способ пометить UI tool; наш
   `meta={"ui": True}` эквивалент, проверить на апгрейде что распознаётся.
4. **`ToolResult(is_error=True)` (3.4.0)** — «мягкие» ошибки как результат,
   которые LLM видит; дополняет типизированные `ToolError`/`DomainErrorMiddleware`.
5. **`ToolError`/`ResourceError`/`PromptError` пробивают `mask_error_details=True`**
   — пользовательские сообщения ошибок только через эти типы; остальное
   маскируется в prod.
6. **Per-session visibility API:** `ctx.enable_components(tags=...)` /
   `disable_components` / `reset_visibility` — изолировано per-session, FastMCP
   сам шлёт `list_changed` этой сессии. Наша оговорка про Claude Code,
   игнорирующий notification, **остаётся в силе** — не полагаться на unlock
   mid-session; `tool_invoke` — escape hatch.
   ([servers/visibility](https://gofastmcp.com/servers/visibility.md))
7. **Component versioning:** `version=` + `VersionFilter`; правило —
   версионировать все реализации компонента или ни одной (смесь = registration
   error). Для эволюции tool-контрактов без слома старых клиентов.
   ([servers/versioning](https://gofastmcp.com/servers/versioning.md))
8. **Tool fingerprinting (3.0):** `sha256(tool.key + to_mcp_tool())` manifest
   как CI/pre-push артефакт — anti-drift для tool-контрактов (дополняет наши
   content-correctness тесты промтов).
   ([tool-fingerprinting](https://gofastmcp.com/servers/tool-fingerprinting.md))
9. **Долгие операции (>120s, напр. batch MP3 download) → кандидат на
   `task=True`** (SEP-1686, spec 2025-11-25): клиент сразу получает task ID и
   поллит прогресс вместо отката UoW по таймауту. Требует `fastmcp[tasks]` +
   клиентской поддержки; поддержка в Claude Code **не подтверждена** — проверять
   до внедрения. Пока канон — батчить download под таймаут (см.
   `.claude/rules/audio.md` «L5-финализация»).
   ([servers/tasks](https://gofastmcp.com/servers/tasks.md))
10. **`@tool(timeout=N)`** — штатная защита от зависших операций; не сочетать с
    `run_in_thread=False`.
11. **Тесты:** доки рекомендуют ассертить **`result.data`** (гидратированный
    typed объект) + inline-snapshot; наш канон `result.structured_content`
    валиден, `result.data` даёт типизированную проверку без ручного парсинга.
    ([servers/testing](https://gofastmcp.com/servers/testing.md))
12. **OTEL-конвенции:** `mcp.method.name` / `gen_ai.tool.name` /
    `fastmcp.provider.type`; `rpc.system`/`rpc.service` удалены — не
    ассертить/не алертить по ним; SDK-setup строго до `import fastmcp`;
    тесты — `InMemorySpanExporter`.
    ([servers/telemetry](https://gofastmcp.com/servers/telemetry.md))
13. **BM25 vs regex search backend:** BM25 корректен для natural-language
    (наш случай), `max_results` default 5; search-прокси нужен только клиентам
    на `list_tools()` — прямой вызов его обходит (наш `ALWAYS_VISIBLE_TOOLS` ↔
    официальный `always_visible`).
    ([transforms/tool-search](https://gofastmcp.com/servers/transforms/tool-search.md))
14. **`fastmcp-remote` (3.4.0)** — официальный bridge stdio→HTTP с auto-OAuth:
    потенциальный канон дать облачной песочнице claude.ai/code доступ к HTTP
    MCP вместо teleport-only (проходимость через egress-прокси песочницы **не
    подтверждена**).
15. **Elicitation (spec 2025-11-25):** multi-select, titled options, enum — если
    добавлять интерактивный conflict gate (напр. `playlist_sync`),
    `ctx.elicit()` с `accept/decline/cancel`, только с фолбэком (клиенты без
    поддержки кидают error).
16. **FileSystemProvider:** `_`-префиксные функции не регистрируются даже с
    декоратором (наши `_body()` helpers безопасны); битый файл не валит startup,
    лишь warning → smoke-тест на количество зарегистрированных компонентов
    (`EXPECTED_PROMPTS`) остаётся обязательным гейтом; `reload=True` только dev.

---

## 7. Дельты, внесённые в исполняемые правила

`.claude/rules/dj-set-building.md`:
- §2 — BPM-полосы по поджанрам расширены вверх (hard 145–168, industrial 170+);
  добавлен блок «сценические оверлеи» (schranz/hard groove/hard bounce/psy) с
  явным запретом `filter mood=<label>`.
- §3 — таблица сценариев: +Festival hard techno, +Warehouse hard techno /
  schranz; warm-up/closing/B2B квантифицированы.
- §4 — key-shift energy boost (+7/+2, 1–2× за сет), loop mix-out, фразовая
  арифметика 32/8; расширен honesty-блок про trance-инъекцию.
- §4a — новый cue-контракт из 3 точек для cheatsheet.
- §6 — persona-таблица: +landry, +oaks, +trym; уточнены lens (RMX-1000-слой),
  mills (Exhibitionist 3-deck), hawtin (3-deck sparse отбор).
- §7 — FastMCP upgrade-watch pointer на этот док.

## 8. Источники — сводка

Techno: Hardcultr, weraveyou/IMS, Beatportal (Psy-Techno), 4D4M, RYM,
Trancehistory, Billboard, Nerve, Feral, DJ.Studio, Disc DJ Store, rekordbox,
VibesDJ, DJ TechTools, Mixed In Key, We Are Crossfader, Digital DJ Tips,
Attack Magazine, RA (Films/reviews/bios), XLR8R, Equipboard, DJ Playbook,
DJ Times, Ticket Fairy, Pioneer DJ, The DJ Mixtape, Mixmag, Algoriddim,
Mosaikbox (ISMIR 2024), DJ StructFreak (ISMIR 2023), arXiv 2407.06823,
TIME 2025. FastMCP: gofastmcp.com (llms.txt, changelog, updates, servers/*,
transforms/*, apps/*, cli/*), github.com/jlowin/fastmcp/releases. Полные URL
— в bullet'ах выше. Проверено 2026-07-05.

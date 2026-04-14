# Techno Transitions — Deep Research

> Дата: 2026-04-08
> Контекст: подготовка редизайна `app/domain/transition/scorer.py` для dj-music-plugin
> Источники: ISMIR / JASMP / Springer papers + индустриальные DJ-руководства + реверс-инжиниринг SOTA-систем
> Цель документа: обоснованная база для редизайн-спеки и калибровки scoring

---

## TL;DR (для тех, кто не хочет читать 600 строк)

1. **Phrasing > harmonic > timbral > tempo > energy > key.** Это противоречит весам, которые сейчас в `DEFAULT_TRANSITION_WEIGHTS` (там harmonic 0.20, timbral 0.10, energy 0.23). Самая большая ошибка нашей текущей формулы — phrasing/structure не моделируется вообще, а энергия переоценена.
2. **Camelot wheel переоценён.** Kim et al. (ISMIR 2020) показали, что в реальных DJ-сетах harmonic compatibility статистически слабо подтверждается. Bibbó & Faraldo (ISMIR 2022 LBD) показали, что continuous HPCP-correlation бьёт дискретный Camelot. Hard-reject на Camelot ≥ 5 — слишком грубо для percussion-heavy тёмного техно, где key вообще ambiguous.
3. **MFCC similarity — реально #1 фактор подбора смежных треков** в живых mixes (Kim 2020). Наш `score_spectral` это уже знает (вес MFCC внутри спектрала 0.30), но общий вес самого спектрала 0.15 — занижен.
4. **DJ держат loudness step очень узко** (Kim 2020 — медиана < 1 dB). Наш hard-reject 6 LUFS правильный, но мы недо-вознаграждаем близкие пары: sigmoid с σ=3 LUFS — слишком пологая.
5. **Optimal mix-points всегда на 16-bar phrase boundaries** внутри intro/outro mixable region (Vande Veire 2018, Zehren 2022 — F1 cue detection > 95% попадают на 16-bar границы). У нас в БД есть `Beatgrid`, `track_sections`, `mix_in_point_ms`, `from_section_id` — но в scoring это не используется. Это **самая дешёвая большая победа**.
6. **6-компонентная weighted-sum формула — мейнстрим в литературе** (AutoMashUpper 2013, MusicMixer 2015, D&B AutoDJ 2018), наша архитектура корректна. Но магические числа, hardcoded thresholds в `recommend_style` и отсутствие phrasing/section-awareness снижают качество.
7. **GAN/end-to-end ML transition models — провалились** (Chen 2022, mode collapse). SOTA на 2024 — гибрид rule-based scorer + structural detection. Это валидирует наш подход в принципе.

---

## 1. Что такое transition в техно — теория

### 1.1 Phrasing — фундамент

Электронная танцевальная музыка пишется в 4/4. Аранжировка естественно группируется в **8, 16, 32 бита** (2, 4, 8 баров). 32-битовая фраза («rule of 32») — крупная фраза, на границе которой обычно происходят аранжировочные события: новый слой перкуссии, drop, breakdown. Все DJ-руководства сходятся: правильное сведение начинается **на старте новой 32-битовой фразы** (DJ TechTools, DJ.Studio, Good Time DJ, Pioneer DJ blog).

**Структура типичного techno-трека (в барах):**

```text
intro 16-32 (drum-only) → build 16-32 → main/drop 32-64 →
breakdown 16-32 → second drop 32-64 → outro 16-32 (drum-only)
```

Источник: Universe of Tracks, Pioneer DJ blog. Treki специально пишутся с **drum-led DJ-friendly intros/outros** именно для того, чтобы первые/последние 32-64 бара были percussion-only — это и есть **mixable region**, где гармонические клэши минимальны и DJ может долго блендить.

### 1.2 Bass swap — техническое ядро techno-блендинга

Жёсткое правило: **никогда не должно звучать два кика одновременно**. Phase cancellation, low-end mush, срыв кика. Стандартная процедура (EQ swap / bass swap):

1. На входящем — полный low-kill (≈−26 dB или off) до подъёма фейдера.
2. На границе фразы (8 или 16 баров после старта) — swap low: входящему вернуть, исходящему снять.
3. Опционально позже снять mid у исходящего, оставив только hi-hat «хвост».

Источники: DJ.Studio EQ Mixing, Mind Flux, TechnoMusicNews, Skilz DJ Academy.

**Следствие для нашего scorer'а:** низкочастотный конфликт нельзя чинить crossfade-длиной. Если оба трека имеют сильные kicks с конфликтующим тоном — нужен либо filter-sweep (HPF исходящего наверх), либо длинное окно с принудительным bass-kill. Это уже отражено в `recommend_style` веткой `score.spectral < 0.45 → FILTER_SWEEP`, но критерий "spectral collision" слишком общий.

### 1.3 Camelot wheel — правила и обязательное relaxation

Базовые «безопасные ходы» (Mixed In Key, Setflow, DJ.Studio):

| Ход | Смысл | Частота в проф. сетах |
|---|---|---|
| Same key | 100% | Безопасно, но монотонно |
| ±1 (adjacent) | Сдвиг одной ноты, почти незаметно | **Самый частый** |
| A↔B same number | Смена mood (minor↔major), same root | Инструмент shaping mood |
| +2 «Energy Boost» | Заметный сдвиг + boost | Sparingly, ~раз в 20-30 мин |
| −5 «Skrillex variation» | Mood reset + boost | Эпизодически |

**Critical relaxation rule.** Pioneer DJ blog: «for techno harmonic compatibility менее критична, потому что много треков имеют слабовыраженную тональность (kicks + atonal pads)». DJ.Studio: «harmonic clash в техно часто маскируется самим kick-low-end». Mixed In Key и Setflow тоже признают: для drum-only intro/outro key matching можно ослабить или **игнорировать вообще**.

**Следствие для scorer'а:** мы уже релаксируем на двойную atonality (`base = max(0.8, base)`), но не учитываем что **mix происходит на percussion-only участках**. Если оба окна mix-in/mix-out — drum-only intro/outro, harmonic вес должен схлопнуться до ~0. Это явная section-awareness.

### 1.4 Energy management

Mixed In Key, Setflow, Theghostproduction, DJ City — все формулируют «золотое правило»: за один переход энергия не должна падать больше чем на 1 шаг (по 1-10 шкале MIK). Curve строится через **rises and releases**, не sustained peak. После peak'а обязателен release.

**5-фазовая структура сета** (DJ.Studio Anatomy of a Great DJ Mix): Warm Up → Build → Peak → Release → Finale.

**Следствие:** наш `TransitionIntent` уже моделирует это (RAMP_UP / MAINTAIN / COOL_DOWN / CONTRAST), но `infer_intent` слишком наивен — только `set_position` 0.2/0.85 и `energy_delta_lufs` ±2.0. Он не знает о шаблоне сета (warm_up_30 vs peak_hour_60), не знает текущую фазу (build vs peak vs release).

### 1.5 Виды переходов (canonical taxonomy)

| Тип | Длина | Когда |
|---|---|---|
| **Long blend / EQ blend** | 32-64 bars | Default для техно: всё совместимо, времени достаточно |
| **Quick cut / drop swap** | 4-8 bars или мгновенно на drop | Hip-hop, peak-hour techno, surprise mood change |
| **Bassline swap** | 16-32 bars | Стандарт house/techno, kicks one at a time |
| **Filter sweep** | 16-32 bars | Low-end несовместим, или для wash-эффекта |
| **Echo-out / delay throw** | 8-16 bars | «Rescue» при плохом BPM/key match |
| **Loop roll** | 1-4 bars | Выровнять phrase mismatch |

Наш `TransitionStyle` enum уже покрывает 5 из 6 (нет loop roll). `TRANSITION_STYLE_PROFILES` даёт bars: CUT 0, BASS_SWAP_SHORT 8, BASS_SWAP_LONG 32, LONG_BLEND 64, ECHO_OUT 16, FILTER_SWEEP 16. Числа **корректны** относительно практики.

---

## 2. Обзор SOTA автоматических систем

| Система | Подход | Ключевая идея |
|---|---|---|
| **hpDJ (Cliff, 2000-05)** | Beat-aligned crossfade на phrase points | Самая ранняя формализация |
| **Ishizaki (ISMIR 2009)** | BPM discomfort function, global tempo schedule | Discomfort нелинеен, оптимизация всего сета |
| **AutoMashUpper (Davies, ISMIR 2013)** | Mashability = harmonic + rhythmic + spectral balance | Прообраз 6-компонентных формул |
| **MusicMixer (Hirai, ACE 2015)** | Latent topic similarity (LDA на chroma+timbre) | Тембр-aware ranking лучше чистого BPM/key |
| **D&B Auto-DJ (Vande Veire, JASMP 2018)** | Downbeat tracking + 16-bar grid + structural sections + drop detection | **Structural alignment важнее тональности для percussion-driven жанров** |
| **Cue Detection (Zehren, CMJ 2022)** | Onset envelope + 16-bar agglomerative grid + per-block features + cue/no-cue classifier | F1 cue detection > 95% попадают на 16-bar границы — **квантование к downbeats почти бесплатно** |
| **Mixed In Key Studio Edition** | 8 hot-cue points через onset/energy peaks + low-end + spectral flux | Проприетарный, но логика на структурных событиях |
| **DJ.Studio Harmonize/Automix** | Минимизация суммы Camelot-расстояний + BPM smoothness + auto intro/outro selection | Classical optimization, не ML |
| **Neural Mix (Algoriddim djay Pro)** | Real-time stem separation → bass swap без EQ knob | Stem-aware crossfading |
| **Mixxx AutoDJ + PRs** | Default: 10s fixed crossfade. PR #13563 предлагает `factor1 * abs(bpm_diff) + factor2 * abs(key_diff)` — наивная формула | Open-source, можно подсматривать |
| **GAN Transitions (Chen, ICASSP 2022)** | End-to-end differentiable DSP | **Mode collapse, хуже rule-based** |

**Главный вывод:** SOTA на 2024 — **гибрид rule-based scoring + structural/phrasing detection**, не end-to-end ML. Это валидирует нашу архитектуру.

**Что у нас уже есть, а у конкурентов нет:**
- 6 компонентов с ясной семантикой (vs Mixxx 2 компонента)
- Hard reject с reasoning (vs DJ.Studio mute reject)
- TransitionIntent context-awareness (vs MusicMixer без позиционного контекста)
- Per-track 47 features в БД (vs RaveDJ "we use ML" без деталей)

**Чего нет:**
- Phrasing/section awareness (есть у Vande Veire, Zehren, MIK Studio)
- Mix-point detection (есть у MIK, Lexicon, rekordbox auto-cue, Vande Veire)
- Stem-aware bass-swap (есть у Algoriddim, VirtualDJ)
- Continuous harmonic distance (есть у Bernardes TIS, Bibbó HPCP)

---

## 3. Структурная сегментация и mix-point detection — state of the art

### 3.1 Foote novelty (2000) — основа, но плохо на techno

Self-similarity matrix (SSM) на любых features → checkerboard kernel вдоль диагонали → novelty curve, пики которой = boundaries. Реализовано в `librosa.segment.recurrence_matrix`. **Слабость на техно:** SSM на mono-timbre трек даёт диффузный отклик, peaks плохо локализованы. Nieto & Bello (ISMIR 2016): F1 < 0.55 для Foote на electronic music.

### 3.2 MSAF (Nieto & Bello) — лучше для электронной музыки

Python framework с 6 алгоритмами. Для электронной музыки **2D-FMC** (Fourier Magnitude Coefficients) и **SF** (structural features Serrà) дают лучший F1 чем Foote. F1 на SALAMI редко > 0.65 даже у best system.

### 3.3 Vande Veire / Zehren — практический подход для EDM

Не используют общие сегментаторы. Берут:
1. Downbeat tracking (madmom RNN)
2. Детерминистическая 16-bar сетка от первого downbeat
3. Per-block features: RMS, low-band energy, spectral flatness
4. Бинарный классификатор «cue / no-cue»

**Ключевой инсайт Zehren 2022:** cue points в EDM с >95% попадают на 16-bar boundaries → **квантование к downbeat grid почти бесплатно улучшает точность**. Это значит: мы можем не строить «правильный» сегментатор для техно, а просто:
- Получить downbeats из beat analyzer
- Квантовать каждую `track_sections` границу к ближайшему downbeat
- Mix-out point = первый downbeat в начале последнего OUTRO/SUSTAIN/RISE сегмента, выровненный к 16-bar grid
- Mix-in point = первый downbeat первого INTRO/AMBIENT сегмента, выровненный к 16-bar grid

### 3.4 «Mixable region»

Устоявшегося термина нет, но Vande Veire и Zehren определяют одинаково:
- **Mix-out region** = последние 16-32 бара перед outro, где energy уже снизилась + удалены leading мелодии + остался grooving rhythm
- **Mix-in region** = первые 16-32 бара симметрично

Detection обычно на **energy envelope в low band + spectral flatness**.

---

## 4. Маппинг ресёрча → наш стек

### 4.1 Какие из 47 features что моделируют

| Feature group | В нашей БД | Используется в scoring | Литература говорит | Действие |
|---|---|---|---|---|
| BPM (bpm, confidence, stability, variable_tempo) | ✅ | ✅ | Critical (Ishizaki, Kim) | OK, оставить |
| Key (key_code, confidence, atonality, chroma_entropy, hnr, tonnetz) | ✅ | ✅ | Переоценён в индустрии (Kim, Bibbó) | Снизить вес, добавить section-aware relaxation |
| Loudness (integrated_lufs, LRA, crest, short_term, momentary, true_peak) | ✅ | Частично (только integrated_lufs + LRA + crest) | Critical, узкое выравнивание (Kim) | Узче sigmoid, добавить short_term для динамической оценки на mix-points |
| MFCC (13 coeffs) | ✅ | ✅ (внутри spectral, вес 0.30) | **#1 фактор реальных mixes** (Kim) | Поднять общий вес spectral, или вынести MFCC отдельным компонентом |
| Spectral (centroid, rolloff85/95, flatness, flux, slope, contrast) | ✅ | ✅ | Critical (AutoMashUpper, Hirai) | OK |
| Rhythm (onset_rate, kick_prominence, hp_ratio, pulse_clarity, beat_loudness, tempogram) | ✅ | ✅ | Critical для percussion-driven жанров (Vande Veire) | OK |
| Tonnetz vector | ✅ | ✅ (cosine 0.30 в harmonic) | Continuous harmonic > Camelot (Bernardes, Bibbó) | Поднять вес, возможно сделать основным harmonic метриком |
| Structure sections (track_sections таблица) | ✅ | ❌ | **Critical для phrasing-aware mixing** (Vande Veire, Zehren, MIK) | **Внедрить section-aware scoring** |
| Beatgrid (downbeats) | ✅ (Beatgrid model) | ❌ | **Critical для mix-point quantization** (Zehren) | **Внедрить downbeat-aware mix points** |
| Cue points (CuePoint model) | ✅ | ❌ | Used by MIK/Lexicon/rekordbox | Опционально: уважать manually-set cues |
| Phrase boundaries | ❌ (нет в БД) | ❌ | Производное от downbeats | Вычислять на лету: каждый 16-й downbeat = phrase boundary |
| P1/P2 (danceability, dissonance, dynamic_complexity, spectral_complexity, pitch_salience, spectral_contrast, bpm_histogram, phrase_boundaries_ms) | ✅ | Частично | — | Используется в timbral/spectral, оставить |

### 4.2 Чего не хватает

1. **Phrasing/section model в scoring.** Поля `mix_in_point_ms`, `mix_out_point_ms`, `from_section_id`, `to_section_id` есть в БД, но nullable и **не используются**. Это самая большая дыра.
2. **Mix-point detection service.** Нет процесса, который ставит `mix_in/out_point_ms` на основе beatgrid + sections.
3. **Continuous harmonic distance.** Используем discrete Camelot lookup `{0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}`. Tonnetz cosine добавлен сверху как 30%, но базовый Camelot всё ещё доминирует.
4. **Phrase-aligned BPM tolerance.** Ishizaki 2009: discomfort нелинеен. У нас линейная Гаусс sigma=3 BPM, нет учёта double/half-time как «free pass» (хотя `bpm_distance()` это считает).
5. **Loudness short-term window for mix region.** Used `integrated_lufs` (whole track), но при сведении важна громкость **именно последних 32 баров outgoing и первых 32 баров incoming**, а не средняя по треку.

### 4.3 Что лишнее или можно упростить

1. **Hardcoded thresholds в `recommend_style`** (0.45/0.40/0.55/0.95/0.85/0.75) — должны быть в `settings.style_*` или в отдельной dataclass StyleRules.
2. **Magic numbers в scoring**: BPM σ=3.0, HNR normalize -30..0, tonnetz blend 0.30/0.70, dissonance threshold 0.4, spectral_complexity threshold 10, timbral норм 15dB/0.5/3.0/10. Все эти константы должны быть в `app/domain/transition/weights.py` (новый файл) или `settings`.
3. **Spectral компонент сейчас 6 sub-сигналов** в одной функции 80 строк. Семантически это два разных явления: (a) тембральная похожесть (MFCC + centroid + rolloff + slope = «звучит похоже»), (b) spectral balance (energy_bands + flux = «энергия распределена так же»). Можно разнести.
4. **`infer_intent` примитивен.** Только set_position и energy_delta. Не знает шаблона сета, не знает текущей фазы.

### 4.4 Конкретные числовые рекомендации (готовые к подстановке)

| Параметр | Текущее | Литература | Рекомендация |
|---|---|---|---|
| BPM hard reject | 10 BPM | ±5 BPM (Ishizaki, Vande Veire) | Снизить до 8, держать double-time exception |
| BPM Gauss sigma | 3.0 | ±3% типично, ±6% предельно | Оставить 3 BPM (~2.5% на 124 BPM), параметризовать |
| Camelot hard reject | dist ≥ 5 | dist ≤ 1 в 80% реальных mixes (Kim), но для atonal раслабляется | Оставить 5, но релакс на atonal/intro→outro pair |
| Energy hard reject | 6 LUFS | Медиана < 1 dB (Kim), 6 LUFS — клэш | Оставить 6 как hard, но softer sigma 1.5 LUFS вместо 3.0 |
| `recommend_style` spectral cutoff | 0.45 | — | Параметризовать в settings, проверить на ground truth pairs |
| `recommend_style` energy cutoff | 0.40 | — | То же |
| `recommend_style` harmonic cutoff | 0.55 | — | То же |
| Phrase length (для mix-point quantization) | — (не используется) | 16 bars (Zehren) | Добавить как `settings.phrase_bars = 16` |
| Mix region length | — | 32-64 bars (Universe of Tracks, Pioneer DJ) | Добавить как `settings.mix_region_bars = 32` |
| Default crossfade длины (CUT/SHORT/LONG/BLEND/ECHO/SWEEP) | 0/8/32/64/16/16 bars | Корректны (Final Scratch, Cursa, DJ.Studio) | Оставить |
| Default weights | bpm 0.22, harm 0.20, energy 0.23, spectral 0.15, groove 0.10, timbral 0.10 | MFCC #1, key переоценён, structure ключевой | Сдвинуть: bpm 0.20, harm 0.12, energy 0.18, spectral 0.20, groove 0.15, timbral 0.15. **Sum = 1.0**. Затем добавить 7-й компонент **structural 0.10** и нормализовать. |

---

## 5. 10 ключевых insights

1. **Tempo manipulation в реальных DJ-сетах минимальна** (Kim ISMIR 2020). BPM hard reject оправдан, но tolerance должен быть жёстким (~5% = ~6 BPM на 124 BPM треке).
2. **Loudness alignment между смежными треками очень узкий** — медиана < 1 dB. Наш hard-reject 6 LUFS правильный, но мы недо-ценим ультра-близкие пары.
3. **MFCC similarity статистически значима в реальных mixes** (Kim 2020) — тембр matters, и больше чем индустрия думала.
4. **Camelot слабо подтверждается статистически** (Kim 2020, Bibbó 2022). Continuous distance (TIS, HPCP correlation) лучше — у нас уже есть Tonnetz, можно сделать его primary метрикой.
5. **Structural alignment важнее тональности для percussion-driven жанров** (Vande Veire 2018). Это **наш case** — техно percussion-driven по определению.
6. **Cue points с >95% попадают на 16-bar boundaries** (Zehren 2022) — квантование mix-points к downbeats почти бесплатно улучшает качество.
7. **Foote novelty плохо работает на techno** (Nieto & Bello). Не пытаться построить «общий» сегментатор — использовать downbeats + section type + low-band energy.
8. **Discomfort от BPM нелинеен** (Ishizaki 2009) — оптимизация суммы по сету > проверка каждого pair против flat threshold. У нас GA уже это делает, но scorer выдаёт линейный score.
9. **GAN transition models провалились** (Chen 2022, mode collapse). Гибрид rule-based + structural detection остаётся SOTA.
10. **«Two kicks at once» — phase cancellation, low-end mush** (Mind Flux, TechnoMusicNews). Spectral collision на low band — критичен; наш `score_spectral` это знает только косвенно через energy_bands. Стоит добавить **explicit low-band conflict check**.

---

## 6. Главные источники

**Академические:**

- Cliff, *hpDJ: An Automated DJ with Floorshow Feedback*, HP Labs HPL-2005-88 (2005)
- Ishizaki et al., *Full-Automatic DJ Mixing System with Optimal Tempo Adjustment*, ISMIR 2009 — https://archives.ismir.net/ismir2009/paper/000043.pdf
- Davies et al., *AutoMashUpper*, ISMIR 2013 — https://archives.ismir.net/ismir2013/paper/000077.pdf
- Hirai et al., *MusicMixer*, ACE 2015 — DOI 10.1007/978-3-319-27671-7_59
- Bernardes et al., *A Hierarchical Harmonic Mixing Method*, CMMR 2017
- Vande Veire & De Bie, *From Raw Audio to a Seamless Mix: Drum and Bass Auto-DJ*, JASMP 2018 — https://link.springer.com/article/10.1186/s13636-018-0134-8
- Kim et al., *A Computational Analysis of Real-World DJ Mixes*, ISMIR 2020 — https://archives.ismir.net/ismir2020/paper/000352.pdf
- Zehren et al., *Automatic Detection of Cue Points*, CMJ 46(3) 2022 — DOI 10.1162/comj_a_00652
- Bibbó & Faraldo, *A New Compatibility Measure for Harmonic EDM Mixing*, ISMIR 2022 LBD
- Chen et al., *Automatic DJ Transitions with Differentiable Audio Effects and GANs*, ICASSP 2022 — arXiv:2110.06525
- Foote, *Automatic Audio Segmentation Using a Measure of Audio Novelty*, ICME 2000
- Nieto & Bello (MSAF), ISMIR 2016
- Krumhansl & Kessler, *Tracing the dynamic changes in perceived tonal organization*, Psychological Review 89 (1982)

**Практика и индустрия:**

- DJ.Studio — Anatomy of a Great DJ Mix, EQ Mixing, Camelot Wheel Guide, Harmonize/Automix
- Mixed In Key — Energy Boost Tutorial, Studio Edition FAQ, Control Energy Level
- DJ TechTools — Phrasing the Perfect Mix (Ean Golden), How to DJ 101 Phrasing
- Pioneer DJ blog — Mixing Techniques per Genre
- Universe of Tracks — Techno Track Structure
- Setflow — Camelot Wheel Guide, DJ Set Energy Flow
- Mind Flux, TechnoMusicNews — EQing Kick and Bass in Techno
- Algoriddim — Neural Mix Pro, djay Pro Crossfader FX
- Mixxx PR #13563 (Track Similarity Algorithm), PR #2746 (Beats as transition unit)

---

## 7. Что отсюда идёт в редизайн-спеку

Этот документ — **обоснование**, не план. Резюме того, что спека должна решить:

- Декомпозиция scorer.py 538 строк → пакет с одним файлом на компонент.
- Вынос магических чисел в `weights.py` / `settings`.
- Section-aware scoring: outro→intro pair получает relaxed harmonic, full-track pair — наоборот.
- Mix-point detection service на базе downbeats + section bounds, заполняет `mix_in_point_ms`/`mix_out_point_ms`.
- Continuous harmonic primary metric (Tonnetz cosine) с Camelot как fallback.
- Перебалансировка весов на основе таблицы из §4.4.
- Параметризация `recommend_style` thresholds.
- `infer_intent` v2: учёт SetTemplate и phase position.
- Контракт `recommend_style(score)` остаётся pure function на partial scores — это уже используется panel waveform player.
- Синхронизация `docs/transition-scoring.md` с реальностью.

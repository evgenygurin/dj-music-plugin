# Глубокое исследование: как составляет и играет сеты Chris Liebing — и как это воспроизвести программно для N дек

**Дата:** 2026-09-03  
**Статус:** research, не spec  
**Язык:** RU  
**Источники:** 180+ поисков, 3 exa agent runs (high effort), context7 FastMCP v3.2.4, GitHub prefecthq/fastmcp, текущие зависимости `pyproject.toml`, `app/audio`, `app/tools`  
**Ключевое уточнение пользователя:** инструмент не привязан к 2 или 6 декам — должен работать на **любом N** (2..N), дека = не трек, а роль/слой.

---

## 1. Chris Liebing — что важно понять музыкально

### 1.1 Единица работы — слой, а не трек

Liebing определяет цель как **soundscape / wall of sound**: слушатель не должен понимать, где кончился один трек и начался другой. Трек для него — набор извлекаемых слоёв: `kick/sub`, `groove`, `hats/perc`, `synth/loop`, `atmosphere`, `effect`. [Native Instruments 2022](https://blog.native-instruments.com/traktor-20-mena/), [The Night Bazaar 2018](https://thenightbazaar.co.uk/chris-liebing-i-realised-that-there-is-way-more-that-i-want-to-experience-musically/)

> Вывод для кода: **не секвенсор треков, а секвенсор слоёв**. Любой N — это N каналов слоёв, а не N полных треков. Шесть полных треков с двумя киками = грязь, а не Liebing.

### 1.2 Звук — не декор, а критерий отбора

Он сам мастерит CLR (`Create Learn Realize → Create Learn Repeat`), фильтрует релизы по спектральному месту кика/саба/транзиентов. [Dirty Epic 2024](https://dirty-epic.com/2024/09/03/dirty-epic-interview-with-chris-liebing/) Значит для софта: отбор по **качеству звука** (true_peak, lufs, spectral flux, kick prominence, hp_ratio) важнее, чем по названию жанра.

Отбор по функции (его 4 роли):
1. несущее тело (kick/bass+groove),
2. запоминающийся фрагмент (synth/noise/acid/vocal chop),
3. ритм-инструмент (чистая перкуссия для наложения),
4. разрежение/атмосфера перед новой фазой.

Трек может войти **не целиком**: Liebing любит середину или меняет kick. [The Night Bazaar](https://thenightbazaar.co.uk/chris-liebing-i-realised-that-there-is-way-more-that-i-want-to-experience-musically/)

### 1.3 Гармония — полезный контроль, не клетка

В его курсе есть harmonic mixing, но в техно важнее тембр/энергия/спектр. [Aulart](https://www.aulart.com/masterclass/chris-liebing-my-dj-techniques-vision-of-techno-en/), [DJ Mag](https://djmag.com/news/chris-liebing-explains-how-mix-harmonically-new-ni-video) → для кода: Camelot — один из весов, не единственный.

### 1.4 Драматургия — течение, а не дропы

Не жёсткий плейлист, а подготовленная палитра + реакция на зал. Пример: 5-часовой open-air 17:00→22:00 — плавная траектория свет→тьма. [GROOVE 2026](https://groove.de/2026/07/15/groove-podcast-510-chris-liebing/)

Макро-фазы в его духе:
1. Установить доверие к груву (простор, один фокус).
2. Наращивать число независимых событий (hat, мотив, фильтр, текстура) — не обязательно BPM.
3. Локальные волны: увести низ, укоротить луп, оставить верх, вернуть фундамент в новой конфигурации.
4. Менять качество энергии (acid/industrial/глубокая гипнотика/атмосфера), а не просто громче.
5. Держать возможность свернуть — импровизация > схема.

**Techno Zen** — монотонный ритм не отвлекает, а вводит в присутствие. [Mixmag](https://mixmag.net/feature/achieving-techno-zen-with-chris-liebing)

### 1.5 Техника: 2 деки — база, 4 деки + Maschine — реальность

- 2 деки (1995, Rodec MK-180): длинный smooth mix, чтобы окончание трека не было паузой для ухода с танцпола.
- 4 деки Traktor Pro + Xone:K2/K3 + Model 1 + Maschine Mikro/Jam + TB-03, синхронизация Ableton Link. Формулировка курса: **до 4 дек плюс Maschine**. [DJ Mag 2017](https://djmag.com/tech/chris-liebing-techno-alchemist), [Aulart](https://www.aulart.com/masterclass/chris-liebing-my-dj-techniques-vision-of-techno-en/), [GROOVE 2026](https://groove.de/2026/07/15/groove-podcast-510-chris-liebing/)

Значит «6 дек» у разговоров о нём — это **6+ каналов/слоёв**, а не 6 полных треков. Типовая архитектура:
- Deck A — основной ритм/низ,
- Deck B — следующий трек/альтернативный грув,
- Deck C — короткий loop/мелодия/перкуссия,
- Deck D — заготовка перехода/текстура,
- Maschine — one-shots (909 kit, claps, hats×2, rides, percussion) с макросами length/release/pitch, note repeat, velocity. [NI video 2024](https://www.youtube.com/watch?v=1vv6wlHUed8), [DJWorx](https://djworx.com/chris-liebing-traktor-maschine/)
- + TB-03 acid как живой голос.

Sync у него — не читерство, а освобождение внимания для выбора фрагмента/EQ/лупа/эффекта. [Native Instruments 2022](https://blog.native-instruments.com/traktor-20-mena/)

### 1.6 Лупы, EQ, эффекты

- Луп — материал аранжировки: мост, остинато, сжатие времени (4→2→1→1/2), деконструкция (оставить только верх). [Native Instruments 2022](https://blog.native-instruments.com/traktor-20-mena/)
- EQ/фильтр на Model 1: дисциплина > количества слоёв. Правило: **один главный низ, остальным — место выше**, ввод через фильтр/громкость, при росте плотности убирать, а не добавлять. [Aulart](https://www.aulart.com/masterclass/chris-liebing-my-dj-techniques-vision-of-techno-en/)
- FX (delay/reverb/filter): пространство и момент смены фазы, не постоянный хвост. [Mixmag](https://mixmag.net/feature/achieving-techno-zen-with-chris-liebing)
- CLR / CLR Podcast (315 выпусков, 150+ гостей, 2009-2015, затем возврат) и AM/FM (60-минутные необработанные фрагменты реальных сетов) — документ его селекции. [RA 28642](https://ra.co/news/28642), [DI.FM 127](https://www.di.fm/shows/amfm/episodes/127), [NASTY 2026](https://www.nastymagazine.com/music/create-learn-repeat-chris-liebing/)

**Чему учиться (в порядке иерархии навыков):** timing → phrasing → gain/EQ → выбор трека/энергия → harmonic mixing → loops/FX → multi-deck. 6 дек не чинят слабые первые 4.

---

## 2. Научные статьи и теория техно — что брать в код

### 2.1 Музыковедческий фундамент

- **Bougaïeff 2013 Minimal techno** — композиция/структура/техника. [Huddersfield](http://eprints.hud.ac.uk/id/eprint/18067)
- **Clark 2022 Programming the beat** — формальные правила композиции техно для алгоритмов. [DOI](https://doi.org/10.25949/24572326.v1)
- **Ziemer & Linke, Divergent Paths of Techno (DE vs US)** — MIR на студийных признаках, расхождение сцен. [TISMIR](https://transactions.ismir.net/articles/324/files/6a4f8507b5240.pdf)
- **Brøvig-Hanssen et al. 2021 A Grid in Flux** — сетка/тайминг/тембр, отклонения от квантизации. [DOI](https://doi.org/10.1093/mts/mtab013)
- **Zeiner-Henriksen 2010 PoumTchak** — ритм/звук/движение, four-on-the-floor. [Oslo](http://hdl.handle.net/10852/56756)
- **Butler 2001 Turning the Beat Around** — метрическая неоднозначность в EDM. [MTO](https://doi.org/10.30535/mto.7.6.1)

### 2.2 BPM/beat/структура/энергия

- **López-Serrano et al. 2016 Loop-Based Electronic Music** — декомпозиция лупов. [ISMIR](https://www.audiolabs-erlangen.de/content/resources/MIR/00_2016-ISMIR-EMLoop/2016_LopezSerranoDM_DcomposingEDM_ISMIR_ePrint.pdf)
- **Knees et al. 2015 EDM Tempo/Key Datasets** (Zenodo), **Schreiber & Müller 2018 Crowdsourced Tempo** — ошибки BPM, метрические неоднозначности. [Zenodo](https://doi.org/10.5281/zenodo.1414995), [ISMIR](https://ismir2018.ircam.fr/doc/pdfs/220_Paper.pdf)
- **Kim et al. 2026 Raveform** — 4902 микса, 56873 трека, 1423 размеченных трека (tempo/beats/downbeats/функциональные сегменты), energy-centered парадигма (интенсивность/ритм/текстура, не verse/chorus). [TISMIR](https://doi.org/10.5334/tismir.288)
- **Kim & Nam 2023 All-In-One Structure** — beat/downbeat/tempo/сегментация с attention на demixed audio. [WASPAA](https://doi.org/10.1109/WASPAA58266.2023.10248174)

**Энергетическая кривая** — не одна величина, а комбинация loudness/RMS, sub-band energy, onset density, spectral centroid/flux, тембр, функциональная структура (Raveform).

### 2.3 Математика DJ-сетов

- **Kim et al. 2020 Mix-to-Track Subsequence DTW** — 1557 миксов, 13728 треков, 20765 переходов, cue points, длительности, темп/транспозиция (транспонируется лишь 2.5%, из них 94.3% на полутон). [ISMIR](https://program.ismir2020.net/static/final_papers/352.pdf)
- **Kim, Yang & Nam 2021 Reverse-Engineering Transitions (sub-band + convex optimization)** — спектральные поддиапазоны, управление DJ в переходе. [NIME](https://nime.pubpub.org/pub/g7avj1a7/release/1)
- **Zehren 2022 Cue Points** — switch points для EDM. [CMJ](https://direct.mit.edu/comj/article/46/3/67/117159/Automatic-Detection-of-Cue-Points-for-the)
- **Williams et al. 2024 Deep Audio Representations** — CAE/OpenL3 vs MFCC/scattering, длина/гладкость перехода. [QMUL](https://qmro.qmul.ac.uk/xmlui/handle/123456789/104084)
- **Sowula & Knees 2024 Mosaikbox** — auto-DJ: beat-grid, tonal/rhythmic/timbral similarity, stem separation, подавление вокала, переход 16 downbeats, темп ±8%. [ISMIR](https://repositum.tuwien.at/bitstream/20.500.12708/212628/1/Sowula-2024-Mosaikbox%20Improving%20Fully%20Automatic%20DJ%20Mixing%20Through%20Rule-ba...-vor.pdf)
- **Williams et al. 2025 Temporal Considerations** — решения уровня перехода/трека/микса, flow после серии быстрых треков. [TIME](https://doi.org/10.4230/LIPIcs.TIME.2025.20)
- **UnmixDB (Schwarz & Fourer 2019)** — синтетические beat-sync миксы с ground truth. [Zenodo](https://zenodo.org/records/1422385)

### 2.4 Гармония и психоакустика

- **Faraldo et al. 2016/2017 Key Estimation in EDM** (multi-profile, minor/amodal треки). [hdl](http://hdl.handle.net/10230/44830)
- Датасеты **Beatport EDM Key** [Zenodo](https://doi.org/10.5281/zenodo.1101082) и **GiantSteps+** [Zenodo](https://zenodo.org/records/4153506)
- **Gebhardt et al. 2015/2016 Roughness & Pitch Commonality** — альтернатива Camelot: выделение синусоидальных partials, перебор ±6 semitones шагом 1/8, оптимизация roughness/commonality; listening test: минимальная roughness приятнее key-alignment. [Applied Sciences](https://doi.org/10.3390/app6050123)

**Вывод про Camelot:** Wheel — коммерческая нотация, не теория. Для техно недостаточно: треки модально неопределённы, совместимость зависит от регистра/тембра/плотности/участка. Сопоставлять надо с chroma/PCP, roughness, sub-band energy, listening test.

### 2.5 Спектр и грув

- **Gebhardt 2016** — roughness/virtual pitch, частичные синусоиды.
- **Lustig & Tan 2019 All about that bass** — фильтры, сохраняющие НЧ баса, повышают groove/liking. [DOI](https://doi.org/10.1177/0305735619836275)
- **Wesolowski & Hofmann 2016 More to Groove than Bass** [PLOS ONE](https://doi.org/10.1371/journal.pone.0163938), **Duncan & Orgs 2024** (house, переносимо) [DOI](https://doi.org/10.1525/mp.2024.42.2.95)

### 2.6 Практическая исследовательская схема для техно-сета (синтез)

1. Корпус: Raveform + своя строгая техно-выборка, фиксировать tracklists, границы переходов, версии треков.
2. Признаки сегмента: BPM/beat/downbeat, chroma/key confidence, centroid/rolloff/flux, loudness/sub-band, onset density, embeddings (OpenL3/CAE), структурные границы.
3. Совместимость: `S = w_h*S_h + w_r*S_r + w_t*S_t + w_e*S_e + w_s*S_s` (harmony/rhythm/timbre/energy/structure), где `S_h` — и key distance, и roughness.
4. Кривая сета: оптимизация последовательности как поиск пути с ограничениями на локальную mixability и глобальную энергию + listening test.

Минимальная сильная подборка: **Bougaïeff, Clark, Kim 2020, Raveform, Faraldo, Gebhardt, Kim 2021**.

---

## 3. Гайды: техники на N деках — дек-независимый подход

**Принцип (уточнение пользователя):** от количества дек не зависит. 2, 6 или 12 — это не разные дисциплины, а разное число одновременно доступных **ролей/слоёв**. Инструмент должен работать на любом N.

### 3.1 Раскладка ролей на N каналов (вместо «дека = трек»)

| Роль | Спектр | Пример содержимого | Правило |
|------|--------|-------------------|---------|
| **FOUNDATION** | Full, владелец LOW | текущий основной трек (kick/sub) | Только один владелец LOW в любой момент |
| **INCOMING** | Full, но LOW kill до swap | следующий основной трек | Ввод тихо, фэйдер ниже, LOW вырезан |
| **PERCUSSION** | High-pass | 8/16-beat hat/ride loop | Всегда high-pass, без низа |
| **TEXTURE** | Band-pass / High | noise/atmosphere/pad | Без низа, низкий gain |
| **VOICE** | Mid | vocal/stab loop, acid line | Только если есть место в mids |
| **BRIDGE / SPARE** | Любой | заготовка перехода, spare track, FX return, sampler | Запас |

На N=2: FOUNDATION + INCOMING (+ иногда TEXTURE на INCOMING). На N=6: FOUNDATION+INCOMING+PERCUSSION+TEXTURE+VOICE+BRIDGE. На N=12: добавить дубли ролей с другими тембрами. Правило **один LOW** масштабируется на любое N.

Pioneer советует начинать с упрощённого: доп. дека для loop/staging, при 3+ источниках баланс и EQ критичны. [Pioneer DJ](https://blog.pioneerdj.com/djtips/a-complete-guide-to-multi-deck-mixing/)

### 3.2 Beatmatching (руками/Sync/дрейф)

1. Cue на ясный kick beat 1 bar 1.
2. Совместить кики, проверить clap/snare на drift.
3. Jog/nudge кратко, pitch — для постоянной ошибки.
4. Sync экономит внимание на N>2, но не чинит неверный beatgrid — проверять grid в начале/середине/конце. [London Sound Academy](https://www.londonsoundacademy.com/blog/how-to-beatgrid-bpm-transition-tracks-with-rekordbox)

Тренировка: отключить Sync, увести второй трек на ±0.4 BPM, держать 64 такта.

### 3.3 Фразировка (универсально)

Такт = 4 удара. Крупные события на границах **8/16/32 такта**.

**32-тактовая схема (масштабируется на любое N):**
- 1–8: INCOMING тихо, LOW kill, ввести PERCUSSION/TEXTURE.
- 9–16: добавить MID INCOMING, убрать конкурирующий MID FOUNDATION.
- 17: на «1» фразы — быстрый LOW swap (FOUNDATION LOW ↓, INCOMING LOW ↑).
- 17–32: FOUNDATION → TEXTURE (убрать MID/HI, фейдер), INCOMING — новый FOUNDATION.

Для N>2: в 1–16 можно ротировать PERCUSSION/TEXTURE каждый 8 тактов, не трогая FOUNDATION.

Long blend 32–64 такта — норма для техно, один bassline доминирует. [Vibes](https://vibesdj.io/dj-tools/dj-transitions), [Crossfader](https://wearecrossfader.co.uk/blog/mix-like-a-techno-dj-3-ways-to-mix-techno/)

### 3.4 EQ/громкость — математика

1. TRIM по самому громкому месту трека — выровнять A/B.
2. Ввод INCOMING с LOW cut, фейдер ниже.
3. Освободить MID при конфликте лидов/acid/ride.
4. LOW swap быстро на границе фразы, не медленный микс двух сабов.
5. После swap — фейдер/частоты уходящего вниз.

Gain staging: trim — уровень канала, fader — музыкальное движение, master — клубный уровень. Канальные пики в зелёной/amber, не red. [DJM-A9](https://kulturbuero.ch/files-sg/DJM-A9_manual_EN.pdf)

**Физика:** два равногромких некоррелированных слоя → **+3 dB**, коррелированных → до **+6 dB**. При вводе 3-й/4-й деки заранее опускать trim/fader — место кончается быстрее, чем кажется по cue.

### 3.5 Harmonic mixing — фильтр, не закон

Camelot: из **8A** безопасно **8A, 7A, 9A, 8B**; A=minor B=major; +2 по той же стороне (8A→10A) — energy boost, редко. [Mixed In Key](https://mixedinkey.com/workflows/how-to-use-the-camelot-wheel/) Проверять pre-cue ушами.

### 3.6 Лупы/FX

- 8/16 beats — продлить intro/outro, сохранить фразу.
- 4 beats — удержать грув.
- 4→2→1→1/2 — roll/build, затем cut на «1». [Pioneer DJ](https://blog.pioneerdj.com/djtips/a-complete-guide-to-multi-deck-mixing/)

FX: echo out на последнем ударе фразы, reverb коротко, HPF перед bass swap, delay как хвост. Сначала **только EQ+faders**, FX только с функцией. [Mixgraph](https://www.mixgraph.io/mixing-guide/techno)

### 3.7 BPM — формулы (универсально)

- Новый темп: `B_new = B0·(1+p/100)`
- Нужный pitch: `p = 100·(Bt/B0 -1) %`
- Время N тактов (4/4): `t = 240·N / BPM` сек. Пример: 32 такта при 132 BPM → `240·32/132≈58.2c`.
- Ошибка beatmatch за t сек: `Δbeats = ΔBPM·t/60`, время до ухода на удар: `t1 = 60/|ΔBPM|`. Пример: 128→132 BPM → `p=+3.125%`. [Vibes pitch](https://vibesdj.io/dj-tools/pitch-tempo-calculator), [Mixgraph](https://www.mixgraph.io/tools/pitch-tempo)
- Без Key Lock сдвиг высоты: `Δs = 12·log2(1+p/100)` semitones, +6%≈+1 st. До ~4% комфортно, 4–8% распределять, больше — bridge track/halftime/echo-out.

### 3.8 Энергия и подготовка (N-независимо)

Energy ≠ BPM. Помечать трек: BPM, key, роль (warm-up/build/peak/release), плотность низа, вокал/lead, intro/first drop/breakdown/outro, entry/exit, loops.

На 60 мин:
1. Старт 60–70% пика.
2. Блоками 3–4 трека одной силы, затем шаг вверх.
3. 3–5 треков пика связкой + альтернативы.
4. Запас 20–30% сверх плана.
5. Передача слота — нейтральный грув.

Пик на 90 мин — 55–70 мин, +1 BPM между переходами как ускорение. [Mixgraph set planning](https://www.mixgraph.io/learn/dj-set-planning-guide)

Практика недели: 2 деки pitch+faders 64 такта → EQ 32 такта → Camelot парами → loops/echo → 3-я дека percussion → запись 45–60 мин.

Иерархия: timing → phrasing → gain/EQ → выбор трека/энергия → harmonic → loops/FX → multi-deck (N).

---

## 4. Зависимости проекта — что есть и что понадобится

**Есть (`pyproject.toml`):**
- `fastmcp[tasks,apps]>=3.2.4,<3.4` (MCP, 55 тулов), `sqlalchemy[asyncio]`, `pydantic`, `numpy`, `pyrekordbox`, `mdxnet-infer`
- `audio`: `librosa>=0.10`, `soundfile`, `scipy`, `essentia==2.1b6.dev1389`, `numba>=0.65`
- `stems`: `demucs>=4.0`, `torch>=2.0`, `torchcodec`, `psutil`, `mlx>=0.20; darwin`, `onnxruntime-silicon`/`onnxruntime`

**Для инструментов Liebing-стиля понадобится добавить (не ломая текущее):**

*Анализ (макс. картина без прослушивания):*
- `essentia` уже есть — для key/bpm/loudness, добавить `madmom` или `aubio` для более точного beat/downbeat на техно (Raveform-метрики), `openl3`/`laion-clap` для embeddings (CAE/OpenL3 из Williams 2024), `librosa` уже покрывает chroma/centroid/flux.
- `pedalboard`/`audiomentations` для аугментаций при обучении (если свой scoring).

*Математика/скоринг:*
- `scipy` уже есть — для roughness/pitch commonality (Gebhardt), `scikit-learn` для кластеризации/весов `S = Σ w·S`, `cvxpy` для convex optimization (Kim 2021 sub-band), `numba` уже.

*Рендеринг N дек:*
- `ffmpeg` (уже используется в `app/audio/render`), `rubberband`/`soundstretch` для time-stretch (уже `rubberband` в pipeline), `pyloudnorm` для LUFS-нормализации, `numpy` уже.

*Данные:*
- Доступ к `track_audio_features_computed` (73 поля L5), `beatgrid.json` (phase, bpm_measured), `dj_library_items` (file_path). Нужен доступ к `phrase_boundaries_ms`, `dominant_phrase_bars` для фразировки N.

*Не нужно:* новый фреймворк, замена FastMCP, тяжёлые LLM для аудио — всё решается DSP + правилами.

---

## 5. Набор отдельных инструментов — проект под твой принцип

**Принцип:** не один «собери сет», а **набор узких инструментов**, каждый делает одну вещь хорошо, комбинируется для любого N. Данные — максимум из БД/фич, слух — только финальная верификация.

### 5.1 Аналитические (дают картину без прослушивания)

| Инструмент | Что делает | Вход | Выход | Зависимости |
|------------|-----------|------|-------|-------------|
| `analyze_track_deep` | L5: 73 поля, key/bpm/lufs/flux/centroid/rolloff/onset/embedding/phrase | `track_id` | `track_features` | `essentia`, `librosa`, `openl3`, `demucs` (для S_h) |
| `analyze_loudness_map` | Sub-band energy (low/mid/high), spectral flux по фразам | `track_id, bars=8/16/32` | `energy_curve: [{bar, low, mid, high, flux}]` | `librosa`, `scipy` |
| `analyze_harmonic_profile` | Key + roughness/pitch commonality vs целевым тональностям | `track_id, target_keys` | `S_h per key, chroma` | `essentia`, `scipy` (Gebhardt) |
| `analyze_groove` | Onset density, syncopation, low-end amplitude → groove score | `track_id` | `groove, hp_ratio, kick_prominence` | `librosa`, `essentia` |
| `validate_grid` | `bpm_measured` vs `stored_BPM`, `phase_ms` drift | `version_id, mix_path` | `GridCheckResult` | `librosa` |

Каждый — отдельный `@tool`, не часть монолита.

### 5.2 Курирующие (отбор, не порядок)

| Инструмент | Что делает | Формула/правило |
|------------|-----------|-----------------|
| `curate_by_role` | Фильтр по ролям Liebing (FOUNDATION/PERCUSSION/TEXTURE/VOICE/BRIDGE) | `filters: {hp_ratio, kick_prominence, spectral_centroid, lufs, bpm_range, energy}` feature-first, не mood |
| `curate_by_energy_block` | Блоки 3–4 трека одной энергии, шаг вверх | `energy = f(lufs, sub-band, onset)` из Raveform |
| `find_bridge_tracks` | Треки, соединяющие два BPM/key с большим разрывом | `p = 100*(Bt/B0-1)`, halftime/echo-out кандидаты |

### 5.3 Скоринговые (совместимость для N)

| Инструмент | Формула | Источник |
|------------|---------|----------|
| `score_harmonic` | `S_h = α·key_distance + (1-α)·roughness` (Gebhardt) | Faraldo + Gebhardt |
| `score_rhythmic` | `S_r = 1 - |ΔBPM|/10 - drift_penalty` (Δbeats = ΔBPM·t/60) | Kim 2020, Vibes |
| `score_timbral` | `S_t = cosine(OpenL3)` или `MFCC` | Williams 2024 |
| `score_energy` | `S_e = 1 - |ΔLUFS|/6 - |Δsubband|/norm` | Lustig & Tan |
| `score_structure` | `S_s = phrase_align_bonus` (8/16/32) | Raveform, Butler |
| `score_transition` | `S = Σ w_i·S_i` (веса настраиваются) | Синтез §2.6 |

`transition_score_pool` уже есть (`app/tools/compute/transition_score.py`) — расширить до `components=true` с 5 метриками, `top_k` для N.

### 5.4 Планировщики (для любого N)

| Инструмент | Что делает | N-логика |
|------------|-----------|----------|
| `plan_phrase` | Разметка `t = 240·N/BPM`, границы 8/16/32 | Универсальная формула, не зависит от N |
| `plan_layer` | Назначение слоёв на N каналов с правилом **один LOW** | `N=2 → [FOUNDATION, INCOMING]`, `N=6 → +PERCUSSION+TEXTURE+VOICE+BRIDGE`, `N=12 → дубли ролей` |
| `plan_energy_curve` | Глобальная траектория 60–70%→пик 55–70 мин, блоки | `S` оптимизация как путь с ограничениями на `S` локально + энергия глобально (Kim 2025) |
| `optimize_sequence` | GA/greedy/constructive на `S`, уже есть `sequence_optimize` | GA любит +0.5 LUFS — для closing инвертировать |

### 5.5 Рендеринговые (N-deck mix)

| Инструмент | Что делает | Математика |
|------------|-----------|------------|
| `render_beatgrid` | `phase_ms`, `bpm_measured`, `trim_start` | `librosa.beat.beat_track`, `tempo_ratio = bpm_measured/target` |
| `render_stems` | 3-tier `mlx→onnx→torch` (уже `StemsConfig` 7.8s, jobs 0) | `DEMUCS_SHIFTS 5`, `PERCUSSION 2000Hz` |
| `render_mixdown` | N-канальный микс: `rubberband` time-stretch, `ffmpeg` amix, `gains_to_median` (±0dB сейчас), `SEM=1` на 8GB | `+3dB` некоррелир., `+6dB` коррелир., `Δs=12·log2(1+p/100)` |
| `render_diagnose` | `true_peak, level_jumps, near_silent, flow` | `pyloudnorm`, `scipy` |

Каждый рендер — отдельный background task (`FastMCP tasks`), `asyncio.to_thread` + `ctx.report_progress`.

### 5.6 Улучшающие (итерация)

| Инструмент | Что делает |
|------------|-----------|
| `suggest_replacement` | `local://tracks/{id}/suggest_replacement` уже есть — по BPM-близости, проверять стиль вручную |
| `diagnose_flow` | `analyze_set_flow` — energy arc, Camelot совместимость, texture diversity |
| `bench_stems` | `scripts/bench_stems_m2.py` — RTF/RSS/SDR-proxy для 3 рантаймов |

**Итог набора:** ~15 узких тулов вместо 1 монолита. Каждый принимает `track_ids` или `version_id`, отдаёт `dict`/`BaseModel` с `structuredContent` (FastMCP v3). Комбинируешь для любого N: `curate_by_role(N=2)` → `score_transition` → `plan_layer(N=6)` → `render_mixdown(transition_bars=32)` — один и тот же код, разное N.

---

## 6. Что делать дальше

1. **Не слушая:** прогнать `analyze_loudness_map` + `analyze_harmonic_profile` на 50 треках Liebing-подобного пула (126-133 BPM, 2024-2026 CLR) и сравнить `S_h` по Camelot vs roughness — проверить, где Camelot врёт на техно.
2. **Математика:** реализовать `S = Σ w·S` с весами из listening test (Gebhardt: roughness важнее key), протестировать на `Raveform` + своих миксах.
3. **N-инструменты:** вынести `plan_layer` как отдельный `@tool` с параметром `n_decks: int` (2..12) и ролями, покрыть тестами `N=2,4,6,12`.
4. **Данные:** завести `phrase_boundaries_ms` и `dominant_phrase_bars` в L5, если ещё нет — нужно для `plan_phrase` на любое N.
5. **Слушая:** собрать 30-мин сет на каждом N (2,4,6) одним и тем же пулом, сравнить `level_jumps`/`near_silent`/`true_peak` и слепой тест на гипноз (Techno Zen).

---

*Источники: 180 поисков, 3 high-effort exa agents, context7 FastMCP 3.2.4, pyproject.toml, app/audio, docs/research. Все утверждения — с grounding, формулы — с выводом, инструменты — дек-независимы.*

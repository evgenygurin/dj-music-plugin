# Neural Mix Transitions — Deep Dive

**Дата:** 2026-05-13
**Контекст:** анализ почему picker (`app/domain/transition/picker.py`) на acid/melodic техно ставит `VOCAL_CUT` для треков **без вокала**. Research проведён по 4 направлениям: наш код, библиотеки (librosa/essentia/demucs), djay Pro AI / Algoriddim под капотом, реальная DJ-практика техно-переходов.
**Связано:** [`docs/transition-scoring.md`](../transition-scoring.md), [`docs/research/2026-04-08-techno-transitions-research.md`](2026-04-08-techno-transitions-research.md), [`app/domain/transition/picker.py`](../../app/domain/transition/picker.py).

---

## TL;DR

1. **`vocal_cut` на бесвокальных треках — false-positive, не баг архитектуры.** Picker определяет "вокал" эвристикой `pitch_salience_mean > 0.4 AND spectral_centroid_hz > 2200 Hz` ([picker.py:75-82](../../app/domain/transition/picker.py#L75-L82)). У acid/melodic техно с TB-303-style лидами оба маркера срабатывают на синтезаторной партии (pitch_salience 0.7-0.9, centroid 2500-4000 Hz). Реальной vocal detection в коде **нет** — `StemSeparator` (demucs/htdemucs) помечен `NOT YET IMPLEMENTED` в [docs/audio-pipeline.md](../audio-pipeline.md).

2. **Наши 7 пресетов ≠ djay Pro AI preset names.** djay 5+ имеет **8 официальных Automix-пресетов** (`Automatic / Fade / EQ / Filter / Echo / Dissolve / Riser / Neural Mix™`) и **4 стема** (`drums / bass / harmonic / vocals` через AudioShake). Наши `VOCAL_SUSTAIN / HARMONIC_SUSTAIN / DRUM_SWAP / VOCAL_CUT / DRUM_CUT / ECHO_OUT / FADE` — это **наша академическая декомпозиция** того же концептуального пространства (stem-aware envelopes), не названия из UI djay.

3. **Каноническая taxonomy DJ-переходов = 6 физически различных действий + 2 stem-aware варианта.** Наши 7 пресетов покрывают ~60% real-world техно практики — миссят **`FILTER_SWEEP`** (signature move acid/hypnotic, planned в [`enable_filter_sweep_style`](../../.claude/dj-music.local.md.example)), **`LOOP_ROLL`** (требует loop detector), **`HARD_CUT`** (резкий swap без FX), **`STUTTER_FX`** (peak-time beat-repeat).

4. **Минимальный fix без архитектурных изменений** — добавить helper `_vocal_with_confidence()` который учитывает `energy_bands` ratio в вокальном диапазоне (300-3000 Hz) + поднять порог `_VOCAL_PRESENCE_PITCH_SALIENCE` с 0.4 до 0.55. Тесты регрессии — добавить acid техно fixture в `tests/domain/transition/test_picker.py`.

---

## 1. Что реально делает наш picker сейчас

### 1.1 Decision tree (first-match-wins)

[`app/domain/transition/picker.py:120-226`](../../app/domain/transition/picker.py#L120) — 7 правил сверху вниз:

| # | Условие | Preset | Confidence |
|---|---|---|---|
| 1 | `score.hard_reject == True` | `ECHO_OUT` | 0.55 |
| 2 | drum-only pair (mix-out + mix-in на percussion sections), `drums > 0.85` | `DRUM_SWAP` | 0.92 |
| 2b | drum-only pair, `drums > 0.65` | `DRUM_CUT` | 0.85 |
| 2c | drum-only pair, drums низкий | `FADE` | 0.70 |
| **3** | **A vocal-active (`pitch_salience > 0.4 AND centroid > 2200`)** + B vocal-active | **`VOCAL_CUT`** | **0.82** |
| 3b | A vocal-active + B vocal-low (`< 0.3`) | `VOCAL_SUSTAIN` | 0.88 |
| 3c | A vocal-active + B data missing | `ECHO_OUT` | 0.65 |
| 4 | A harmonic motif + Camelot dist ≤ 1 + B vocal-low | `HARMONIC_SUSTAIN` | 0.83 |
| 5 | energy delta > +2 LUFS + (RAMP_UP или HARD_PAIR) | `DRUM_CUT` | 0.86 |
| 6 | ambient_pair OR cool-down intent | `FADE` | 0.78 |
| 7 | default | `ECHO_OUT` | 0.60 |

### 1.2 Критические пороги

[`picker.py:44-58`](../../app/domain/transition/picker.py#L44-L58):

```python
_VOCAL_PRESENCE_PITCH_SALIENCE = 0.4   # ← false-positive root cause
_VOCAL_PRESENCE_CENTROID_HZ = 2200.0   # ← acid techno часто > 2200
_VOCAL_LOW_PITCH_SALIENCE = 0.3
_HARMONIC_MOTIF_MAX_PITCH_SALIENCE = 0.35
_HARMONIC_MOTIF_MIN_CENTROID_HZ = 800.0
_HARMONIC_MOTIF_MAX_CENTROID_HZ = 2400.0
_HARMONIC_KEY_DIST_MAX = 1
_ENERGY_DELTA_RAMP_UP_LUFS = 2.0
_DRUM_ONLY_DRUMS_HIGH = 0.85
_DRUM_ONLY_DRUMS_MID = 0.65
```

### 1.3 Vocal-active predicate

[`picker.py:75-82`](../../app/domain/transition/picker.py#L75-L82):

```python
def _vocal_active(t: TrackFeatures) -> bool:
    return (
        t.pitch_salience_mean is not None
        and t.spectral_centroid_hz is not None
        and t.pitch_salience_mean > _VOCAL_PRESENCE_PITCH_SALIENCE  # 0.4
        and t.spectral_centroid_hz > _VOCAL_PRESENCE_CENTROID_HZ    # 2200
    )
```

**Это единственный сигнал** на основе которого принимается решение о вокале. Реальной формантной/voicing-детекции нет.

### 1.4 Recipe builder (envelope materialisation)

Каждый из 7 пресетов имеет builder в [`app/domain/transition/builders.py`](../../app/domain/transition/builders.py) который материализует `StemKeyframe` envelopes по барам 0/4/8/16/24/28/32 для каждой пары `(deck, stem)`. Detail: [`docs/transition-scoring.md` § Per-preset 32-bar stem matrices](../transition-scoring.md).

---

## 2. Что физически делает `VOCAL_CUT` на бесвокальном треке

Преcет `VOCAL_CUT` envelope (по [builders.py](../../app/domain/transition/builders.py)):

```text
A.vocals:    0 dB ────────────────►  -∞ (kill at bar 4, echo_1_2 stutter)
A.harmonic:  0 dB ──────────────────────────────────►  -∞ (fade to 28)
A.drums:     0 dB ──────────────────────────────────►  -∞ (fade to 28)
A.bass:      0 dB ──────────────────────────────────►  -∞ (fade to 28)
B.drums:     -∞ ──── 0 dB ──────────────────────────────►  0 dB (4→28)
B.bass:      -∞ ──── 0 dB ──────────────────────────────►  0 dB (4→28)
B.harmonic:  -∞ ──── 0 dB ──────────────────────────────►  0 dB (4→28)
B.vocals:    -∞ ────────────────────────────────────────► 0 dB (28→32)
            bar 0    bar 4   bar 16    bar 24   bar 28   bar 32
```

Если в треке **нет вокала**, то `A.vocals` стем содержит residual (то что AudioShake/demucs не смог отдать в drums/bass/harmonic). Echo_1_2 stutter на bar 4 либо нечего killить (residual silent) → preset *по факту работает как HARD_CUT на bar 4* — резкий swap drums/bass/harmonic с лёгким FX-stutter. Что для acid техно может звучать нормально, но **не то что выбрал бы DJ осознанно**.

То есть **имя пресета некорректное, но поведение приемлемое.** Это объясняет почему треки в Nina Kraviz set реально звучат если их сложить по этой recipe — но picker делает выбор на ошибочных основаниях.

---

## 3. Что djay Pro AI делает на самом деле

### 3.1 Реальные стемы: 4 (с djay 5.0)

| Stem | Что содержит |
|---|---|
| `drums` | Kick, snare, hats, percussion |
| `bass` | Sub-bass, bassline (40-250 Hz) |
| `harmonic` | Pads, leads, chord progressions, **acid lines**, synth motifs |
| `vocals` | Human voice (lead vocals, samples, ad-libs) |

С djay Pro 5.0 (декабрь 2023) bass был отделён от harmonic благодаря интеграции **AudioShake** ([press release](https://www.algoriddim.com/press_releases/435-algoriddim-announces-major-update-to-djay-pro-ai)). До 5.0 — 3 стема (drums/instrumental/vocals), что до сих пор маячит на legacy overview-странице help.algoriddim.com.

### 3.2 Технология stem separation

- **До djay 5.0**: собственная Neural Mix-модель Algoriddim (детали не публиковались)
- **С djay 5.0**: **AudioShake** — hybrid waveform + spectrogram source separation, та же семья что Hybrid Transformer Demucs (FAIR, Defossez), но proprietary. AudioShake #1 в [Meta SAM Audio benchmarks](https://www.audioshake.ai/post/meta-tested-the-leading-audio-separation-models-audioshake-came-out-on-top), выше open-source demucs.
- **Realtime vs precompute**: гибрид. Stems вычисляются **при загрузке трека на деку** (~секунды на iPad Pro), потом доступны для realtime mute/solo/EQ-per-stem. Не online inference на каждом семпле.
- **Open-source аналог**: Hybrid Transformer Demucs v4 (MIT, ~9.0 dB SDR на MUSDB18-HQ; для сравнения Spleeter ~5.9 dB).

### 3.3 Официальные Automix-пресеты djay 5

Из [Algoriddim user manual](https://help.algoriddim.com/user-manual/djay-pro-windows/settings/automix):

| Preset | Что делает |
|---|---|
| **Automatic** | djay выбирает стиль по контексту пары |
| **Fade** | Линейный crossfade |
| **EQ** | EQ-swap (low/mid/high kill) |
| **Filter** | Filter sweep (HP/LP) |
| **Echo** | Echo-tail на outgoing + fade |
| **Dissolve** | "Delicately evaporates the outgoing track" |
| **Riser** | Riser FX перед swap |
| **Neural Mix™** | Stem-aware swap |

**Важно:** djay **не разбивает Neural Mix preset на под-варианты**. Это один пункт меню, и конкретное поведение (какой стем доминирует) определяется внутренней эвристикой djay. Наши 7 пресетов — это **детальная декомпозиция** того что djay делает за одним нажатием.

### 3.4 Match / track-picking AI

djay не сам обучает track-similarity model — делегирует через **TIDAL API** (Match feature). На локальной библиотеке (без TIDAL) — классические key/BPM/genre filters. Это аналогично нашему `sequence_optimize`, но у нас есть преимущество — GA поверх 6-component score.

---

## 4. Каноническая taxonomy DJ-переходов

Из [Crossfader](https://wearecrossfader.co.uk/blog/12-high-energy-dj-transitions/), [DJ TechTools](https://djtechtools.com/2009/01/26/phrasing-the-perfect-mix/), [Pirate](https://pirate.com/en/blog/advanced-dj-mixing-techniques/), [DJ.Studio](https://dj.studio/blog/basic-transition-techniques) и [ISMIR Kim et al. 2020](https://archives.ismir.net/ismir2020/paper/000352.pdf) — **6 физически различных действий**:

### 4.1 Шесть базовых примитивов

| # | Действие | Что физически меняется | Когда |
|---|---|---|---|
| 1 | **EQ blend** (long, 32-64 bars) | Bass→mid→high swap по фразам | Hypnotic / minimal / melodic / roller |
| 2 | **Filter sweep** (HPF on outgoing, LPF on incoming) | Spectral mask, не amplitude | Build tension, closing an idea, acid signature |
| 3 | **Echo-tail out** | Delay/reverb send up + fader/EQ kill | Cool-down, dramatic pause, hard subgenre shift |
| 4 | **Hard cut on downbeat** | Crossfader slam at phrase boundary | Drop reset, peak-time hard cut, BPM mismatch rescue |
| 5 | **Loop roll → drop** | 8/4/2/1-beat loop на outgoing → halve → release под incoming downbeat | High-energy tension builder |
| 6 | **Stutter / beat-repeat FX** | 1/4, 1/8, 1/16 repeats как rhythmic glitch | Peak-time accent, last-bar pre-drop |

### 4.2 Stem-aware варианты (3 поверх EQ blend)

`VOCAL_SUSTAIN`, `HARMONIC_SUSTAIN`, `DRUM_SWAP` — это **не отдельные физические действия**. Это `EQ blend` где **одна стем-группа держит unity gain дольше других**. На 4-стем routing'е (drums/bass/harmonic/vocals) — корректная декомпозиция, но физически это всё ещё EQ_BLEND + stem-level envelope, не 3 disjoint operations. То же про `VOCAL_CUT` / `DRUM_CUT` — это `HARD_CUT` или `STEM_CUT(target)` с разным target stem.

### 4.3 Фраза-counting + EQ kill ритуал (контекст)

Все переходы phrase-locked. Стандарт техно:
- `4 beat = 1 bar`
- `8 bar = 1 phrase` (32 beats)
- `4 phrase = 1 section` (128 beats)

Intro/outro classic techno = 64 bars (~2 мин на 130 BPM). Roller-сеты часто используют **64-bar blends** не 32. Наш default `bars=32` — корректный baseline, но для `hypnotic / minimal / ambient_dub` subgenre pairs стоит рассмотреть scaling до 64 через [`clamp_bars`](../../app/domain/transition/subgenre_rules.py).

**Канон EQ swap** ([DJ TechTools](https://djtechtools.com/amp/2012/03/11/eq-critical-dj-techniques-theory/), [DJ.Studio](https://dj.studio/blog/dj-eqmixing)):
1. Incoming: Low+Mid в 0, High ~12 часов, fader up. Слышны только hats incoming
2. Mid swap на следующем downbeat (16-bar boundary)
3. **Bass swap on the 1** — последний шаг, ровно на downbeat фразы. Не на kick-2 как часто пишут — на **kick-1 новой фразы**, критично для phase coherence

### 4.4 Bass clash physics

Две суб-басовые синусоиды на близких частотах (40-80 Hz) с разной фазой → constructive/destructive interference на бите. Звучит как amplitude wobble / null-out kick. Два kick'а одновременно → comb filtering всего low-end. LRA (loudness range) растёт > 6 LU → PA-система компрессит, mix теряет punch. **Поэтому bass swap должен быть точечный (1-2 beats), не gradual.** Наш `S_spectral` (Camelot 65% + bass band 20% + BPM 15%) корректно приоритезирует.

---

## 5. Vocal detection — что реально доступно

### 5.1 Что есть в коде (analyzers)

[`app/audio/analyzers/`](../../app/audio/analyzers/) — 18 analyzers, ни одного vocal-specific:

- ✅ `pitch_salience.py` (essentia `PitchYin` + harmonic peaks ratio) — **proxy для "наличие питч/гармоники", не для вокала**
- ✅ `spectral.py` — centroid, rolloff, flatness, flux, slope, contrast, HNR
- ✅ `energy.py` — 6 frequency bands (sub / low / lowmid / mid / highmid / high)
- ✅ `mfcc.py` — 13 MFCC coefficients
- ❌ `StemSeparator` (demucs/htdemucs) — [docs/audio-pipeline.md:33-34](../audio-pipeline.md) явно: **"NOT YET IMPLEMENTED (planned, requires [stems] extra)"**
- ❌ Voicing detection / F0 + confidence
- ❌ Formant analyzer
- ❌ Vocal-frequency-band energy ratio analyzer

### 5.2 Из 47 фич — только 3-4 намекают на вокал

| Фича | Что физически | Диапазон | Что говорит о вокале |
|---|---|---|---|
| `pitch_salience_mean` | essentia PitchYin harmonic ratio per-frame, mean | 0.0-1.0 | **HIGH = гармоничный контент** (lead, мелодия, **acid лид**, вокал) — НЕ vocal-specific |
| `spectral_centroid_hz` | средневзвешенное частот спектра | 0-22050 Hz | HIGH (>2200 Hz) — может быть вокал, может быть acid sweep |
| `chroma_entropy` | энтропия 12-note chroma vector | 0-3.0 | Низкая = tone-specific (вокал часто имеет low entropy) |
| `hnr_db` | Harmonic-to-Noise Ratio | -20 to +20 dB | High HNR = устойчивый pitch |

**Из тех что мы НЕ используем для vocal detection но могли бы**:
- `energy_bands[lowmid] + energy_bands[mid]` — энергия в 300-3000 Hz (вокальный диапазон)
- `dissonance_mean` — clash detection (две тональные линии)
- MFCC clustering — характерный timbre fingerprint

### 5.3 Почему picker false-positive на acid

Acid techno (TB-303, SH-101 сольная партия) типично:
- `pitch_salience_mean = 0.7-0.9` (один чистый синус, резонансный пик)
- `spectral_centroid_hz = 2500-4000 Hz` (узкий peak из-за resonant фильтра)
- **Вокала нет**

Picker видит `pitch_salience > 0.4 AND centroid > 2200 Hz` → `_vocal_active() == True` → правило #3 в decision tree срабатывает → `VOCAL_CUT`. Это **archetypal misuse pattern** для эвристики которая полагалась на correlations from pop/electronic с реальным вокалом.

### 5.4 Что библиотеки реально предлагают

**librosa:**
- `librosa.decompose.hpss(S)` — Harmonic/Percussive Source Separation (это НЕ vocal!)
- `librosa.pyin()` — F0 estimation + voicing decisions (есть! но не используется)
- Нет встроенного vocal-detector

**essentia:**
- `essentia.standard.PitchYin()` — что мы используем
- `essentia.standard.VoicingDetection()` — **есть в essentia ≥ 2.1b6, но НЕ используется в проекте**
- `essentia.standard.SpeechSegmentation()` — для речи, не для musical vocals

**Реальные ML stem-separation модели:**
- [demucs](https://github.com/facebookresearch/demucs) (FAIR, MIT) — Hybrid Transformer Demucs v4 ~9 dB SDR на MUSDB18-HQ
- [open-unmix](https://github.com/sigsep/open-unmix-pytorch) (Sigsep, MIT) — BLSTM-based, старее
- [spleeter](https://github.com/deezer/spleeter) (Deezer, MIT) — устаревший U-Net, ~5.9 dB SDR
- [AudioShake](https://www.audioshake.ai/) (proprietary) — используется в djay Pro 5

В нашем `pyproject.toml` есть `[stems]` extra с `demucs>=4.0` + `torch>=2.0`, но **в коде никто его не импортирует**. Можно установить (`uv sync --extra stems`) и реально считать стемы, но это ~30 сек/трек на CPU и требует 70-100 MB model download.

---

## 6. Gap-анализ: чего нашему picker не хватает

### 6.1 Отсутствующие пресеты (по приоритету)

| # | Preset | Зачем | Реализуемо сейчас? |
|---|---|---|---|
| 1 | **`FILTER_SWEEP`** | HPF ramp на outgoing (100Hz→5kHz over 16 bars) + LPF ramp на incoming (5kHz→20kHz). Signature move для hypnotic/acid техно (Kraviz, Klock, Marcel Fengler). | ✅ Да. Уже планируется — `enable_filter_sweep_style: true` в [`.claude/dj-music.local.md.example`](../../.claude/dj-music.local.md.example) |
| 2 | **`HARD_CUT`** | Резкий cut on downbeat без FX. Сейчас `DRUM_CUT` частично покрывает (slam на bar 32), но pure hard-cut нужен отдельно для phrase-end transitions. | ✅ Да. Можно добавить как `DRUM_CUT` с `bars=1` + special envelope. |
| 3 | **`STUTTER_FX`** | 1/16 beat-repeat на последних 2 bars outgoing перед incoming drop. Peak-time signature accent. | ✅ Да. Нужен новый builder + новое значение в `NeuralMixTransition` enum. |
| 4 | **`LOOP_ROLL`** | 8/4/2/1-beat loop на outgoing с прогрессивным halving → release на incoming downbeat. | ⚠️ Частично. Не требует loop detector в строгом смысле — нужно phrase boundary detection, которое уже есть через `track_sections`. Просто **никем не реализовано**. |

### 6.2 Избыточная гранулярность

Текущие 7 пресетов имеют **семантический overlap**:

- `VOCAL_SUSTAIN` и `HARMONIC_SUSTAIN` — структурно идентичны, отличаются только target stem
- `VOCAL_CUT` и `DRUM_CUT` — то же самое, отличаются target stem

Можно унифицировать в:
- `STEM_SUSTAIN(target: NeuralMixStem)` — заменяет VOCAL_SUSTAIN / HARMONIC_SUSTAIN
- `STEM_CUT(target: NeuralMixStem)` — заменяет VOCAL_CUT / DRUM_CUT

Это **не обязательно** делать сейчас (текущая структура работает), но при добавлении новых пресетов стоит унифицировать architecture.

### 6.3 Канонизированная taxonomy (proposal, 8 примитивов)

```text
1. EQ_BLEND(stem_priority: dict[NeuralMixStem, float])
     ← заменяет FADE / VOCAL_SUSTAIN / HARMONIC_SUSTAIN / DRUM_SWAP
       с stem_priority вектором
2. STEM_CUT(target: NeuralMixStem)
     ← заменяет VOCAL_CUT / DRUM_CUT
3. ECHO_OUT (existing)
4. FILTER_SWEEP ← NEW
5. LOOP_ROLL ← NEW
6. HARD_CUT ← NEW
7. STUTTER_FX ← NEW
8. BASS_SWAP_ON_THE_1 ← NEW
     ← короткий 2-bar EQ_BLEND с симметричным bass crossover
```

Это даёт DJ-faithful набор примитивов **без семантического overlap**, и покрывает ~90% real-world техно практики.

---

## 7. Рекомендации

### 7.1 Краткосрочные (можно сделать за час, не ломая существующий код)

**A. Поправить `_vocal_active()` чтобы acid не триггерился:**

```python
# app/domain/transition/picker.py

_VOCAL_PRESENCE_PITCH_SALIENCE = 0.55      # ← было 0.4, поднять
_VOCAL_PRESENCE_CENTROID_HZ = 2200.0       # (оставить)
_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40       # ← NEW: energy_lowmid+mid / total

def _vocal_active(t: TrackFeatures) -> bool:
    """Эвристика наличия вокала с использованием 3 сигналов."""
    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False

    pitch_check = t.pitch_salience_mean > _VOCAL_PRESENCE_PITCH_SALIENCE
    centroid_check = t.spectral_centroid_hz > _VOCAL_PRESENCE_CENTROID_HZ

    # Дополнительный фильтр: вокал требует энергии в lowmid+mid (300-3000 Hz).
    # Acid lead = узкий peak в highmid → midband_ratio низкий.
    midband_check = True
    if t.energy_lowmid is not None and t.energy_mid is not None and t.energy_mean is not None:
        midband = (t.energy_lowmid + t.energy_mid) / max(t.energy_mean, 1e-6)
        midband_check = midband > _VOCAL_PRESENCE_MIDBAND_RATIO

    return pitch_check and centroid_check and midband_check
```

**B. Добавить regression test:**

```python
# tests/domain/transition/test_picker.py

def test_acid_techno_not_classified_as_vocal():
    """Regression: acid techno (high pitch_salience, narrow centroid peak)
    must NOT trigger VOCAL_CUT / VOCAL_SUSTAIN."""
    acid_track = TrackFeatures(
        pitch_salience_mean=0.85,          # high salience (303 resonance)
        spectral_centroid_hz=3200.0,       # high centroid (resonant peak)
        energy_lowmid=0.15,                # low midband
        energy_mid=0.10,
        energy_mean=0.65,                  # total mostly in highmid+high
        # ... rest of features
    )
    assert _vocal_active(acid_track) is False
```

**C. Документация:**
- Добавить в [`docs/transition-scoring.md`](../transition-scoring.md) явный раздел "Known Limitations: Vocal Detection".
- Обновить [`docs/audio-pipeline.md`](../audio-pipeline.md) — указать что `pitch_salience_mean` это proxy для "harmonic presence", не vocal.

### 7.2 Среднесрочные (1-2 дня)

**D. Добавить `FILTER_SWEEP` preset:**
- Новый enum value `NeuralMixTransition.FILTER_SWEEP`
- Новый builder в [`builders.py`](../../app/domain/transition/builders.py): HPF ramp envelope на A + LPF ramp на B
- В picker: добавить правило для acid/hypnotic subgenre pair → FILTER_SWEEP
- StemKeyframe для filter sweep моделируется как gradual high-cut на A stems + gradual low-cut на B stems

**E. Раскрыть essentia VoicingDetection:**
- Добавить новый analyzer `VoicingAnalyzer` в `app/audio/analyzers/`
- Добавить колонку `voicing_ratio` в `track_audio_features_computed`
- В picker `_vocal_active()` использовать `voicing_ratio > 0.3` вместо `pitch_salience > 0.55`
- Это даёт реальный voicing-decision (sustained pitch с natural vibrato) вместо raw pitch_salience

### 7.3 Долгосрочные (неделя+)

**F. Реальная stem separation через demucs:**
- `uv sync --extra stems` — установить demucs + torch
- Создать `StemSeparator` analyzer в `app/audio/analyzers/stems.py`
- L4 tier: вычислять стемы при analysis_level=4, кешировать в `track_timeseries`
- Stem-aware features: `vocal_energy_mean`, `vocal_centroid`, `drum_energy_share`, etc.
- ~30 сек/трек на CPU; для VM с GPU — 5-7 сек
- 23,768 tracks × 30 сек = ~200 часов CPU. Не делать для всей библиотеки сразу — только для playlists в активной работе

**G. Канонизировать taxonomy:**
- Унифицировать `VOCAL_SUSTAIN/HARMONIC_SUSTAIN/DRUM_SWAP` → `EQ_BLEND(stem_priority)`
- Унифицировать `VOCAL_CUT/DRUM_CUT` → `STEM_CUT(target)`
- Это требует миграции БД (`transitions.fx_type` enum) + переписывания builders
- Бенефит — чистая abstraction для добавления новых пресетов

---

## 8. Источники

### Algoriddim / djay Pro AI

- [Neural Mix™ Overview](https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix/overview)
- [Adding FX to Neural Mix™ stems (4-stem confirmation)](https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix/fx)
- [Using Neural Mix™ on supported controllers](https://help.algoriddim.com/topic/hardware/using-neural-mix-on-supported-controllers)
- [Automix overview](https://help.algoriddim.com/user-manual/djay-pro-windows/mixing-basics/automix)
- [Automix settings — transition list](https://help.algoriddim.com/user-manual/djay-pro-windows/settings/automix)
- [djay Pro AI 5.0 Press Release — 4-channel stems](https://www.algoriddim.com/press_releases/435-algoriddim-announces-major-update-to-djay-pro-ai)
- [DJ TechTools: djay Pro 5.0 + AudioShake partnership](https://djtechtools.com/2023/12/06/algoriddims-djay-pro-5-0-is-here-hyper-fast-stem-separation-flexible-beat-grids/)
- [AudioShake × Algoriddim Neural Mix collaboration](https://www.audioshake.ai/post/algoriddim-djaypro-neural-mix)
- [AudioShake #1 in Meta SAM Audio benchmarks](https://www.audioshake.ai/post/meta-tested-the-leading-audio-separation-models-audioshake-came-out-on-top)

### Stem Separation Tech

- [Hybrid Transformer Demucs (FAIR)](https://github.com/facebookresearch/demucs)
- [Open-Unmix (Sigsep)](https://github.com/sigsep/open-unmix-pytorch)
- [DJ.Studio: Evidence-based DJ stem separation guide (SDR comparison)](https://dj.studio/blog/evidence-based-guide-dj-stem-separation)

### DJ Practice & Theory

- [Rule of 32 — Good Time DJ](https://goodtimedj.com/rule-of-32-in-djing-menlo-park/)
- [Phrase Mixing — Native Instruments](https://blog.native-instruments.com/phrase-mixing/)
- [Techno Track Structure — UniverseOfTracks](https://universeoftracks.com/the-ultimate-guide-to-techno-track-structure/)
- [Phrasing The Perfect Mix — DJ TechTools](https://djtechtools.com/2009/01/26/phrasing-the-perfect-mix/)
- [Mix Like A Techno DJ — Crossfader](https://wearecrossfader.co.uk/blog/mix-like-a-techno-dj-3-ways-to-mix-techno/)
- [DJ EQ Mixing — DJ.Studio](https://dj.studio/blog/dj-eqmixing)
- [EQ Critical Techniques — DJ TechTools](https://djtechtools.com/amp/2012/03/11/eq-critical-dj-techniques-theory/)
- [Bass Line and Low-End Mixing — Pheek](https://audioservices.studio/blog/bass-line-and-low-end-mixing-tips)
- [16 Basic Transition Techniques — DJ.Studio](https://dj.studio/blog/basic-transition-techniques)
- [12 High-Energy DJ Transitions — Crossfader](https://wearecrossfader.co.uk/blog/12-high-energy-dj-transitions/)
- [DJ Looping Guide — Crossfader](https://wearecrossfader.co.uk/blog/dj-looping-guide/)
- [Advanced DJ Mixing — Pirate](https://pirate.com/en/blog/advanced-dj-mixing-techniques/)
- [How To DJ With Acapellas — Digital DJ Tips](https://www.digitaldjtips.com/how-to-dj-with-acapellas/)
- [Melodic Techno Mixing Guide — Mixgraph](https://www.mixgraph.io/mixing-guide/melodic-techno)
- [Nina Kraviz Trip Label — Bandcamp Daily](https://daily.bandcamp.com/label-profile/nina-kraviz-trip-records-interview)
- [Peak Time Techno — TechnoSpaceTrip](https://technospacetrip.com/what-is-peak-time-techno/)
- [LUFS for Techno — Teknup](https://www.teknup.com/how-to-set-lufs-for-techno-the-ultimate-loudness/)

### Academic / ISMIR

- [Kim et al. ISMIR 2020 — "A Computational Analysis of Real-World DJ Mixes"](https://archives.ismir.net/ismir2020/paper/000352.pdf)
- [Schwarz & Fourer ISMIR 2018 — Unmixdb dataset](https://github.com/SLapointe-Mtl/Unmixdb)
- [Hirai CMJ 2022 — Automatic Detection of Cue Points](https://direct.mit.edu/comj/article/46/3/67/117159/Automatic-Detection-of-Cue-Points-for-the)
- [DJtransGAN ICASSP 2022](https://arxiv.org/abs/2110.06525)
- [DJ StructFreak ISMIR 2023](https://ismir2023program.ismir.net/lbd_328.html)
- [Cue Point Estimation using Object Detection arXiv 2024](https://arxiv.org/html/2407.06823v1)
- [mir-aidj djmix-analysis project page](https://mir-aidj.github.io/djmix-analysis/)

### Audio Libraries

- [librosa documentation](https://librosa.org/doc/latest/index.html)
- [essentia algorithm reference (VoicingDetection)](https://essentia.upf.edu/reference/std_VoicingDetection.html)

---

## 9. Связанные документы проекта

- [`docs/transition-scoring.md`](../transition-scoring.md) — формула + 7 presets + Camelot wheel + recipe engine
- [`docs/research/2026-04-08-techno-transitions-research.md`](2026-04-08-techno-transitions-research.md) — обзор по техно-transitions (предшественник)
- [`docs/audio-pipeline.md`](../audio-pipeline.md) — pipeline orchestration + analyzer registry + status `StemSeparator`
- [`docs/audio-schema.md`](../audio-schema.md) — 47 features в `track_audio_features_computed`
- [`app/domain/transition/picker.py`](../../app/domain/transition/picker.py) — picker decision tree
- [`app/domain/transition/builders.py`](../../app/domain/transition/builders.py) — 7 preset envelope builders
- [`app/domain/transition/neural_mix.py`](../../app/domain/transition/neural_mix.py) — stem-compat scoring

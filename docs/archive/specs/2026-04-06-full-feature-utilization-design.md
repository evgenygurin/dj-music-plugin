# Full Audio Feature Utilization — Design Spec

> Задача: задействовать все 55 audio features из `track_audio_features_computed` во всех подсистемах.
> Текущая утилизация: ~22/55 в scoring, ~22/55 в classifier, ~6/55 в export, ~12/55 в panel.
> Целевая: 55/55 — каждое поле используется хотя бы в одной подсистеме.

---

## 1. Transition Scoring (19 → 34 features)

### 1.1 BPM component (2 → 5 features)

| Feature | Как использовать |
|---------|-----------------|
| `bpm_confidence` | Множитель: `min(conf_a, conf_b)`. Если confidence < 0.5, BPM score снижается до 70% |
| `variable_tempo` | Штраф -0.15 если хотя бы один трек имеет variable_tempo=true |
| `bpm_histogram_first_peak_weight` | Если weight < 0.5 (полиритмичный), проверять `bpm_histogram_second_peak_bpm` для double/half-time |

### 1.2 Harmonic component (3 → 6 features)

| Feature | Как использовать |
|---------|-----------------|
| `atonality` | Если оба трека атональные → harmonic score = 0.8 (не штрафовать, key не важен) |
| `key_confidence` | Множитель: `min(conf_a, conf_b)`. Low confidence → ослабить harmonic penalty |
| `chroma_entropy` | Уже загружается но не используется. Высокая энтропия → размытый тональный центр → ослабить penalty |

### 1.3 Energy component (1 → 5 features)

| Feature | Как использовать |
|---------|-----------------|
| `short_term_lufs_mean` | Взвешенное среднее с integrated_lufs (70/30) для более точной оценки перехода |
| `loudness_range_lu` | Penalty: если \|LRA_a - LRA_b\| > 8 LU → -0.10 (трудно сводить ровно) |
| `crest_factor_db` | Similarity: если \|crest_a - crest_b\| > 10 dB → -0.10 (грубый переход) |
| `energy_slope` | Bonus +0.05 если оба трека имеют одинаковый знак slope (оба растут или падают) |

### 1.4 Spectral component (5 → 8 features)

| Feature | Как использовать |
|---------|-----------------|
| `spectral_rolloff_85` | Similarity: `1 - \|rolloff_a - rolloff_b\| / max_rolloff`. Вес 15% в spectral sub-score |
| `spectral_rolloff_95` | Совместно с rolloff_85 для оценки частотного диапазона (среднее двух) |
| `spectral_slope` | Similarity: `1 - \|slope_a - slope_b\| / max_slope`. Вес 10% |
| `spectral_flux_std` | Similarity: `1 - \|flux_std_a - flux_std_b\| / max_flux_std`. Вес 5% |

Пересчитать веса внутри spectral component:
- mfcc_sim: 30% (было 40%)
- centroid_sim: 20% (было 30%)
- band_balance: 20% (было 30%)
- rolloff_sim: 15% (новое)
- slope_sim: 10% (новое)
- flux_std_sim: 5% (новое)

### 1.5 Groove component (3 → 6 features)

| Feature | Как использовать |
|---------|-----------------|
| `pulse_clarity` | Similarity: `1 - \|clarity_a - clarity_b\|`. Два трека с чётким пульсом → проще сводить |
| `hp_ratio` | Similarity: `1 - \|hp_a - hp_b\| / max(hp_a, hp_b)`. Перкуссивный+гармоничный = плохо |
| `tempogram_ratio_vector` | Cosine similarity (как beat_loudness_band_ratio). Ритмическая совместимость |

Пересчитать веса:
- onset_match: 25% (было 35%)
- kick_match: 25% (было 35%)
- beat_loudness: 20% (было 30%)
- pulse_clarity_sim: 10% (новое)
- hp_ratio_sim: 10% (новое)
- tempogram_sim: 10% (новое)

### 1.6 Timbral component (2 → 4 features)

| Feature | Как использовать |
|---------|-----------------|
| `danceability` | Similarity: `1 - \|dance_a - dance_b\| / max_dance`. Оба танцевальных или оба атмосферных |
| `dynamic_complexity` | Similarity: `1 - \|dc_a - dc_b\| / max_dc`. Похожая динамика → лучший переход |

Пересчитать веса:
- spectral_contrast_sim: 35% (было 50%)
- pitch_salience_sim: 35% (было 50%)
- danceability_sim: 15% (новое)
- dynamic_complexity_sim: 15% (новое)

### 1.7 Затронутые файлы

- `app/core/track_features.py` — добавить 15 полей в TrackFeatures dataclass
- `app/repositories/feature.py` — расширить SQL-запрос в `get_scoring_features` / `get_scoring_features_batch`
- `app/services/scoring.py` — обновить 6 scoring methods
- `app/core/constants.py` — новые пороги (LRA_DIFF_PENALTY, CREST_DIFF_PENALTY и т.д.)
- `app/config.py` — новые settings для порогов (настраиваемые)
- `tests/` — обновить scoring тесты

### 1.8 Оставшиеся 21 поле (не в scoring)

Scoring после обогащения: 34/55. Оставшиеся 21 поле покрываются classifier, export, panel, audit:
- `energy_max`, `energy_std`, `energy_sub/low/lowmid/mid/highmid/high` (8) → classifier profiles
- `energy_sub_ratio` ... `energy_high_ratio` (6) → panel visualization
- `rms_dbfs`, `true_peak_db`, `momentary_max` (3) → export + audit
- `mood`, `mood_confidence` (2) → classifier output, panel, export
- `analysis_level`, `pipeline_run_id` (2) → metadata, panel

---

## 2. Export / Delivery

### 2.1 M3U8 — новые EXTDJ tags

```text
#EXTDJ-MOOD-CONFIDENCE:{mood_confidence:.2f}
#EXTDJ-RMS:{rms_dbfs:.1f}
#EXTDJ-PEAK:{true_peak_db:.1f}
#EXTDJ-CREST:{crest_factor_db:.1f}
#EXTDJ-DANCEABILITY:{danceability:.2f}
#EXTDJ-HP-RATIO:{hp_ratio:.2f}
#EXTDJ-PHRASE:{dominant_phrase_bars} bars
```

### 2.2 JSON Guide — полные features

Секция `track.audio_features` расширяется до всех 55 полей, сгруппированных:

```json
{
  "tempo": {"bpm", "confidence", "stability", "variable_tempo"},
  "loudness": {"integrated_lufs", "short_term_mean", "momentary_max", "rms_dbfs", "true_peak_db", "crest_factor_db", "loudness_range_lu"},
  "energy": {"mean", "max", "std", "slope", "bands": {...}, "ratios": {...}},
  "spectral": {"centroid_hz", "rolloff_85", "rolloff_95", "flatness", "flux_mean", "flux_std", "slope", "contrast"},
  "key": {"code", "confidence", "atonality", "hnr_db", "chroma_entropy"},
  "rhythm": {"mfcc_vector", "hp_ratio", "onset_rate", "pulse_clarity", "kick_prominence"},
  "advanced": {"danceability", "dissonance_mean", "dynamic_complexity", "tonnetz", "tempogram_ratio", "beat_loudness_band_ratio", "spectral_complexity", "pitch_salience"},
  "structure": {"bpm_histogram": {...}, "phrase_boundaries_ms", "dominant_phrase_bars"},
  "classification": {"mood", "confidence"}
}
```

### 2.3 Cheat Sheet — новые колонки

```text
#  Title                BPM   Key  LUFS   Mood          Phrase  Flags
01 Soul Spiritism       129.2 5A   -13.3  dub_techno    8 bars
02 Modest               123.1 11B  -13.2  minimal       8 bars
03 Boogeyman            123.1 5B   -13.8  progressive   8 bars  ⚠ VarTempo
```

Flags: `⚠ VarTempo`, `⚠ Peak>-0.5`, `⚠ LowConf`

### 2.4 Rekordbox XML

- `rms_dbfs` → `<TEMPO>` нормализация
- `phrase_boundaries_ms` → memory cue points (`<POSITION_MARK Type="0">`)

### 2.5 Затронутые файлы

- `app/services/export.py` — M3U8 writer, JSON guide writer, cheat sheet writer, Rekordbox writer
- `app/services/delivery_service.py` — передавать полные features в export
- `app/repositories/feature.py` — новый метод `get_full_features(track_id)` для export (все 55 полей)

---

## 3. Panel

### 3.1 Dashboard — новые charts

| Chart | Feature | Тип визуализации |
|-------|---------|-----------------|
| Danceability Distribution | `danceability` | Histogram (bar) |
| HP Ratio Distribution | `hp_ratio` | Histogram (bar) |
| Dynamic Complexity | `dynamic_complexity` | Histogram (bar) |
| Energy Distribution | `energy_mean` | Histogram (bar) |
| Crest Factor | `crest_factor_db` | Histogram (bar) |
| Phrase Length | `dominant_phrase_bars` | Pie (4/8/16/32 bars) |
| Variable Tempo | `variable_tempo` | Badge count |
| Atonality | `atonality` | Badge count |
| BPM Confidence | avg(`bpm_confidence`) | Gauge indicator |

### 3.2 Track Detail — полные features

**Loudness tab** (1 → 7 полей):
`integrated_lufs`, `short_term_lufs_mean`, `momentary_max`, `rms_dbfs`, `true_peak_db`, `crest_factor_db`, `loudness_range_lu`

**Energy tab** (2 → 16 полей):
`energy_mean/max/std/slope` + 7 bands bar chart + 6 ratios

**Spectral tab** (3 → 8 полей):
`centroid_hz`, `rolloff_85/95`, `flatness`, `flux_mean/std`, `slope`, `contrast`

**Key tab** (2 → 5 полей):
`key_code`, `key_confidence`, `atonality` (badge), `hnr_db`, `chroma_entropy`

**Rhythm tab** (4 → 6 полей):
+ `tempogram_ratio_vector` mini-chart, `hp_ratio` уже есть

**Classification**: `mood_confidence` badge рядом с mood (green/yellow/red)

### 3.3 Track List — optional columns

Toggle через column visibility: `energy_mean`, `hp_ratio`, `danceability`, `dynamic_complexity`, `mood_confidence`, `analysis_level`

### 3.4 Затронутые файлы

- `panel/lib/queries/dashboard.ts` — 9 новых запросов
- `panel/lib/queries/tracks.ts` — расширить SELECT до всех 55 полей
- `panel/app/page.tsx` — новые chart components
- `panel/components/charts/` — 6 новых chart components
- `panel/components/track-features.tsx` — расширить все табы
- `panel/app/library/page.tsx` — optional columns

---

## 4. Classifier & Curation

### 4.1 Mood Classifier — новые features в profiles

Добавить в subgenre profiles (которые сейчас их не используют):

| Feature | Subgenres где полезен |
|---------|----------------------|
| `onset_rate` | breakbeat (высокий), minimal (низкий), tribal (средне-высокий) |
| `kick_prominence` | peak_time/industrial (высокий), ambient_dub/dub_techno (низкий) |
| `integrated_lufs` | hard_techno (> -8), ambient_dub (< -14) |
| `spectral_contrast` | acid (высокий), dub_techno (низкий) |
| `spectral_rolloff_85` | hard_techno (высокий), minimal (низкий) |
| `bpm` | breakbeat (< 130), hard_techno (> 145), ambient_dub (< 125) |
| `bpm_histogram_first_peak_weight` | tribal/breakbeat (< 0.6, полиритмичные) |

Добавить в `_CLASSIFIER_FIELDS`:

| Feature | Subgenres где полезен |
|---------|----------------------|
| `tempogram_ratio_vector` | tribal (нестабильный ритм) vs driving (стабильный) |
| `dominant_phrase_bars` | progressive/melodic_deep (16/32 bars) vs minimal/acid (4 bars) |

### 4.2 Audit Playlist — новые проверки

| Проверка | Feature | Порог | Severity |
|----------|---------|-------|----------|
| Clipping risk | `true_peak_db > -0.3` | -0.3 dB | warning |
| Unreliable BPM | `bpm_confidence < 0.5` | 0.5 | warning |
| Unreliable key | `key_confidence < 0.4` | 0.4 | warning |
| Variable tempo | `variable_tempo = true` | — | info |
| Too harmonic | `hp_ratio > 8.0` | 8.0 | warning |
| Excessive dynamics | `crest_factor_db > 30` | 30 dB | warning |
| Noise-like | `spectral_flatness > 0.5` | 0.5 | warning |

### 4.3 Review Set Quality — новые метрики

| Метрика | Features | Что проверяет |
|---------|----------|---------------|
| Danceability arc | `danceability` per position | Монотонность / провалы |
| HP Ratio jumps | `hp_ratio` between consecutive | Резкие скачки > 2.0 |
| Phrase alignment | `dominant_phrase_bars` pairs | Разная длина фразы у соседей |

### 4.4 Затронутые файлы

- `app/services/mood.py` (или `profiles.py`) — обновить 15 subgenre profiles + weights
- `app/models/audio.py` — расширить `_CLASSIFIER_FIELDS` (+2 поля)
- `app/services/curation_service.py` — audit_playlist (новые проверки), review_set_quality (новые метрики)
- `app/config.py` — новые пороги для audit
- `tests/` — обновить classifier и audit тесты

---

## 5. Coverage Matrix

| Feature | Scoring | Classifier | Export | Panel | Audit |
|---------|---------|------------|--------|-------|-------|
| bpm | BPM | NEW | M3U8/JSON/cheat | list/dash | range |
| bpm_confidence | NEW | NEW | JSON | NEW | NEW |
| bpm_stability | BPM | profiles | JSON | detail | — |
| variable_tempo | NEW | — | NEW cheat flag | NEW badge | NEW |
| integrated_lufs | Energy | NEW | M3U8/JSON/cheat | list/dash | range |
| short_term_lufs_mean | NEW | — | JSON | NEW detail | — |
| momentary_max | — | — | NEW JSON | NEW detail | — |
| rms_dbfs | — | — | NEW M3U8/JSON | NEW detail | — |
| true_peak_db | — | — | NEW M3U8/JSON | NEW detail | NEW |
| crest_factor_db | NEW | profiles | NEW M3U8/JSON | NEW detail/dash | NEW |
| loudness_range_lu | NEW | profiles | JSON | NEW detail | — |
| energy_mean | — | profiles | JSON | list/dash | — |
| energy_max | — | — | JSON | detail | — |
| energy_std | — | profiles | JSON | NEW detail | — |
| energy_slope | NEW | profiles | JSON | NEW detail | — |
| energy_sub..high (7) | spectral | profiles | JSON | NEW chart | — |
| energy_*_ratio (6) | — | — | JSON | NEW detail | — |
| spectral_centroid_hz | spectral | profiles | JSON | detail | — |
| spectral_rolloff_85 | NEW | NEW | JSON | NEW detail | — |
| spectral_rolloff_95 | NEW | — | JSON | NEW detail | — |
| spectral_flatness | spectral | profiles | JSON | detail | NEW |
| spectral_flux_mean | — | profiles | JSON | NEW detail | — |
| spectral_flux_std | NEW | profiles | JSON | NEW detail | — |
| spectral_slope | NEW | — | JSON | NEW detail | — |
| spectral_contrast | timbral | NEW | JSON | detail | — |
| key_code | harmonic | — | M3U8/JSON/cheat | list/dash | — |
| key_confidence | NEW | — | JSON | NEW detail | NEW |
| atonality | NEW | — | JSON | NEW badge | — |
| hnr_db | harmonic | — | JSON | NEW detail | — |
| chroma_entropy | NEW | — | JSON | NEW detail | — |
| mfcc_vector | spectral | — | JSON | detail | — |
| hp_ratio | NEW | profiles | NEW M3U8 | detail | NEW |
| onset_rate | groove | NEW | JSON | detail | — |
| pulse_clarity | NEW | profiles | JSON | detail | — |
| kick_prominence | groove | NEW | JSON | detail | — |
| danceability | NEW | profiles | NEW M3U8 | NEW dash | — |
| dynamic_complexity | NEW | profiles | JSON | NEW dash | — |
| dissonance_mean | spectral | profiles | JSON | detail | — |
| tonnetz_vector | harmonic | — | JSON | detail | — |
| tempogram_ratio_vector | NEW | NEW | JSON | NEW chart | — |
| beat_loudness_band_ratio | groove | — | JSON | detail | — |
| spectral_complexity_mean | spectral | profiles | JSON | detail | — |
| pitch_salience_mean | timbral | profiles | JSON | detail | — |
| bpm_histogram_first_peak_weight | NEW | NEW | JSON | detail | — |
| bpm_histogram_second_peak_bpm | NEW | — | JSON | detail | — |
| bpm_histogram_second_peak_weight | NEW | — | JSON | detail | — |
| phrase_boundaries_ms | — | NEW | NEW JSON/Rekordbox | detail | — |
| dominant_phrase_bars | — | NEW | NEW cheat/M3U8 | NEW dash | — |
| mood | — | output | M3U8/JSON/cheat | list/dash | — |
| mood_confidence | — | output | NEW M3U8 | NEW badge | — |
| analysis_level | — | — | — | detail | — |

**Result: 55/55 features используются в >= 1 подсистеме.**

---

## 6. Принципы реализации

1. **Backward compatibility**: все новые features в scoring — additive. Если feature = None, используется нейтральное значение (0.5 или без penalty). Существующие scores не ломаются.
2. **Configurability**: все новые пороги — через `settings.*` (не magic numbers).
3. **Weights tuning**: внутренние веса sub-components настраиваемые, но общие веса 6 компонентов (0.22/0.20/0.23/0.15/0.10/0.10) не меняются.
4. **Testing**: каждое изменение scoring покрывается unit-тестом с synthetic features.
5. **Panel**: новые charts используют существующий cyberpunk theme. Новые компоненты следуют shadcn patterns.

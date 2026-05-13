# Audio DB Schema — Core Tables Overview

> Короткий обзор "что у нас есть по аудио" в БД, без расширенных P1/P2 фич.
> Для полной справки по features см. `app/models/track_features.py` и
> `docs/domain-glossary.md`. Live row counts — `entity_aggregate(entity="...", operation="count")` или `mcp__plugin_dj-music_db__list_tables`.

## Покрытие данными (2026-04-18, post-BFS expansion)

| Таблица | Строк | Покрытие / комментарий |
|---|---:|---|
| `tracks` | **23,929** | базовый каталог треков (BFS пополняет к 20000 из YM playlist 1355) |
| `track_audio_features_computed` | **23,768** | **≈99%** треков проанализированы |
| `track_sections` | **1,680,465** | ~70 секций на трек — structure analyzer прогоняется по умолчанию |
| `dj_library_items` | **97** ⚠️ | физических MP3 на диске мало — скачиваются только под `deliver_set_workflow` (L4) |
| `dj_beatgrids` | **31** | beatgrid analyzer запускается редко |
| `dj_cue_points` | **0** | drop-pending таблица (blueprint §13.2) |
| `dj_saved_loops` | **0** | drop-pending |
| `keys` | 24 | static reference (Camelot wheel) |

### Что это значит для транзиций

**Работает:**

- BPM, key, energy, LUFS, kick_prominence, hp_ratio — **99%** треков (`track_audio_features_computed`)
- Intro/outro detection и section boundaries — везде (`track_sections` огромная)
- Camelot harmonic compatibility — есть (`key_code` + static `keys` lookup)
- LUFS normalization, adaptive swap depth, kick-click kill, dry/wet LR4 — работает на этих данных

**Degraded:**

- **Downbeat alignment** (`firstDownbeatSec`) — `dj_beatgrids` покрывает ~0.1% треков, mix-point detector использует fallback `0`. Для 4/4 техно с intro на `t=0` это OK, но при нестандартном downbeat фаза слегка off.
- **Cue-aware mix points** — `dj_cue_points` пустой (drop-pending). Mix-in/out берутся только из section boundaries, не из manually-set hot-cue'ов.
- **Multi-file tracks** — `dj_library_items` 97/23929 (файлы качаются под set delivery, не всплошную).

### BPM distribution

Снапшот на 2026-04-18: ядро коллекции — 120-129 BPM (classic peak-time /
driving techno). Запрос: `entity_aggregate(entity="track_features",
operation="histogram", field="bpm")`.

---

## ERD — core audio tables

```mermaid
erDiagram
    tracks ||--o| track_audio_features_computed : "1:1 features"
    tracks ||--o{ track_sections : "structural segments"
    tracks ||--o{ dj_library_items : "physical files"
    dj_library_items ||--o{ dj_beatgrids : "BPM grids"
    dj_beatgrids ||--o{ dj_beatgrid_change_points : "variable tempo"
    dj_library_items ||--o{ dj_cue_points : "hot cues"
    dj_library_items ||--o{ dj_saved_loops : "loops"
    track_audio_features_computed }o--|| keys : "key_code lookup"

    tracks {
        int id PK
        string title
        string sort_title
        int duration_ms
        int status "0=active 1=archived"
    }

    track_audio_features_computed {
        int track_id PK_FK
        int pipeline_run_id FK
        int analysis_level "0 none, 2 L1+L2, 3 L3"
        float bpm "20-300"
        float bpm_confidence "0-1"
        float bpm_stability "0-1"
        bool variable_tempo
        float integrated_lufs "dB"
        float short_term_lufs_mean
        float momentary_max
        float rms_dbfs
        float true_peak_db "dBFS"
        float crest_factor_db
        float loudness_range_lu
        float energy_mean "0-1"
        float energy_sub "20-60 Hz"
        float energy_low "60-250 Hz"
        float energy_lowmid "250-500 Hz kick click"
        float energy_mid
        float energy_highmid
        float energy_high
        float spectral_centroid_hz
        float spectral_rolloff_85
        float spectral_rolloff_95
        float spectral_flatness
        float spectral_flux_mean
        float spectral_flux_std
        float spectral_slope
        float spectral_contrast
        int key_code "0-23 Camelot"
        float key_confidence
        bool atonality
        float hnr_db "harmonic-noise ratio"
        float chroma_entropy
        string mfcc_vector "JSON 13 coeffs"
        float hp_ratio "harmonic-percussive"
        float onset_rate "per sec"
        float pulse_clarity
        float kick_prominence "0-1"
        string mood "techno subgenre label"
        float mood_confidence
    }

    track_sections {
        int id PK
        int track_id FK
        int section_type "0 intro 1 attack 2 build 3 pre-drop 4 drop 5 peak 6 breakdown 7 outro 8 rise 9 valley 10 sustain 11 ambient"
        int start_ms
        int end_ms
        float energy "0-1"
        float confidence "0-1"
    }

    dj_library_items {
        int id PK
        int track_id FK
        string file_path
        string file_uri
        string file_hash "sha256"
        int file_size
        string mime_type
        int bitrate
        int sample_rate "Hz"
        int channels
        string source_app
    }

    dj_beatgrids {
        int id PK
        int library_item_id FK
        float bpm "20-300"
        float first_downbeat_ms "NULL-ok"
        float grid_offset_ms "alt field"
        float confidence "0-1"
        bool variable_tempo
        bool canonical "primary grid"
    }

    dj_beatgrid_change_points {
        int id PK
        int beatgrid_id FK
        float position_ms
        float bpm
    }

    dj_cue_points {
        int id PK
        int library_item_id FK
        float position_ms
        int kind "0-7 cue/hotcue/memory"
        int hotcue_index "0-15"
        string label
        string color
        bool quantized
        string source_app
    }

    dj_saved_loops {
        int id PK
        int library_item_id FK
        float in_position_ms
        float out_position_ms
        float length_ms
        int hotcue_index "0-15"
        string label
        bool active_on_load
        string color
    }

    keys {
        int key_code PK "0-23"
        int pitch_class "0-11"
        int mode "0 minor 1 major"
        string name "'A minor'"
        string camelot "'8A'"
    }
```

---

## Что покрывает какие проблемы транзиций

| Задача crossfade | Откуда данные | Статус |
|---|---|---|
| BPM match + tempo sync | `features.bpm` | ✅ 96.6% |
| LUFS normalization | `features.integrated_lufs` + `true_peak_db` | ✅ 96.6% |
| Key compatibility (Camelot) | `features.key_code` + `keys` table | ✅ 96.6% |
| Adaptive kick-kill depth | `features.kick_prominence` | ✅ 96.6% |
| Adaptive swap length | `features.hp_ratio` | ✅ 96.6% |
| Low-band overlap prediction | `features.energy_sub / energy_low / energy_lowmid` | ✅ 96.6% |
| Intro/outro seek targets | `track_sections` | ✅ ~70 секций/трек |
| **Downbeat alignment** | `dj_beatgrids.first_downbeat_ms` | ❌ **0 строк** |
| **Variable tempo handling** | `dj_beatgrid_change_points` | ❌ 0 строк |
| **Manual hot-cue anchors** | `dj_cue_points` | ❌ 0 строк |
| **Loop roll transitions** | `dj_saved_loops` | ❌ 0 строк |

---

## Что сделать чтобы использовать **все** данные

1. **Прогнать beatgrid analyzer** на всю библиотеку → заполнит
   `dj_library_items` + `dj_beatgrids` → панель начнёт видеть реальные
   `first_downbeat_ms` вместо fallback'а `0`. Downbeat-alignment тогда
   реально будет работать, а не только на "intro начинается на t=0"
   треках.
2. **Cue-point detector** → `dj_cue_points` → можно использовать
   manually-set hot-cue как mix-in / mix-out anchors в дополнение к
   автоматическим `track_sections`.
3. **Loop detector** → `dj_saved_loops` → позволит реализовать
   `LOOP_ROLL` transition style (отсутствует в текущих 6 style'ах
   backend scorer'а).

---

## Excluded (extended P1/P2 features)

Следующие 13 полей из `track_audio_features_computed` **не включены** в
схему выше — они есть в БД, но не используются в текущем crossfade
pipeline:

- `energy_max`, `energy_std`, `energy_slope`
- `energy_{sub,low,lowmid,mid,highmid,high}_ratio` (6 band-ratio полей)
- `danceability`, `dynamic_complexity`, `dissonance_mean`
- `tonnetz_vector`, `tempogram_ratio_vector`, `beat_loudness_band_ratio`
- `spectral_complexity_mean`, `pitch_salience_mean`
- `bpm_histogram_first_peak_weight`, `bpm_histogram_second_peak_bpm`,
  `bpm_histogram_second_peak_weight`
- `phrase_boundaries_ms`, `dominant_phrase_bars`

Пока схема фокусируется на тех 30+ core полях которые реально
читаются crossfade dispatcher'ом в `audio-player-context.tsx` +
`mix-meta.ts`. Extended P1/P2 фичи — для mood classifier и scoring,
не для audio engine.

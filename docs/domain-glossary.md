# Domain Glossary

DJ-специфичная терминология для понимания кодовой базы.

## Музыкальные понятия

| Термин | Описание | В коде |
|--------|----------|--------|
| **BPM** | Beats Per Minute — темп трека (120-155 для техно) | `float`, range 20-300 |
| **Key** | Тональность трека (A minor, C major, ...) | `key_code: int` 0-23 |
| **Camelot** | Система нотации ключей для DJ-микширования (1A-12B) | `camelot.py`, 24 ключа на колесе |
| **Camelot Distance** | Расстояние между двумя ключами (0=идеально, 6=макс) | `camelot_distance()` |
| **LUFS** | Loudness Units Full Scale — стандарт измерения громкости | `energy_lufs: float`, обычно -20...-4 |
| **Cue Point** | Отметка в треке (позиция для прыжка, hot cue) | `CuePoint` model, `CueKind` enum |
| **Beatgrid** | Сетка битов — BPM + позиция первого удара | `Beatgrid` model |
| **Stem** | Отдельный звуковой слой (vocals, drums, bass, other) | `stems.py` analyzer |
| **MFCC** | Mel-Frequency Cepstral Coefficients — "отпечаток" звука | 13 коэффициентов, `mfcc.py` |

## DJ Set понятия

| Термин | Описание | В коде |
|--------|----------|--------|
| **Transition** | Переход между двумя треками | `Transition` model, 5-компонентный score |
| **Energy Arc** | Кривая энергии сета (обычно build → peak → release) | `target_energy_arc` JSON в Set |
| **Template** | Шаблон сета (classic_60, peak_hour_60, ...) | `SetTemplate` enum, 8 шаблонов |
| **Slot** | Позиция в шаблоне с target mood/energy/BPM | Определены в template definitions |
| **Pinned Track** | Трек, закреплённый в сете (GA не может убрать) | `pinned: bool` в SetItem |
| **Hard Conflict** | Переход с score=0.0 (нарушены hard constraints) | BPM>10, Camelot≥5, Energy>6 LUFS |

## Techno Subgenres (15)

Упорядочены по энергии (low → high):

```text
ambient_dub → dub_techno → minimal → detroit → melodic_deep →
progressive → hypnotic → driving → tribal → breakbeat →
peak_time → acid → raw → industrial → hard_techno
```

`driving` и `hypnotic` — "catch-all" subgenres, штрафуются при классификации.

## Audio Features (47 дескрипторов)

| Группа | Дескрипторы | Ключевые для |
|--------|-------------|-------------|
| **Tempo** | bpm, confidence, stability, variable_tempo | Transition: BPM matching |
| **Loudness** | integrated_lufs, short_term_lufs_mean, momentary_max, rms_dbfs, true_peak_db, crest_factor_db, loudness_range_lu | Transition: energy step |
| **Energy** | mean, max, std, slope + 7-band breakdown | Mood classification |
| **Spectral** | centroid_hz, rolloff_85/95, flatness, flux_mean/std, slope, contrast | Transition: timbral similarity |
| **Key** | key_code, confidence, atonality, chroma_vector, hnr_db, chroma_entropy | Transition: harmonic compatibility |
| **Rhythm** | mfcc_vector(13), hp_ratio, onset_rate, pulse_clarity, kick_prominence | Transition: groove matching |

## Platform IDs

Каждый трек может быть связан с несколькими платформами:

| Платформа | ID поле | Метаданные |
|-----------|---------|-----------|
| Yandex Music | `yandex_track_id` | album, label, cover, duration, explicit |
| Spotify | `spotify_track_id` | popularity, preview_url, audio_features |
| Beatport | `beatport_track_id` | bpm, key, genre/subgenre, preview |
| SoundCloud | `soundcloud_track_id` | plays, favorites, streamable, artwork |

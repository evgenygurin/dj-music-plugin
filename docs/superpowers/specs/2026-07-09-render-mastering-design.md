# Render Mastering Pipeline — Design

> Date: 2026-07-09 · Status: approved · Branch: `feat/render-mastering`
>
> Builds on:
> - `docs/superpowers/specs/2026-07-08-transition-render-refactor-design.md` (current render graph)
> - `docs/audio-pipeline.md` , `docs/render-pipeline.md`
>
> Goal: устранить глухой/ватный звук микса — добавить per-track предобработку и мастер-шину с эквализацией, компрессией и улучшенным лимитером.

---

## Problem

Текущий микс звучит: середина выпирает, не хватает высоких, нет чистоты и панча. Причина — чисто FFmpeg-скрипт без частотной и динамической коррекции.

**Корневые проблемы** (из исследования `graph.py`):
1. `alimiter attack=5ms` без правильного lookahead — съедает атаку киков
2. Нет per-band эквализации — баланс зависит только от исходников
3. `dynaudnorm maxgain=6` — поднимает шум/реверб, создавая муть
4. Нет HPF — суб-басовый мусор вызывает интермодуляцию в лимитере
5. Простые lowpass/highpass без Linkwitz-Riley — фазовые искажения на кроссоверах

---

## Architecture

Гибридный подход: Python + FFmpeg. Два прохода рендера.

### Pass 1 — Per-track pre-processing

Каждый трек обрабатывается отдельным FFmpeg перед входом в микс:

```
[track.wav] → volume(gain) → rubberband(tempo) → 
  highpass=30Hz (elliptic 4-pole) → 
  firequalizer(per-track EQ кривая) → 
  acompressor(мягкая 3:1, порог -18dB, атака 10ms, релиз 80ms)
  → [pipe в главный граф]
```

**HPF 30Hz** — elliptic 4-го порядка. Убирает суб-бас <30Hz до того как он дойдёт до лимитера и вызовет интермодуляционные искажения.

**firequalizer per-track EQ** — 18-band эквалайзер. Кривая строится из `track_features`:
- `spectral_centroid_hz > 3000` (яркий трек): -1dB на 2-4kHz (не пересвечивать)
- `spectral_centroid_hz < 2000` (тёмный трек): +1.5dB на 8-12kHz (добавить воздуха)
- Всегда: -1dB на 300-500Hz (убрать «коробочность»/мутность середины)

**acompressor** — мягкая пред-компрессия:
- `ratio=3:1`, `threshold=-18dB`, `attack=10ms`, `release=80ms`, `knee=6dB`
- Срезает только пики перед финальным лимитером, не убивает динамику
- RMS detection для музыкальности

### Pass 2 — Main graph (кроссфейды + мастер-шина)

```
[track_1_pipe] [track_2_pipe] ... [track_N_pipe]
  → 3-band crossfade (существующий EQ ритуал)
  → [mix] → acompressor(glue) → firequalizer(master EQ) → alimiter → output.mp3
```

**Glue compressor** — склеивает микс:
- `ratio=2:1`, `threshold=-14dB`, `attack=30ms`, `release=150ms`, `knee=8dB`
- RMS detection, мягкое колено

**Master EQ** — финальная тональная коррекция:
- +1.5dB на 10-12kHz (high shelf) — воздух, прозрачность
- -1dB на 200-400Hz (bell, Q=0.7) — убрать гулкость
- +0.5dB на 60-80Hz (bell, Q=0.5) — вес кику

**Лимитер** — улучшенные настройки:
- `attack=2ms` (было 5) — с lookahead у `alimiter` это НЕ режет транзиенты, а наоборот точнее их пропускает
- `release=40ms` (было 60) — меньше пампинга на басе
- `limit=0.95` (-0.45dBFS ceiling) — запас под true-peak
- `level_in=1`, `level_out=1`, `asc=1`

**dynaudnorm** — `maxgain=2` (было 6) или убрать совсем

**MP3 encoding** — `libmp3lame -b:a 320k -q:a 0`

---

## File changes

### Modify: `app/config/render.py`

New settings:
```python
# Pre-processing
hpf_cutoff_hz: float = 30.0
per_track_eq_mid_cut_db: float = -1.0
per_track_eq_bright_boost_db: float = 1.5
pre_comp_threshold_db: float = -18.0
pre_comp_ratio: float = 3.0
pre_comp_attack_ms: float = 10.0
pre_comp_release_ms: float = 80.0

# Master bus
glue_comp_threshold_db: float = -14.0
glue_comp_ratio: float = 2.0
glue_comp_attack_ms: float = 30.0
glue_comp_release_ms: float = 150.0
master_eq_air_boost_db: float = 1.5
master_eq_mud_cut_db: float = -1.0
master_eq_sub_boost_db: float = 0.5
limiter_attack_ms: float = 2.0
limiter_release_ms: float = 40.0
dynaudnorm_maxgain: float = 2.0
```

### Modify: `app/domain/render/graph.py`

- `build_preprocess_graph(track, features)` — новый метод, генерирует per-track pre-processing filterchain
- `build_filtergraph(plan)` — изменён: принимает уже предобработанные треки + добавляет glue comp + master EQ

### New: `app/domain/render/eq.py`

- `build_per_track_eq(features: TrackFeatures) -> str` — firequalizer-строка из фич
- `build_master_eq() -> str` — статическая кривая мастер-шины

### Modify: `app/audio/render/runner.py`

- Двухпроходный рендер: сначала pre-processing каждого трека в pipe, потом main graph
- `-q:a 0` в параметрах MP3

---

## Target loudness

- **Integrated LUFS: -9** (клубный стандарт)
- **True peak: -1 dBTP** (запас под lossy кодирование)
- **LRA:** 4-6 LU (умеренная динамика для техно)

---

## Out of scope

- Мульти-дечный рендер (отдельная фаза)
- True-peak лимитер (oversampled) — `alimiter` работает по sample-peak
- Linkwitz-Riley кроссоверы — остаются текущие фильтры
- Стерео-обработка (width, M/S EQ)

# Render Mastering Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить per-track предобработку и мастер-шину с EQ/компрессией/лимитером для устранения глухого звука микса и достижения клубного качества (-9 LUFS).

**Architecture:** Гибрид Python + FFmpeg. Два прохода: (1) per-track pre-processing через FFmpeg pipe (HPF 30Hz + firequalizer EQ + acompressor), (2) main graph — кроссфейды + glue compressor + master EQ + улучшенный лимитер. Настройки в `RenderSettings`.

**Tech Stack:** FFmpeg (firequalizer, acompressor, alimiter, highpass), scipy.signal (только валидация EQ в тестах)

## Global Constraints

- Все python-команды — через `uv run python`
- Тесты — `uv run pytest`
- Линт — `uv run ruff check --fix`
- Коммит после каждой задачи
- Ответы и комментарии на русском, идентификаторы на английском
- Значения частот, dB, ms — брать точно из спеки `docs/superpowers/specs/2026-07-09-render-mastering-design.md`

---

### Task 1: Config — добавить настройки мастеринга в RenderSettings

**Files:**
- Modify: `app/config/render.py`

**Interfaces:**
- Produces: новые поля `RenderSettings` — доступны через `plan.pre_comp_threshold_db` и т.д. в `RenderPlan`

- [ ] **Step 1: Добавить поля в RenderSettings**

В файл `app/config/render.py`, после `limiter_ceiling` (строка 54), добавить:

```python
    # ── Per-track pre-processing ──
    hpf_cutoff_hz: float = Field(default=30.0, gt=0, description="Subsonic highpass filter cutoff.")
    per_track_eq_mid_cut_db: float = Field(
        default=-1.0, le=0, description="300-500Hz mid cut for all tracks."
    )
    per_track_eq_bright_boost_db: float = Field(
        default=1.5, ge=0, description="8-12kHz boost for dark tracks (centroid < 2000 Hz)."
    )
    pre_comp_threshold_db: float = Field(default=-18.0, description="Pre-compressor threshold.")
    pre_comp_ratio: float = Field(default=3.0, gt=1, description="Pre-compressor ratio.")
    pre_comp_attack_ms: float = Field(default=10.0, gt=0, description="Pre-compressor attack.")
    pre_comp_release_ms: float = Field(default=80.0, gt=0, description="Pre-compressor release.")

    # ── Master bus ──
    glue_comp_threshold_db: float = Field(default=-14.0, description="Glue compressor threshold.")
    glue_comp_ratio: float = Field(default=2.0, gt=1, description="Glue compressor ratio.")
    glue_comp_attack_ms: float = Field(default=30.0, gt=0, description="Glue compressor attack.")
    glue_comp_release_ms: float = Field(default=150.0, gt=0, description="Glue compressor release.")
    master_eq_air_boost_db: float = Field(default=1.5, ge=0, description="10-12kHz high shelf boost.")
    master_eq_mud_cut_db: float = Field(default=-1.0, le=0, description="200-400Hz mud cut.")
    master_eq_sub_boost_db: float = Field(default=0.5, ge=0, description="60-80Hz sub weight boost.")
    limiter_attack_ms: float = Field(default=2.0, gt=0, description="alimiter attack (ms).")
    limiter_release_ms: float = Field(default=40.0, gt=0, description="alimiter release (ms).")
    dynaudnorm_maxgain: float = Field(default=2.0, ge=0, description="dynaudnorm maxgain (was 6).")
```

- [ ] **Step 2: Тест — поля читаются из RenderSettings**

```python
# tests/config/test_render_mastering.py
from app.config.render import RenderSettings


def test_mastering_defaults():
    s = RenderSettings()
    assert s.hpf_cutoff_hz == 30.0
    assert s.pre_comp_threshold_db == -18.0
    assert s.pre_comp_ratio == 3.0
    assert s.glue_comp_ratio == 2.0
    assert s.master_eq_air_boost_db == 1.5
    assert s.limiter_attack_ms == 2.0
    assert s.limiter_release_ms == 40.0
    assert s.dynaudnorm_maxgain == 2.0
```

- [ ] **Step 3: Запустить тест**

```bash
uv run pytest tests/config/test_render_mastering.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/config/render.py tests/config/test_render_mastering.py
git commit -m "feat(render): add mastering settings to RenderSettings"
```

---

### Task 2: EQ module — построитель кривых firequalizer

**Files:**
- Create: `app/domain/render/eq.py`
- Create: `tests/domain/render/test_eq.py`

**Interfaces:**
- Produces: `build_per_track_eq(features) -> str` — firequalizer-строка
- Produces: `build_master_eq() -> str` — мастер-кривая

- [ ] **Step 1: Написать модуль eq.py**

```python
"""Firequalizer curve builders for per-track and master EQ."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.features import TrackFeatures

_MASTER_EQ_CURVE = [
    "entry(65, 0)",
    "entry(92, 0)",
    "entry(131, 0.5)",   # 60-130Hz sub weight
    "entry(185, 0.3)",
    "entry(262, -0.5)",   # 200-400Hz mud cut start
    "entry(370, -1.0)",   # 370Hz max cut
    "entry(523, -0.5)",
    "entry(740, 0)",
    "entry(1046, 0)",
    "entry(1480, 0)",
    "entry(2093, 0)",
    "entry(2960, 0)",
    "entry(4186, 0)",
    "entry(5920, 0.5)",   # 6-8kHz presence
    "entry(8372, 1.0)",   # 8-12kHz air start
    "entry(11840, 1.5)",  # 10-12kHz air peak
    "entry(16744, 1.2)",  # 16kHz gentle rolloff
    "entry(20000, 0.5)",  # 20kHz
]


def build_master_eq(mud_cut_db: float = -1.0, air_boost_db: float = 1.5, sub_boost_db: float = 0.5) -> str:
    curve = []
    for entry in _MASTER_EQ_CURVE:
        # parse and adjust
        parts = entry.strip("entry()").split(",")
        freq = float(parts[0].strip())
        gain = float(parts[1].strip())
        if 200 <= freq <= 500 and gain < 0:
            gain = mud_cut_db * (abs(gain) / 1.0)  # scale to configured cut
        elif 6000 <= freq <= 20000 and gain > 0:
            gain = air_boost_db * (gain / 1.5)  # scale to configured boost
        elif 60 <= freq <= 185 and gain > 0:
            gain = sub_boost_db * (gain / 0.5)
        curve.append(f"entry({int(freq)},{gain:.1f})")
    return ":".join(curve)


def build_per_track_eq(features: "TrackFeatures") -> str:
    """Build per-track EQ curve from track audio features.

    Dark tracks (centroid < 2000 Hz): boost highs.
    Bright tracks (centroid > 3000 Hz): cut 2-4kHz.
    All tracks: gentle mid cut at 300-500Hz.
    """
    centroid = features.spectral_centroid_hz or 2200.0
    mid_cut = -1.0  # dB, configurable later

    entries = {
        "65": 0, "92": 0, "131": 0, "185": 0,
        "262": 0, "370": mid_cut / 2, "523": mid_cut,
        "740": mid_cut / 2, "1046": 0, "1480": 0,
    }

    if centroid > 3000:
        # Bright track — slight 2-4kHz cut
        entries["2093"] = -0.5
        entries["2960"] = -1.0
        entries["4186"] = -0.5
        entries["5920"] = 0
        entries["8372"] = 0
        entries["11840"] = 0
    elif centroid < 2000:
        # Dark track — high boost
        entries["2093"] = 0
        entries["2960"] = 0
        entries["4186"] = 0.5
        entries["5920"] = 0.8
        entries["8372"] = 1.2
        entries["11840"] = 1.5
    else:
        entries["2093"] = 0
        entries["2960"] = 0
        entries["4186"] = 0
        entries["5920"] = 0
        entries["8372"] = 0
        entries["11840"] = 0

    entries["16744"] = 0
    entries["20000"] = 0

    curve = [f"entry({freq},{gain:.1f})" for freq, gain in entries.items()]
    return f"firequalizer=gain_entry='{':'.join(curve)}'"


def build_preprocess_filter(ratio: float, gain_db: float, eq_filter: str) -> str:
    """Assemble per-track pre-processing filter chain."""
    return (
        f"highpass=f=30:t=4,"   # elliptic 4-pole HPF at 30Hz
        f"volume={gain_db:.2f}dB,"
        f"{eq_filter},"
        f"acompressor=threshold=-18dB:ratio=3:attack=10:release=80:"
        f"knee=6:detection=rms:link=average:makeup=1"
    )
```

- [ ] **Step 2: Написать тест**

```python
# tests/domain/render/test_eq.py
from app.domain.render.eq import build_master_eq, build_per_track_eq, build_preprocess_filter
from app.shared.features import TrackFeatures


def test_build_master_eq_returns_firequalizer():
    result = build_master_eq()
    assert result.startswith("entry(")
    assert "1.5" in result  # air boost at 11840
    assert "-1.0" in result  # mud cut at 370


def test_build_per_track_eq_dark_track():
    feat = TrackFeatures(spectral_centroid_hz=1500.0)
    result = build_per_track_eq(feat)
    # Dark track should have positive gain at high frequencies
    assert any(float(p.split(",")[1].strip(")")) > 0 for p in result.split("entry(") if "11840" in p or "8372" in p)


def test_build_per_track_eq_bright_track():
    feat = TrackFeatures(spectral_centroid_hz=3500.0)
    result = build_per_track_eq(feat)
    # Bright track should have negative gain at 2-4kHz
    assert any(float(p.split(",")[1].strip(")")) < 0 for p in result.split("entry(") if "2960" in p)


def test_build_per_track_eq_neutral_track():
    feat = TrackFeatures(spectral_centroid_hz=2500.0)
    result = build_per_track_eq(feat)
    assert "11840" in result  # high freq entry present but at 0 gain
    assert "370,0.0" in result or "370,-0.5" in result


def test_build_preprocess_filter():
    result = build_preprocess_filter(1.0, -2.5, "firequalizer=gain_entry='entry(100,0)'")
    assert "highpass=f=30:t=4" in result
    assert "volume=-2.50dB" in result
    assert "acompressor=threshold=-18dB" in result
    assert "ratio=3" in result
    assert "attack=10" in result
    assert "release=80" in result
```

- [ ] **Step 3: Запустить тесты**

```bash
uv run pytest tests/domain/render/test_eq.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/domain/render/eq.py tests/domain/render/test_eq.py
git commit -m "feat(render): add EQ curve builder — per-track + master firequalizer"
```

---

### Task 3: Graph — добавить pre-processing и мастер-шину

**Files:**
- Modify: `app/domain/render/graph.py`
- Modify: `app/domain/render/models.py` (добавить поля в RenderPlan)

**Interfaces:**
- Produces: `build_preprocess_filter(seg, features) -> str` — filterchain для одного трека
- Modifies: `build_filtergraph(plan)` — добавляет glue comp + master EQ + новые настройки лимитера

- [ ] **Step 1: Добавить поля в RenderPlan**

В `app/domain/render/models.py`, добавить в `RenderPlan`:

```python
    # Mastering
    hpf_cutoff_hz: float = 30.0
    per_track_eq_mid_cut_db: float = -1.0
    per_track_eq_bright_boost_db: float = 1.5
    pre_comp_threshold_db: float = -18.0
    pre_comp_ratio: float = 3.0
    pre_comp_attack_ms: float = 10.0
    pre_comp_release_ms: float = 80.0
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

- [ ] **Step 2: Добавить импорт в graph.py**

В начало файла `app/domain/render/graph.py` добавить:

```python
from app.domain.render.eq import build_master_eq
```

- [ ] **Step 3: Изменить финальную цепочку в build_filtergraph**

В `app/domain/render/graph.py`, строка 105-109, заменить `alimiter` и `dynaudnorm`:

```python
    parts.append(
        "".join(mixlabels) + f"amix=inputs={n}:normalize=0,"
        f"acompressor=threshold={plan.glue_comp_threshold_db}dB:"
        f"ratio={plan.glue_comp_ratio}:attack={plan.glue_comp_attack_ms}:"
        f"release={plan.glue_comp_release_ms}:knee=8:detection=rms:"
        f"link=average:makeup=1,"
        f"firequalizer=gain_entry='{build_master_eq(plan.master_eq_mud_cut_db, plan.master_eq_air_boost_db, plan.master_eq_sub_boost_db)}',"
        f"alimiter=level_in=1:level_out=1:limit={plan.limiter_ceiling}:"
        f"attack={plan.limiter_attack_ms}:release={plan.limiter_release_ms}:asc=1,"
        f"dynaudnorm=framelen=500:peak=0.95:maxgain={plan.dynaudnorm_maxgain}[mix]"
    )
```

- [ ] **Step 4: Тест на новый фильтрграф**

```python
# tests/domain/render/test_graph.py — дополнить существующий тест
def test_filtergraph_contains_mastering_chain():
    from app.domain.render.graph import build_filtergraph
    from app.domain.render.models import RenderPlan, TrackSegment
    # ... setup plan with 2 segments
    parts = build_filtergraph(plan)
    graph_str = ";".join(parts)
    assert "acompressor" in graph_str
    assert "firequalizer" in graph_str
    assert "attack=2" in graph_str or "attack=2.0" in graph_str
    assert "release=40" in graph_str or "release=40.0" in graph_str
```

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/domain/render/test_graph.py -v
```

- [ ] **Step 6: Коммит**

```bash
git add app/domain/render/graph.py app/domain/render/models.py tests/domain/render/test_graph.py
git commit -m "feat(render): add glue comp + master EQ + improved limiter to filtergraph"
```

---

### Task 4: Runner — двухпроходный рендер с pre-processing

**Files:**
- Modify: `app/audio/render/runner.py`

**Interfaces:**
- Produces: `build_preprocess_cmd(track_path, features, plan) -> list[str]` — FFmpeg команда для pre-processing одного трека
- Modifies: `build_ffmpeg_cmd(plan, out_path)` — добавляет `-q:a 0`

- [ ] **Step 1: Добавить build_preprocess_cmd**

```python
def build_preprocess_cmd(track_path: str, out_path: str, eq_filter: str) -> list[str]:
    """Pre-process one track: HPF + EQ + soft compression → temp WAV."""
    return [
        "ffmpeg",
        "-y",
        "-i", track_path,
        "-af",
        f"highpass=f=30:t=4,"
        f"{eq_filter},"
        f"acompressor=threshold=-18dB:ratio=3:attack=10:release=80:"
        f"knee=6:detection=rms:link=average:makeup=1",
        "-c:a", "pcm_s16le",
        out_path,
    ]


def build_ffmpeg_cmd(plan: RenderPlan, out_path: str) -> list[str]:
    """One ``-i`` per segment (in index order) + the filtergraph + mp3 out."""
    inputs: list[str] = []
    for seg in plan.segments:
        inputs += ["-i", seg.file_path]
    graph = ";".join(build_filtergraph(plan))
    return [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a", "0",
        out_path,
    ]
```

- [ ] **Step 2: Тест**

```python
# tests/audio/render/test_runner.py — дополнить
def test_build_preprocess_cmd():
    cmd = build_preprocess_cmd(
        "/tmp/test.mp3", "/tmp/test_pre.wav",
        "firequalizer=gain_entry='entry(100,0)'"
    )
    assert "highpass=f=30:t=4" in " ".join(cmd)
    assert "acompressor" in " ".join(cmd)
    assert "/tmp/test_pre.wav" in cmd


def test_ffmpeg_cmd_has_quality_flag():
    from app.audio.render.runner import build_ffmpeg_cmd
    from app.domain.render.models import RenderPlan, TrackSegment
    # setup plan
    cmd = build_ffmpeg_cmd(plan, "/tmp/out.mp3")
    assert "-q:a" in cmd
    assert "0" in cmd
```

- [ ] **Step 3: Запустить тесты**

```bash
uv run pytest tests/audio/render/test_runner.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/audio/render/runner.py tests/audio/render/test_runner.py
git commit -m "feat(render): add per-track pre-processing + q:a 0 MP3 quality"
```

---

### Task 5: Интеграция — timeline передаёт mastering-настройки в RenderPlan

**Files:**
- Modify: `app/domain/render/timeline.py`
- Modify: `app/handlers/render_mixdown.py`

**Interfaces:**
- Modifies: `build_render_plan(...)` — читает `RenderSettings` и передаёт mastering-поля в `RenderPlan`

- [ ] **Step 1: Изменить build_render_plan**

В `app/domain/render/timeline.py`, функция `build_render_plan()`, добавить в конструктор `RenderPlan(...)`:

```python
    from app.config.render import RenderSettings
    settings = RenderSettings()
    return RenderPlan(
        # ... existing fields ...
        hpf_cutoff_hz=settings.hpf_cutoff_hz,
        pre_comp_threshold_db=settings.pre_comp_threshold_db,
        pre_comp_ratio=settings.pre_comp_ratio,
        pre_comp_attack_ms=settings.pre_comp_attack_ms,
        pre_comp_release_ms=settings.pre_comp_release_ms,
        glue_comp_threshold_db=settings.glue_comp_threshold_db,
        glue_comp_ratio=settings.glue_comp_ratio,
        glue_comp_attack_ms=settings.glue_comp_attack_ms,
        glue_comp_release_ms=settings.glue_comp_release_ms,
        master_eq_air_boost_db=settings.master_eq_air_boost_db,
        master_eq_mud_cut_db=settings.master_eq_mud_cut_db,
        master_eq_sub_boost_db=settings.master_eq_sub_boost_db,
        limiter_attack_ms=settings.limiter_attack_ms,
        limiter_release_ms=settings.limiter_release_ms,
        dynaudnorm_maxgain=settings.dynaudnorm_maxgain,
    )
```

- [ ] **Step 2: Тест — таймлайн передаёт настройки**

```python
# tests/domain/render/test_timeline.py — дополнить
def test_timeline_passes_mastering_settings():
    plan = build_render_plan(...)
    assert plan.limiter_attack_ms == 2.0
    assert plan.dynaudnorm_maxgain == 2.0
    assert plan.glue_comp_ratio == 2.0
```

- [ ] **Step 3: Запустить тесты**

```bash
uv run pytest tests/domain/render/test_timeline.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/domain/render/timeline.py tests/domain/render/test_timeline.py
git commit -m "feat(render): wire mastering settings into RenderPlan from timeline"
```

---

### Task 6: End-to-end — полный прогон

- [ ] **Step 1: Все тесты**

```bash
uv run pytest tests/config/test_render_mastering.py tests/domain/render/ tests/audio/render/ -v
```

- [ ] **Step 2: Линт**

```bash
uv run ruff check app/config/render.py app/domain/render/ app/audio/render/
```

- [ ] **Step 3: Пере-рендерить сет #111 с новым пайплайном**

```bash
# Через MCP: dj_render_mixdown(version_id=166, refresh_grid=false)
```

- [ ] **Step 4: Финальный коммит**

```bash
git commit -m "test(render): end-to-end mastering pipeline verification"
```

---

### Зависимости

```
Task 1 (config) → Task 2 (eq) → Task 3 (graph) → Task 4 (runner) → Task 5 (timeline) → Task 6 (e2e)
```

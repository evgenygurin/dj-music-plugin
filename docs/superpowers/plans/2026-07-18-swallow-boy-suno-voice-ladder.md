# Swallow Boy Suno Voice Ladder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Проанализировать уже удачные short takes, перенацелить voice lock на `swallow boy` (`ed011c66-bd94-4bb2-bfd8-ec96a78ddc93`), собрать 10 коротких vocal variants под этот голос и подготовить Voice-ready shortlist для следующего verified Suno Voice шага.

**Architecture:** Три фазы. Фаза 1 — анализ референса и локальных short takes, формирование нового `swallow boy` vocal DNA. Фаза 2 — 10 short-form generation experiments на `chirp-fenix` с одной общей voice core и 10 контролируемыми twists. Фаза 3 — ranking, report и handoff-пакет для будущего `Suno Voice` create flow.

**Tech Stack:** Python 3.12, uv, pytest, ruff, existing Suno session adapter, local librosa analysis, markdown artifacts in `suno_out/rimjoba/` and `docs/superpowers/`.

## Global Constraints

- Все команды только через `uv`.
- Модель для generation phase: `chirp-fenix`.
- Формат тестовых генераций: short-form, target 15-35 s, no long intros.
- Никаких новых external dependencies.
- Если Suno session auth истёк, live steps начинают с refresh bearer.
- Сначала анализ + shortlist, потом verified Voice; не перепрыгивать сразу к voice.generate.
- Коммит после каждой task.

---

## File map

| Path | Responsibility |
|------|----------------|
| `docs/superpowers/reports/2026-07-18-swallow-boy-voice-analysis.md` | why-it-worked report |
| `app/domain/suno_voice/swallow_boy.py` | new voice DNA constants + 10 variant specs |
| `tests/domain/suno_voice/test_swallow_boy.py` | unit tests for new voice contract |
| `scripts/swallow_boy_variants.py` | live generation runner for 10 variants |
| `suno_out/rimjoba/swallow_boy/` | prompts, manifests, downloaded mp3, ranking |
| `docs/superpowers/specs/2026-07-18-swallow-boy-suno-voice-ladder-design.md` | approved spec |

---

### Task 1: Write analysis report from existing short takes

**Files:**
- Create: `docs/superpowers/reports/2026-07-18-swallow-boy-voice-analysis.md`
- Modify: `suno_out/rimjoba/gens_v20/LISTEN.md` only if adding notes is useful

**Interfaces:**
- Produces:
  - stable summary of previous successful voice cluster
  - recommended keep/discard rules for next 10 variants
  - top 5 promising takes from existing `gens_v20`

- [ ] **Step 1: Collect local metrics from existing takes**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
import json
import librosa
import numpy as np

rows = []
for f in sorted(Path("suno_out/rimjoba/gens_v20").glob("*.mp3")):
    y, sr = librosa.load(f, sr=22050, mono=True)
    f0, *_ = librosa.pyin(y, fmin=70, fmax=420, sr=sr)
    f0v = f0[~np.isnan(f0)]
    rows.append(
        {
            "file": f.name,
            "duration_s": round(len(y) / sr, 2),
            "f0_median": None if len(f0v) == 0 else round(float(np.median(f0v)), 1),
            "centroid_hz": round(float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()), 1),
            "rms": round(float(librosa.feature.rms(y=y).mean()), 4),
        }
    )
Path("/tmp/swallow_boy_existing_metrics.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("saved", len(rows))
PY
```

- [ ] **Step 2: Write report with concrete conclusions**

Report must include:

- which descriptors caused consistency
- measured cluster (`70-90 Hz`, `1300-2200 Hz`, dry/intimate)
- why short-form reduced drift
- what to preserve in `swallow boy` voice core
- shortlist of strongest existing takes by filename

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/reports/2026-07-18-swallow-boy-voice-analysis.md
git commit -m "docs(suno): analyze short-take voice stabilization"
```

---

### Task 2: Encode `swallow boy` voice contract in domain code

**Files:**
- Create: `app/domain/suno_voice/swallow_boy.py`
- Create: `tests/domain/suno_voice/test_swallow_boy.py`

**Interfaces:**
- Produces:
  - `SWALLOW_BOY_REFERENCE_CLIP_ID`
  - `SWALLOW_BOY_REFERENCE_URL`
  - `SWALLOW_BOY_VOICE_CORE`
  - `SWALLOW_BOY_NEGATIVE`
  - `SWALLOW_BOY_VARIANTS: tuple[VoiceVariant, ...]` length 10
  - `assemble_swallow_boy_style(variant_id: str) -> str`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Implement 10 variant specs exactly matching the design hypotheses**
- [ ] **Step 3: Verify with**

```bash
uv run pytest tests/domain/suno_voice/test_swallow_boy.py -v
uv run ruff check app/domain/suno_voice/swallow_boy.py tests/domain/suno_voice/test_swallow_boy.py
```

- [ ] **Step 4: Commit**

```bash
git add app/domain/suno_voice/swallow_boy.py tests/domain/suno_voice/test_swallow_boy.py
git commit -m "feat(suno): encode swallow boy voice contract"
```

---

### Task 3: Build live generation runner for 10 variants

**Files:**
- Create: `scripts/swallow_boy_variants.py`
- Create: `suno_out/rimjoba/swallow_boy/README.md`

**Interfaces:**
- Consumes: `SWALLOW_BOY_VOICE_CORE`, variant specs, existing Suno adapter
- Produces:
  - `suno_out/rimjoba/swallow_boy/SUMMARY.json`
  - `suno_out/rimjoba/swallow_boy/LISTEN.md`
  - downloaded mp3 files for all completed takes

- [ ] **Step 1: Implement auth preflight**
  - call account read
  - if 401: print exact refresh command and stop cleanly

- [ ] **Step 2: Generate 10 variants on `chirp-fenix`**
  - 2 outputs per create
  - short lyrics only
  - no long intro/outro

- [ ] **Step 3: Persist manifest + listen sheet**
  - variant id
  - Suno URLs
  - local paths
  - model key
  - durations

- [ ] **Step 4: Manual verification command**

```bash
uv run python scripts/swallow_boy_variants.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/swallow_boy_variants.py suno_out/rimjoba/swallow_boy
git commit -m "feat(suno): generate swallow boy short voice variants"
```

---

### Task 4: Rank the 10 variants and define Voice-ready shortlist

**Files:**
- Create: `suno_out/rimjoba/swallow_boy/RANKING.md`
- Create: `suno_out/rimjoba/swallow_boy/VOICE_HANDOFF.md`

**Interfaces:**
- Produces:
  - top 3 ranked takes
  - top 1 source candidate for future Voice
  - notes for window selection and verification prep

- [ ] **Step 1: Rank each variant on 4 axes**
  - timbre match to reference
  - diction clarity
  - emotional restraint / deadpan control
  - cross-genre portability

- [ ] **Step 2: Write `VOICE_HANDOFF.md`**
  - selected source candidate
  - why selected
  - ideal excerpt window (15-30 s)
  - future `voiceName`, `description`, `style`, `skillLevel`
  - post-Voice test prompts

- [ ] **Step 3: Commit**

```bash
git add suno_out/rimjoba/swallow_boy/RANKING.md suno_out/rimjoba/swallow_boy/VOICE_HANDOFF.md
git commit -m "docs(suno): shortlist swallow boy voice candidates"
```

---

### Task 5: Final verification and handoff

**Files:** none

- [ ] **Step 1: Run focused checks**

```bash
uv run pytest tests/domain/suno_voice/test_swallow_boy.py -v
uv run ruff check app/domain/suno_voice/swallow_boy.py tests/domain/suno_voice/test_swallow_boy.py scripts/swallow_boy_variants.py
```

- [ ] **Step 2: Confirm artifacts exist**

```bash
ls docs/superpowers/reports/2026-07-18-swallow-boy-voice-analysis.md
ls suno_out/rimjoba/swallow_boy/
```

- [ ] **Step 3: Deliver summary**
  - why the voice stabilized
  - which 10 variants were attempted
  - which take is the best future Voice seed

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| explain why consistency happened | Task 1 |
| use `ed011c66...` as voice target | Task 2 |
| 10 short variants | Task 3 |
| v5.5 Pro / `chirp-fenix` | Task 3 |
| future Voice-ready handoff | Task 4 |
| no immediate jump to verified Voice | Whole plan |

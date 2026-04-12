# Phase 2b: Domain Logic — Pure packages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Move `transition/`, `optimization/`, `export/`, `templates/` from `app/` to `src/dj_music/`. These are already pure (no DB, no HTTP, no MCP) — only internal imports change.

**Architecture:** Each package stays as-is structurally. Only import paths change from `app.X` to `dj_music.X`. Re-export shims in `app/`.

**Tech Stack:** No new deps — pure Python + numpy

---

### Task 1: Move transition/

**Files:**
- Create: `src/dj_music/transition/` (copy entire `app/transition/`)
- Modify: `app/transition/*.py` (re-export shims)

- [ ] **Step 1: Copy entire package**

```bash
cp -r app/transition src/dj_music/transition
```

- [ ] **Step 2: Update internal imports**

In all files under `src/dj_music/transition/`, replace:
- `from app.transition.` → `from dj_music.transition.`
- `from app.core.` → `from dj_music.core.`
- `from app.camelot.` → `from dj_music.core.camelot` (camelot moved to core in Phase 1)
- `from app.entities.audio.features` → `from dj_music.schemas.audio` (TrackFeatures moved in Phase 2a)
- `from app.config` → `from dj_music.core.config`

```bash
find src/dj_music/transition -name "*.py" -exec sed -i '' \
  -e 's/from app\.transition\./from dj_music.transition./g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  -e 's/from app\.camelot\.wheel/from dj_music.core.camelot/g' \
  -e 's/from app\.entities\.audio\.features/from dj_music.schemas.audio/g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  {} +
```

- [ ] **Step 3: Replace app/transition/ with re-export shims**

For each `.py` file in `app/transition/`:
```python
# app/transition/__init__.py
from dj_music.transition import *  # noqa: F401,F403
```

For submodules:
```python
# app/transition/scorer.py
from dj_music.transition.scorer import *  # noqa: F401,F403
```

- [ ] **Step 4: Run transition tests**

```bash
uv run pytest tests/test_transition/ -x -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move transition/ to dj_music.transition

Pure domain — no behavior change. Internal imports updated.
Re-export shims in app/transition/ for backward compat.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Move optimization/

Same pattern as Task 1.

- [ ] **Step 1: Copy**
```bash
cp -r app/optimization src/dj_music/optimization
```

- [ ] **Step 2: Update imports** — `app.optimization.` → `dj_music.optimization.`, plus core/config/transition refs.

- [ ] **Step 3: Shims in app/optimization/**

- [ ] **Step 4: Run tests**
```bash
uv run pytest tests/test_domain/ -x -q  # optimization tests live here
```

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "refactor: move optimization/ to dj_music.optimization

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Move export/

Same pattern.

- [ ] **Step 1: Copy**
```bash
cp -r app/export src/dj_music/export
```

- [ ] **Step 2: Update imports**

- [ ] **Step 3: Shims**

- [ ] **Step 4: Run tests**
```bash
uv run pytest -x -q
```

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "refactor: move export/ to dj_music.export

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Move templates/

Same pattern.

- [ ] **Step 1: Copy**
```bash
cp -r app/templates src/dj_music/templates
```

- [ ] **Step 2: Update imports**

- [ ] **Step 3: Shims**

- [ ] **Step 4: Run tests, commit**
```bash
uv run pytest -x -q && git add -A && git commit -m "refactor: move templates/ to dj_music.templates

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Move audio/ domain parts (analyzers, classification, dsp, quality)

**Important:** `audio/` has both domain (analyzers, dsp, classification) and infrastructure (pipeline, loader, temp_download, timeseries). This task moves the **entire** audio/ package since analyzers depend on pipeline context. Infrastructure separation will happen logically via import-linter contracts, not by splitting the package.

- [ ] **Step 1: Copy**
```bash
cp -r app/audio src/dj_music/audio
```

- [ ] **Step 2: Update imports in all audio files**

- [ ] **Step 3: Shims in app/audio/**

- [ ] **Step 4: Run audio tests**
```bash
uv run pytest tests/test_audio/ -x -q
```

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "refactor: move audio/ to dj_music.audio

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Final Phase 2b verification

- [ ] **Step 1: Verify pure domain packages exist**

```bash
ls -d src/dj_music/transition src/dj_music/optimization src/dj_music/export src/dj_music/templates src/dj_music/audio
```

- [ ] **Step 2: Verify no forbidden imports in pure packages**

```bash
uv run lint-imports
```

- [ ] **Step 3: Full check**

```bash
make check
```

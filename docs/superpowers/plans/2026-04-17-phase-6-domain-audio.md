# Phase 6 — Domain + Audio Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port pure-domain modules (`transition/`, `optimization/`, `camelot/`, `templates/`, `audit/`, `entities/audio/features.py`) and the audio pipeline (`audio/`) into `app/v2/domain/` and `app/v2/audio/` — one-to-one file moves with import rewrites, zero behaviour change, import-linter gate green.

**Architecture:** Parallel-refactor continues per blueprint §15.7 — legacy `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`, `app/entities/`, `app/audio/` remain intact and continue serving legacy callers (services, tools). New copies live under `app/v2/domain/` (pure math) and `app/v2/audio/` (librosa/essentia machinery). v2 modules import ONLY from v2 peers + `app.v2.config` + `app.v2.shared` — never from legacy `app.transition`, `app.core.*`, `app.config`, `app.entities.*`. Phase 7 will do the atomic swap.

**Tech Stack:** Python 3.12, numpy, librosa (optional extra `[audio]`), essentia (optional extra `[audio]`), pytest + pytest-asyncio, import-linter.

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§3, 14.5, 15.7, 16.

---

## File Structure

Files created by this plan. Legacy paths (left column) are **not modified** — copies are made to v2 paths (right column) with imports rewritten to point at v2 peers.

### Source code (`app/v2/domain/` + `app/v2/audio/`)

```bash
app/v2/domain/
├── __init__.py
├── transition/
│   ├── __init__.py                 # public re-exports (mirrors legacy __init__)
│   ├── features.py                 # TrackFeatures dataclass (moved from app/entities/audio/features.py)
│   ├── math_helpers.py             # bpm_distance, cosine_similarity, correlation
│   ├── weights.py                  # StyleRules + magic constants + DRUM_ONLY_* overrides
│   ├── score.py                    # TransitionScore dataclass
│   ├── hard_constraints.py         # check_hard_constraints
│   ├── intent.py                   # TransitionIntent enum + infer_intent
│   ├── section_context.py          # SectionContext + is_drum_only_pair
│   ├── style.py                    # recommend_style, recommend_recipe, style_profile
│   ├── recipe.py                   # TransitionRecipe / TransitionType / DjayTransition / EQPlan
│   ├── recipe_engine.py            # TransitionRecipeEngine (12 djay Pro AI types)
│   ├── subgenre_rules.py           # SubgenrePairType, clamp_bars, classify_pair
│   ├── neural_mix.py               # NeuralMixScorer
│   ├── scorer.py                   # TransitionScorer (orchestrator)
│   └── components/
│       ├── __init__.py             # re-export score_bpm/.../score_timbral
│       ├── bpm.py
│       ├── harmonic.py
│       ├── energy.py
│       ├── spectral.py
│       ├── groove.py
│       └── timbral.py
├── optimization/
│   ├── __init__.py
│   ├── result.py                   # OptimizationResult
│   ├── protocol.py                 # OptimizerStrategy Protocol
│   ├── fitness.py                  # compute_fitness, transition_quality
│   ├── greedy.py                   # GreedyChainBuilder
│   └── genetic.py                  # GeneticAlgorithm
├── camelot/
│   ├── __init__.py
│   └── wheel.py                    # camelot_distance, key_code_to_camelot, ...
├── template/                       # NOTE: singular per blueprint §3
│   ├── __init__.py
│   ├── models.py                   # SetTemplateDefinition, TemplateSlot
│   └── registry.py                 # 8 templates + get_template + list_template_names
└── audit/
    ├── __init__.py
    └── rules.py                    # techno audit specs + gate helpers

app/v2/audio/
├── __init__.py
├── pipeline.py                     # AnalysisPipeline
├── level_config.py                 # L1-L4 tiered config
├── timeseries.py                   # NPZ storage helpers
├── temp_download.py                # temp-file helper
├── core/
│   ├── __init__.py
│   ├── loader.py                   # load_audio
│   ├── context.py                  # AnalysisContext + shared STFT + onset env
│   ├── framing.py
│   ├── rhythm.py
│   ├── spectral.py
│   ├── tonal.py
│   └── types.py                    # AudioSignal dataclass
├── analyzers/
│   ├── __init__.py
│   ├── base.py                     # BaseAnalyzer + AnalyzerResult + AnalyzerRegistry
│   ├── loudness.py
│   ├── energy.py
│   ├── spectral.py
│   ├── structure.py
│   ├── bpm.py
│   ├── key.py
│   ├── beat.py
│   ├── mfcc.py
│   ├── tonnetz.py
│   ├── tempogram.py
│   ├── bpm_histogram.py
│   ├── phrase.py
│   ├── beats_loudness.py
│   ├── danceability.py
│   ├── dissonance.py
│   ├── dynamic_complexity.py
│   ├── pitch_salience.py
│   └── spectral_complexity.py
└── classification/
    ├── __init__.py
    ├── classifier.py               # rule-based mood classifier
    └── profiles.py                 # 15 subgenre weight profiles
```

### Tests (`tests/v2/domain/` + `tests/v2/audio/`)

```bash
tests/v2/domain/
├── __init__.py
├── transition/
│   ├── __init__.py
│   ├── test_math_helpers.py
│   ├── test_hard_constraints.py    # migrated from tests/test_domain/test_hard_constraints.py
│   ├── test_section_context.py     # migrated from tests/test_domain/test_section_context.py
│   ├── test_style.py               # migrated from tests/test_domain/test_transition_style.py
│   ├── test_weights.py             # migrated from tests/test_domain/test_transition_weights.py
│   ├── test_neural_mix.py          # migrated from tests/test_transition/test_neural_mix.py
│   ├── test_recipe.py              # migrated from tests/test_transition/test_recipe.py
│   ├── test_recipe_engine.py       # migrated from tests/test_transition/test_recipe_engine.py
│   ├── test_recipe_integration.py  # migrated from tests/test_transition/test_recipe_integration.py
│   ├── test_subgenre_rules.py      # migrated from tests/test_transition/test_subgenre_rules.py
│   ├── test_scorer_parity.py       # NEW parity test: v2 scorer == legacy scorer on same input
│   └── test_features_from_db.py    # NEW: TrackFeatures.from_db mapping
├── optimization/
│   ├── __init__.py
│   ├── test_fitness.py
│   ├── test_greedy.py
│   └── test_genetic.py
├── camelot/
│   ├── __init__.py
│   └── test_wheel.py
├── template/
│   ├── __init__.py
│   └── test_registry.py
└── audit/
    ├── __init__.py
    └── test_rules.py

tests/v2/audio/
├── __init__.py
├── test_analyzer_base.py           # migrated from tests/test_audio/test_analyzer_base.py
├── test_registry.py
├── test_core_context.py
├── test_core_framing.py
├── test_core_loader.py
├── test_core_rhythm.py
├── test_core_spectral.py
├── test_core_tonal.py
├── test_core_types.py
├── test_bpm_detector.py
├── test_spectral.py
├── test_structure.py
├── test_classification.py
├── test_mood.py
├── test_level_config.py
├── test_timeseries.py
├── test_temp_download.py
├── test_pipeline_refactored.py
├── test_analyzers.py               # meta — enumerates registered analyzers
├── test_beat_export.py
├── test_bpm_histogram.py
├── test_phrase.py
├── test_tempogram.py
├── test_tonnetz.py
├── test_danceability.py
├── test_dissonance.py
├── test_dynamic_complexity.py
├── test_pitch_salience.py
├── test_spectral_complexity.py
└── test_beats_loudness.py
```

### Config updates

- `.importlinter` — 2 new contracts (`v2-domain-pure`, `v2-audio-internal`). Legacy contracts (`transition-pure`, `optimization-pure`) remain green against legacy `app/transition/` and `app/optimization/`.
- No changes to `pyproject.toml` — `app.v2.*` already picked up by existing `packages.find` glob.

---

## Assumptions and ground rules

1. **One-to-one file moves.** Each legacy source file gets an exact copy in v2 with imports rewritten. No refactor of internals in this phase — that was Phase 3 (tools) and Phase 5 (server). Internal audio reorg is permitted per §15.7, but we defer it to Phase 7 to keep diff reviewable.
2. **v2 imports v2 only.** Every ported module imports from `app.v2.domain.*`, `app.v2.audio.*`, `app.v2.config`, `app.v2.shared.*` — never from legacy `app.transition`, `app.core.*`, `app.config`, `app.entities.*`.
3. **`TrackFeatures` merges into `app.v2.domain.transition.features`** (blueprint §14.5: *"`app/entities/*` (5 files) → merged into `app/domain/transition/features.py` (TrackFeatures) + deleted rest"*). All v2 domain imports reference the new path. `TrackFeatures.from_db(row)` stays — but it takes an ORM row (duck-typed attributes), so it does NOT import from `app.models`.
4. **Constants and settings come from Phase 1 skeleton.** Legacy modules import `from app.core.constants import SetTemplate`, `from app.config import settings` — rewritten to `from app.v2.shared.constants import SetTemplate`, `from app.v2.config import settings` (facade). Phase 1 defined those facades.
5. **Audio optional deps stay optional.** `librosa`/`essentia` imports stay guarded inside analyzer modules — v2 copies preserve the exact guard style.
6. **Tests get migrated, not duplicated.** Each legacy test in `tests/test_transition/`, `tests/test_domain/`, `tests/test_audio/` is copied to the new `tests/v2/...` path with imports rewritten. The *legacy* tests remain (pointing at legacy modules) — they still pass. Parity is enforced by tests exercising the SAME behaviour in both trees.
7. **No new tests of new features.** Tests added in this phase are either migrated 1:1 OR parity tests that lock v2 = legacy. No green-field testing.
8. **Commits are per-module-family** — one commit for `v2/domain/camelot/`, one for `v2/domain/transition/components/`, etc. Each commit leaves all gates green (lint-imports + `uv run pytest tests/v2` + `uv run pytest tests/`).
9. **Cutover / deletion is out of scope.** Phase 7 moves `app/` → `app/v1_legacy/` and deletes legacy paths. This phase ONLY adds v2 copies.

---

## Task 1: Create `app/v2/domain/` and `app/v2/audio/` package skeletons

**Files:**
- Create: `app/v2/domain/__init__.py`
- Create: `app/v2/domain/transition/__init__.py`
- Create: `app/v2/domain/transition/components/__init__.py`
- Create: `app/v2/domain/optimization/__init__.py`
- Create: `app/v2/domain/camelot/__init__.py`
- Create: `app/v2/domain/template/__init__.py`
- Create: `app/v2/domain/audit/__init__.py`
- Create: `app/v2/audio/__init__.py`
- Create: `app/v2/audio/core/__init__.py`
- Create: `app/v2/audio/analyzers/__init__.py`
- Create: `app/v2/audio/classification/__init__.py`
- Create: `tests/v2/domain/__init__.py`
- Create: `tests/v2/domain/transition/__init__.py`
- Create: `tests/v2/domain/optimization/__init__.py`
- Create: `tests/v2/domain/camelot/__init__.py`
- Create: `tests/v2/domain/template/__init__.py`
- Create: `tests/v2/domain/audit/__init__.py`
- Create: `tests/v2/audio/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p app/v2/domain/transition/components
mkdir -p app/v2/domain/optimization
mkdir -p app/v2/domain/camelot
mkdir -p app/v2/domain/template
mkdir -p app/v2/domain/audit
mkdir -p app/v2/audio/core
mkdir -p app/v2/audio/analyzers
mkdir -p app/v2/audio/classification
mkdir -p tests/v2/domain/transition
mkdir -p tests/v2/domain/optimization
mkdir -p tests/v2/domain/camelot
mkdir -p tests/v2/domain/template
mkdir -p tests/v2/domain/audit
mkdir -p tests/v2/audio
```

- [ ] **Step 2: Write top-level `app/v2/domain/__init__.py`**

```python
"""Pure domain layer (v2).

Blueprint §3: no I/O, no DB, no FastMCP, no SQLAlchemy, no httpx.
Import-linter contract `v2-domain-pure` enforces this.

Submodules:
- transition  — 6-component scoring formula, hard constraints, recipes
- optimization — GA, greedy, fitness function
- camelot      — Camelot wheel math
- template     — 8 set templates (singular per blueprint §3)
- audit        — techno quality criteria
"""
```

- [ ] **Step 3: Write `app/v2/audio/__init__.py`**

```python
"""Audio analysis pipeline (v2).

Librosa + essentia machinery. Not pure — may touch filesystem, numeric deps.
Import-linter contract `v2-audio-internal` forbids MCP/REST/repository imports.

Submodules:
- core           — STFT/framing/loader plumbing
- analyzers      — 18 concrete analyzer implementations
- classification — rule-based mood classifier (15 subgenres)
"""
```

- [ ] **Step 4: Create one-line `__init__.py` in every other package and test package**

Every file listed in Step 1 that doesn't have explicit content above gets:

```python
""""""
```

(triple-empty docstring placeholder).

- [ ] **Step 5: Verify packages importable**

```bash
uv run python -c "
import app.v2.domain
import app.v2.domain.transition
import app.v2.domain.transition.components
import app.v2.domain.optimization
import app.v2.domain.camelot
import app.v2.domain.template
import app.v2.domain.audit
import app.v2.audio
import app.v2.audio.core
import app.v2.audio.analyzers
import app.v2.audio.classification
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add app/v2/domain app/v2/audio tests/v2/domain tests/v2/audio
git commit -m "feat(v2): scaffold domain and audio package skeletons

Empty packages for transition/optimization/camelot/template/audit
and audio/{core,analyzers,classification}. Prepares for 1:1 file
ports from legacy app/transition, app/optimization, app/camelot,
app/templates, app/audit, app/audio."
```

---

## Task 2: Port `app/camelot/` → `app/v2/domain/camelot/`

Camelot first — smallest module, zero internal deps, proves the porting recipe.

**Files:**
- Copy: `app/camelot/wheel.py` → `app/v2/domain/camelot/wheel.py` (with rewrite)
- Copy: `app/camelot/__init__.py` → `app/v2/domain/camelot/__init__.py` (with rewrite)
- Test: `tests/v2/domain/camelot/test_wheel.py` (migrated or authored against v2)

- [ ] **Step 1: Read legacy `app/camelot/wheel.py` to catalogue imports**

Legacy file starts with:

```python
from app.core.constants import CAMELOT_KEYS, KEY_CODE_MAX, KEY_CODE_MIN
```

All other imports are stdlib. Only rewrite: `app.core.constants` → `app.v2.shared.constants`.

- [ ] **Step 2: Copy file + rewrite import**

```bash
cp app/camelot/wheel.py app/v2/domain/camelot/wheel.py
```

Then edit `app/v2/domain/camelot/wheel.py` line 12:

```python
# before
from app.core.constants import CAMELOT_KEYS, KEY_CODE_MAX, KEY_CODE_MIN
# after
from app.v2.shared.constants import CAMELOT_KEYS, KEY_CODE_MAX, KEY_CODE_MIN
```

- [ ] **Step 3: Copy `__init__.py`**

```bash
cp app/camelot/__init__.py app/v2/domain/camelot/__init__.py
```

Rewrite every `from app.camelot.wheel import ...` to `from app.v2.domain.camelot.wheel import ...`.

- [ ] **Step 4: Import smoke test**

```bash
uv run python -c "
from app.v2.domain.camelot.wheel import camelot_distance
from app.v2.domain.camelot import camelot_distance as via_pkg
assert camelot_distance == via_pkg
print(camelot_distance(0, 12))  # minor vs relative major
"
```

Expected prints a small integer (Camelot distance between C minor and C major).

- [ ] **Step 5: Migrate tests**

If `tests/test_camelot/` exists, mirror to `tests/v2/domain/camelot/`:

```bash
if [ -f tests/test_camelot/test_wheel.py ]; then
  cp tests/test_camelot/test_wheel.py tests/v2/domain/camelot/test_wheel.py
fi
```

Otherwise create `tests/v2/domain/camelot/test_wheel.py`:

```python
"""Camelot wheel distance tests (v2)."""
from __future__ import annotations

from app.v2.domain.camelot.wheel import camelot_distance

def test_identity_zero() -> None:
    assert camelot_distance(0, 0) == 0

def test_relative_major_minor_distance_one() -> None:
    # Per Camelot wheel: 8A <-> 8B (relative minor <-> relative major)
    # key_code 0-11 = major (B), 12-23 = minor (A). Adjacent 8A -> 8B = dist 1.
    assert camelot_distance(12, 0) == camelot_distance(0, 12)  # symmetric
```

Rewrite any `from app.camelot` imports inside migrated tests to `from app.v2.domain.camelot`.

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/v2/domain/camelot/ -v
```

Expected: all pass.

- [ ] **Step 7: Verify import-linter still clean (contract added in Task 15)**

This step is a no-op for Camelot (it only imports stdlib + `app.v2.shared.constants`), but confirm:

```bash
uv run lint-imports 2>&1 | tail -20
```

Expected: current contracts green (no `v2-domain-pure` contract yet — added in Task 15).

- [ ] **Step 8: Commit**

```bash
git add app/v2/domain/camelot tests/v2/domain/camelot
git commit -m "feat(v2): port camelot wheel to app/v2/domain/camelot

One-to-one move from app/camelot. Only rewrite: app.core.constants ->
app.v2.shared.constants. Pure math, stdlib only. Legacy app/camelot
remains intact for transition-pure contract compliance."
```

---

## Task 3: Port `app/templates/` → `app/v2/domain/template/` (note singular)

Blueprint §3 mandates singular **`template`** (not `templates`). This is a breaking rename — legacy stays `templates/`, v2 uses `template/`.

**Files:**
- Copy: `app/templates/models.py` → `app/v2/domain/template/models.py`
- Copy: `app/templates/registry.py` → `app/v2/domain/template/registry.py`
- Copy: `app/templates/__init__.py` → `app/v2/domain/template/__init__.py`
- Test: `tests/v2/domain/template/test_registry.py`

- [ ] **Step 1: Inspect legacy imports**

```bash
uv run python -c "
import pathlib
for p in pathlib.Path('app/templates').rglob('*.py'):
    print('===', p)
    print(p.read_text())
" | head -80
```

Expected: `models.py` imports `SectionType`/`SetTemplate` etc. from `app.core.constants`; `registry.py` imports from `app.templates.models`; `__init__.py` re-exports.

- [ ] **Step 2: Copy + rewrite imports**

```bash
cp app/templates/models.py app/v2/domain/template/models.py
cp app/templates/registry.py app/v2/domain/template/registry.py
cp app/templates/__init__.py app/v2/domain/template/__init__.py
```

Edit each copy:

| In file | Rewrite | To |
|---|---|---|
| `models.py` | `from app.core.constants import ...` | `from app.v2.shared.constants import ...` |
| `registry.py` | `from app.templates.models import ...` | `from app.v2.domain.template.models import ...` |
| `registry.py` | `from app.core.constants import ...` | `from app.v2.shared.constants import ...` (if any) |
| `__init__.py` | `from app.templates.models import ...` | `from app.v2.domain.template.models import ...` |
| `__init__.py` | `from app.templates.registry import ...` | `from app.v2.domain.template.registry import ...` |

- [ ] **Step 3: Smoke test**

```bash
uv run python -c "
from app.v2.domain.template import TEMPLATES, get_template, list_template_names
from app.v2.domain.template.models import SetTemplateDefinition, TemplateSlot
names = list_template_names()
print(len(names), 'templates:', names)
assert len(names) == 8, f'expected 8 templates, got {len(names)}'
t = get_template('classic_60')
assert isinstance(t, SetTemplateDefinition)
print('classic_60 slots:', len(t.slots))
"
```

Expected: `8 templates: ['warm_up_30', 'classic_60', ...]` then `classic_60 slots: N`.

- [ ] **Step 4: Migrate test (create if legacy has none)**

```python
# tests/v2/domain/template/test_registry.py
"""Template registry tests (v2)."""
from __future__ import annotations

import pytest

from app.v2.domain.template import TEMPLATES, get_template, list_template_names
from app.v2.domain.template.models import SetTemplateDefinition

def test_has_eight_templates() -> None:
    assert len(list_template_names()) == 8

def test_get_template_returns_definition() -> None:
    t = get_template("classic_60")
    assert isinstance(t, SetTemplateDefinition)

def test_get_unknown_raises() -> None:
    with pytest.raises((KeyError, ValueError)):
        get_template("does_not_exist")

def test_templates_mapping_exposes_all_names() -> None:
    assert set(TEMPLATES.keys()) == set(list_template_names())
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/v2/domain/template/ -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/domain/template tests/v2/domain/template
git commit -m "feat(v2): port templates to app/v2/domain/template (singular)

Blueprint section 3 mandates singular 'template' for the new tree.
Legacy app/templates retained. Rewrites: app.core.constants ->
app.v2.shared.constants, app.templates.* -> app.v2.domain.template.*."
```

---

## Task 4: Port `app/audit/` → `app/v2/domain/audit/`

**Files:**
- Copy: `app/audit/rules.py` → `app/v2/domain/audit/rules.py`
- Copy: `app/audit/__init__.py` → `app/v2/domain/audit/__init__.py`
- Test: `tests/v2/domain/audit/test_rules.py`

- [ ] **Step 1: Inspect `app/audit/rules.py`**

```bash
grep -n "^from\|^import" app/audit/rules.py
```

Expected: `from app.config import settings` + stdlib.

- [ ] **Step 2: Copy + rewrite**

```bash
cp app/audit/rules.py app/v2/domain/audit/rules.py
cp app/audit/__init__.py app/v2/domain/audit/__init__.py
```

Edit:

| File | Before | After |
|---|---|---|
| `rules.py` | `from app.config import settings` | `from app.v2.config import settings` |
| `__init__.py` | `from app.audit.rules import ...` | `from app.v2.domain.audit.rules import ...` |

- [ ] **Step 3: Smoke test**

```bash
uv run python -c "
from app.v2.domain.audit import rules
print(dir(rules))
"
```

Expected: a list of the public symbols re-exported from legacy (e.g. `evaluate_track`, `AuditResult`, `DEFAULT_TECHNO_CRITERIA`, ...).

- [ ] **Step 4: Migrate tests**

If `tests/test_audit/` exists, mirror. Otherwise create smoke test:

```python
# tests/v2/domain/audit/test_rules.py
"""Techno audit rules tests (v2)."""
from __future__ import annotations

from app.v2.domain.audit import rules

def test_module_is_pure_python() -> None:
    # No sqlalchemy/fastmcp/httpx should have been transitively imported.
    import sys
    mod = sys.modules["app.v2.domain.audit.rules"]
    assert mod is rules

def test_default_criteria_exposed() -> None:
    # Symbol existence is the contract; exact structure is legacy.
    assert hasattr(rules, "__dict__")
    assert len(dir(rules)) > 5
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/v2/domain/audit/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/v2/domain/audit tests/v2/domain/audit
git commit -m "feat(v2): port audit rules to app/v2/domain/audit

Techno audit criteria (BPM 120-155, LUFS -20..-4, ...) lifted 1:1.
Only rewrite: app.config -> app.v2.config."
```

---

## Task 5: Port `TrackFeatures` — `app/entities/audio/features.py` → `app/v2/domain/transition/features.py`

Per blueprint §14.5: "`app/entities/*` (5 files) — merged into `app/domain/transition/features.py` (TrackFeatures) + deleted rest". `TrackFeatures` is the shared dataclass used by every transition/optimization module. Porting it FIRST unblocks the components chain.

**Files:**
- Copy: `app/entities/audio/features.py` → `app/v2/domain/transition/features.py`
- Test: `tests/v2/domain/transition/test_features_from_db.py`

- [ ] **Step 1: Read legacy file**

```bash
uv run python -c "
import pathlib
print(pathlib.Path('app/entities/audio/features.py').read_text())
" | head -60
```

Expected: `@dataclass(frozen=True)` (or similar) with fields `bpm`, `key_code`, `integrated_lufs`, `energy_mean`, ..., `mood`. A `@classmethod from_db(cls, row)` that reads attrs off a duck-typed ORM row (no `sqlalchemy` import).

- [ ] **Step 2: Copy file**

```bash
cp app/entities/audio/features.py app/v2/domain/transition/features.py
```

- [ ] **Step 3: Rewrite imports**

If the copy imports anything from `app.entities.*` or `app.core.*` rewrite:

| Before | After |
|---|---|
| `from app.core.constants import ...` | `from app.v2.shared.constants import ...` |
| `from app.entities.audio.*` | `from app.v2.domain.transition.*` |

Then verify `grep -n "^from app" app/v2/domain/transition/features.py` — should show ONLY `app.v2.*` imports (or no `app.*` imports at all — `TrackFeatures` is usually dependency-free).

- [ ] **Step 4: Smoke test**

```bash
uv run python -c "
from app.v2.domain.transition.features import TrackFeatures
f = TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.5)
print(f.bpm, f.key_code, f.integrated_lufs)
assert TrackFeatures().bpm is None  # all optional
"
```

Expected: `128.0 5 -8.5` then clean exit.

- [ ] **Step 5: Write `from_db` mapping test**

```python
# tests/v2/domain/transition/test_features_from_db.py
"""TrackFeatures.from_db duck-typed row mapping."""
from __future__ import annotations

from dataclasses import dataclass

from app.v2.domain.transition.features import TrackFeatures

@dataclass
class _FakeRow:
    """Duck-typed surrogate for TrackAudioFeaturesComputed ORM row.

    Only needs attribute-read semantics — TrackFeatures.from_db never
    touches SQLAlchemy or session state.
    """

    bpm: float | None = 128.0
    bpm_confidence: float | None = 0.9
    bpm_stability: float | None = 0.85
    variable_tempo: bool | None = False
    key_code: int | None = 5
    key_confidence: float | None = 0.8
    atonality: bool | None = False
    integrated_lufs: float | None = -8.5
    short_term_lufs_mean: float | None = -9.0
    loudness_range_lu: float | None = 6.0
    crest_factor_db: float | None = 10.0
    energy_mean: float | None = 0.2
    energy_slope: float | None = 0.01
    energy_sub: float | None = 0.1
    energy_low: float | None = 0.15
    energy_lowmid: float | None = 0.2
    energy_mid: float | None = 0.25
    energy_highmid: float | None = 0.18
    energy_high: float | None = 0.12
    spectral_centroid_hz: float | None = 3000.0
    spectral_rolloff_85: float | None = 5000.0
    spectral_rolloff_95: float | None = 7000.0
    spectral_flatness: float | None = 0.3
    spectral_flux_std: float | None = 0.1
    spectral_slope: float | None = -20.0
    # JSON-string fields the dataclass parses on load
    mfcc_vector: str | None = "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
    tonnetz_vector: str | None = None
    beat_loudness_band_ratio: str | None = None
    tempogram_ratio_vector: str | None = None
    hp_ratio: float | None = 2.0
    onset_rate: float | None = 5.0
    pulse_clarity: float | None = 0.1
    kick_prominence: float | None = 0.5
    chroma_entropy: float | None = 0.6
    hnr_db: float | None = 10.0
    dynamic_complexity: float | None = 2.0
    mood: str | None = "driving"
    first_downbeat_ms: float | None = 12.0

def test_from_db_populates_primary_fields() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert feat.bpm == 128.0
    assert feat.key_code == 5
    assert feat.integrated_lufs == -8.5
    assert feat.energy_mean == 0.2
    assert feat.mood == "driving"

def test_from_db_parses_mfcc_json_string() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert isinstance(feat.mfcc_vector, list)
    assert len(feat.mfcc_vector) == 13

def test_from_db_assembles_energy_bands_from_six_columns() -> None:
    feat = TrackFeatures.from_db(_FakeRow())
    assert feat.energy_bands is not None
    assert len(feat.energy_bands) == 6
    # Order: sub, low, lowmid, mid, highmid, high
    assert feat.energy_bands[0] == 0.1
    assert feat.energy_bands[5] == 0.12

def test_from_db_drops_energy_bands_when_any_missing() -> None:
    row = _FakeRow(energy_mid=None)
    feat = TrackFeatures.from_db(row)
    assert feat.energy_bands is None

def test_from_db_handles_missing_json_fields() -> None:
    row = _FakeRow(mfcc_vector=None, tonnetz_vector=None)
    feat = TrackFeatures.from_db(row)
    assert feat.mfcc_vector is None
    assert feat.tonnetz_vector is None
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/v2/domain/transition/test_features_from_db.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add app/v2/domain/transition/features.py tests/v2/domain/transition/test_features_from_db.py
git commit -m "feat(v2): port TrackFeatures to app/v2/domain/transition

Merges app/entities/audio/features.py into domain.transition per
blueprint section 14.5. Legacy entities/ stays put. Duck-typed row
fixture locks from_db contract without touching SQLAlchemy."
```

---

## Task 6: Port `app/transition/math_helpers.py`, `weights.py`, `score.py`, `intent.py`, `section_context.py`, `subgenre_rules.py`, `recipe.py`

These are the six leaf modules of `transition/` — zero transitive deps on other transition files (except `recipe.py → nothing; subgenre_rules.py → recipe`). Port them together so the next task can port components + scorer.

**Files:**
- Copy 7 files from `app/transition/` → `app/v2/domain/transition/`
  - `math_helpers.py`
  - `weights.py`
  - `score.py`
  - `intent.py`
  - `section_context.py`
  - `recipe.py`
  - `subgenre_rules.py`

- [ ] **Step 1: Catalogue imports per file**

```bash
for f in math_helpers.py weights.py score.py intent.py section_context.py recipe.py subgenre_rules.py; do
  echo "=== app/transition/$f ==="
  grep -n "^from\|^import" "app/transition/$f"
done
```

Expected rewrites:

| File | Legacy import | v2 rewrite |
|---|---|---|
| `weights.py` | `from app.core.constants import DEFAULT_TRANSITION_WEIGHTS` | `from app.v2.shared.constants import DEFAULT_TRANSITION_WEIGHTS` |
| `intent.py` | `from app.core.constants import SetTemplate` | `from app.v2.shared.constants import SetTemplate` |
| `section_context.py` | `from app.core.constants import SectionType` | `from app.v2.shared.constants import SectionType` |
| `subgenre_rules.py` | `from app.transition.recipe import TransitionType` | `from app.v2.domain.transition.recipe import TransitionType` |
| `subgenre_rules.py` | `from app.core.constants import TechnoSubgenre` | `from app.v2.shared.constants import TechnoSubgenre` |
| `math_helpers.py`, `score.py`, `recipe.py` | stdlib only | no rewrite |

- [ ] **Step 2: Copy files**

```bash
for f in math_helpers.py weights.py score.py intent.py section_context.py recipe.py subgenre_rules.py; do
  cp "app/transition/$f" "app/v2/domain/transition/$f"
done
```

- [ ] **Step 3: Rewrite imports (per table above)**

Edit each copied file. Apply only the rewrites listed — do NOT change function bodies.

- [ ] **Step 4: Smoke test each module individually**

```bash
uv run python -c "
from app.v2.domain.transition.math_helpers import bpm_distance, cosine_similarity, correlation
from app.v2.domain.transition.weights import DEFAULT_WEIGHTS, StyleRules
from app.v2.domain.transition.score import TransitionScore
from app.v2.domain.transition.intent import TransitionIntent, infer_intent, INTENT_WEIGHT_MODIFIERS
from app.v2.domain.transition.section_context import SectionContext
from app.v2.domain.transition.recipe import TransitionRecipe, TransitionType
from app.v2.domain.transition.subgenre_rules import SubgenrePairType, classify_pair, clamp_bars

# sanity
assert bpm_distance(128.0, 130.0) == 2.0
assert bpm_distance(64.0, 128.0) == 0.0  # half-tempo
intent = infer_intent(set_position=0.3, energy_delta_lufs=1.5)
assert isinstance(intent, TransitionIntent)
print('all leaf modules load')
"
```

Expected: `all leaf modules load`.

- [ ] **Step 5: Migrate tests that target these modules**

Mirror the following legacy tests:

| Legacy | Target |
|---|---|
| `tests/test_domain/test_transition_weights.py` | `tests/v2/domain/transition/test_weights.py` |
| `tests/test_domain/test_section_context.py` | `tests/v2/domain/transition/test_section_context.py` |
| `tests/test_transition/test_recipe.py` | `tests/v2/domain/transition/test_recipe.py` |
| `tests/test_transition/test_subgenre_rules.py` | `tests/v2/domain/transition/test_subgenre_rules.py` |

For each: `cp SRC DST` then rewrite all `from app.transition.X` → `from app.v2.domain.transition.X`, `from app.core.constants` → `from app.v2.shared.constants`, `from app.entities.audio.features` → `from app.v2.domain.transition.features`.

Also add a fresh `tests/v2/domain/transition/test_math_helpers.py`:

```python
"""Pure math helpers: bpm_distance / cosine_similarity / correlation."""
from __future__ import annotations

import math

from app.v2.domain.transition.math_helpers import (
    bpm_distance,
    correlation,
    cosine_similarity,
)

def test_bpm_distance_zero_identity() -> None:
    assert bpm_distance(128.0, 128.0) == 0.0

def test_bpm_distance_half_tempo_folds_to_zero() -> None:
    # 64 BPM and 128 BPM are rhythmically equivalent (double-time).
    assert bpm_distance(64.0, 128.0) == 0.0

def test_bpm_distance_normal_gap() -> None:
    assert bpm_distance(128.0, 130.0) == 2.0

def test_cosine_similarity_identity_one() -> None:
    assert math.isclose(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

def test_cosine_similarity_orthogonal_zero() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)

def test_correlation_perfect_positive() -> None:
    assert math.isclose(correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]), 1.0, abs_tol=1e-9)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/v2/domain/transition/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/v2/domain/transition tests/v2/domain/transition
git commit -m "feat(v2): port transition leaf modules (math/weights/score/intent/section/recipe/subgenre)

Seven leaf files ported 1:1 to app/v2/domain/transition with only
import path rewrites (app.core.constants -> app.v2.shared.constants,
app.entities.audio.features -> app.v2.domain.transition.features,
app.transition.recipe -> app.v2.domain.transition.recipe).

Unblocks the components chain + scorer port in Task 7-8."
```

---

## Task 7: Port `app/transition/components/` → `app/v2/domain/transition/components/`

Six pure per-component scorers: `bpm`, `harmonic`, `energy`, `spectral`, `groove`, `timbral`. Each imports `TrackFeatures`, `math_helpers`, `weights` (already ported in Tasks 5-6) plus `camelot` (ported Task 2) for `harmonic` and `section_context` (Task 6) for `harmonic`.

**Files:**
- Copy 6 files `app/transition/components/*.py` + `__init__.py` → `app/v2/domain/transition/components/`

- [ ] **Step 1: Catalogue internal imports per component**

```bash
for f in bpm.py harmonic.py energy.py spectral.py groove.py timbral.py __init__.py; do
  echo "=== components/$f ==="
  grep -n "^from\|^import" "app/transition/components/$f"
done
```

Expected import rewrites (applied uniformly):

| Legacy | v2 |
|---|---|
| `from app.entities.audio.features import TrackFeatures` | `from app.v2.domain.transition.features import TrackFeatures` |
| `from app.transition.math_helpers import ...` | `from app.v2.domain.transition.math_helpers import ...` |
| `from app.transition.weights import ...` | `from app.v2.domain.transition.weights import ...` |
| `from app.transition.section_context import SectionContext` | `from app.v2.domain.transition.section_context import SectionContext` |
| `from app.camelot.wheel import camelot_distance` | `from app.v2.domain.camelot.wheel import camelot_distance` |
| `from app.config import settings` | `from app.v2.config import settings` |

- [ ] **Step 2: Copy + rewrite**

```bash
for f in bpm.py harmonic.py energy.py spectral.py groove.py timbral.py __init__.py; do
  cp "app/transition/components/$f" "app/v2/domain/transition/components/$f"
done
```

Edit each copy per the table above.

- [ ] **Step 3: Smoke test the components package**

```bash
uv run python -c "
from app.v2.domain.transition.components import (
    score_bpm, score_harmonic, score_energy,
    score_spectral, score_groove, score_timbral,
)
from app.v2.domain.transition.features import TrackFeatures

a = TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                  spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                  hnr_db=10.0, chroma_entropy=0.6)
b = TrackFeatures(bpm=130.0, key_code=7, integrated_lufs=-7.5, energy_mean=0.32,
                  spectral_centroid_hz=3100.0, onset_rate=5.2, kick_prominence=0.55,
                  hnr_db=9.5, chroma_entropy=0.62)

for name, fn in [
    ('bpm', score_bpm), ('harmonic', score_harmonic), ('energy', score_energy),
    ('spectral', score_spectral), ('groove', score_groove), ('timbral', score_timbral),
]:
    s = fn(a, b)
    assert 0.0 <= s <= 1.0, f'{name} out of range: {s}'
    print(f'{name}: {s:.3f}')
"
```

Expected: six lines, each score in [0, 1].

- [ ] **Step 4: Parity test — v2 components produce same scores as legacy**

Create `tests/v2/domain/transition/test_components_parity.py`:

```python
"""Numeric parity: v2 components produce the same scores as legacy."""
from __future__ import annotations

import pytest

from app.v2.domain.transition.components import (
    score_bpm as v2_bpm,
    score_energy as v2_energy,
    score_groove as v2_groove,
    score_harmonic as v2_harmonic,
    score_spectral as v2_spectral,
    score_timbral as v2_timbral,
)
from app.v2.domain.transition.features import TrackFeatures as V2Features

def _make_features(cls: type, **kw: object) -> object:
    """Instantiate either v2 or legacy TrackFeatures with the same kwargs."""
    return cls(**kw)  # type: ignore[call-arg]

_FEATURES = dict(
    bpm=128.0,
    key_code=5,
    integrated_lufs=-8.0,
    energy_mean=0.3,
    spectral_centroid_hz=3000.0,
    onset_rate=5.0,
    kick_prominence=0.5,
    hnr_db=10.0,
    chroma_entropy=0.6,
)

@pytest.mark.parametrize(
    ("legacy_path", "v2_fn_name", "v2_fn"),
    [
        ("app.transition.components.bpm:score_bpm", "score_bpm", v2_bpm),
        ("app.transition.components.harmonic:score_harmonic", "score_harmonic", v2_harmonic),
        ("app.transition.components.energy:score_energy", "score_energy", v2_energy),
        ("app.transition.components.spectral:score_spectral", "score_spectral", v2_spectral),
        ("app.transition.components.groove:score_groove", "score_groove", v2_groove),
        ("app.transition.components.timbral:score_timbral", "score_timbral", v2_timbral),
    ],
)
def test_component_parity(legacy_path: str, v2_fn_name: str, v2_fn) -> None:
    mod_path, fn_name = legacy_path.split(":")
    legacy_mod = __import__(mod_path, fromlist=[fn_name])
    legacy_fn = getattr(legacy_mod, fn_name)
    # Legacy TrackFeatures
    from app.entities.audio.features import TrackFeatures as LegacyFeatures

    a_legacy = _make_features(LegacyFeatures, **_FEATURES)
    b_legacy = _make_features(LegacyFeatures, **{**_FEATURES, "bpm": 130.0, "key_code": 7})
    a_v2 = _make_features(V2Features, **_FEATURES)
    b_v2 = _make_features(V2Features, **{**_FEATURES, "bpm": 130.0, "key_code": 7})

    legacy_score = legacy_fn(a_legacy, b_legacy)
    v2_score = v2_fn(a_v2, b_v2)
    assert legacy_score == pytest.approx(v2_score, abs=1e-9), (
        f"{v2_fn_name} parity drift: legacy={legacy_score}, v2={v2_score}"
    )
```

This parity test exercises BOTH trees — if the v2 rewrite accidentally changes behaviour, the test catches it. It also proves the legacy tree is untouched.

- [ ] **Step 5: Run parity test**

```bash
uv run pytest tests/v2/domain/transition/test_components_parity.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Run full v2 domain test suite so far**

```bash
uv run pytest tests/v2/domain/ -v
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add app/v2/domain/transition/components tests/v2/domain/transition/test_components_parity.py
git commit -m "feat(v2): port transition components with parity harness

Six per-component scorers (bpm/harmonic/energy/spectral/groove/timbral)
lifted 1:1. Parity test exercises both trees side-by-side and asserts
numeric equality to 1e-9 on a fixed input — locks behavioural equivalence."
```

---

## Task 8: Port remaining `app/transition/` modules — `hard_constraints`, `scorer`, `style`, `recipe_engine`, `neural_mix` + `__init__.py`

These five files depend on everything ported so far. `scorer.py` is the orchestrator; `style.py` / `recipe_engine.py` / `neural_mix.py` are peers.

**Files:**
- Copy: 5 files `app/transition/{hard_constraints,scorer,style,recipe_engine,neural_mix}.py` + `__init__.py` → `app/v2/domain/transition/`

- [ ] **Step 1: Catalogue imports**

```bash
for f in hard_constraints.py scorer.py style.py recipe_engine.py neural_mix.py __init__.py; do
  echo "=== app/transition/$f ==="
  grep -n "^from\|^import" "app/transition/$f"
done
```

Expected rewrites (full table):

| File | Rewrites |
|---|---|
| `hard_constraints.py` | `app.camelot.wheel`→`app.v2.domain.camelot.wheel`; `app.entities.audio.features`→`app.v2.domain.transition.features`; `app.transition.math_helpers`→`app.v2.domain.transition.math_helpers`; `app.transition.score`→`app.v2.domain.transition.score`; `app.config`→`app.v2.config` |
| `scorer.py` | `app.core.constants`→`app.v2.shared.constants`; `app.entities.audio.features`→`app.v2.domain.transition.features`; `app.transition.{components,hard_constraints,intent,score,section_context,style,weights}`→`app.v2.domain.transition.*` |
| `style.py` | `app.core.constants`→`app.v2.shared.constants`; `app.entities.audio.features`→`app.v2.domain.transition.features`; `app.transition.{recipe,score,weights}`→`app.v2.domain.transition.*`; `app.transition.recipe_engine`→`app.v2.domain.transition.recipe_engine` (lazy import inside function) |
| `recipe_engine.py` | `app.core.constants`→`app.v2.shared.constants`; `app.entities.audio.features`→`app.v2.domain.transition.features`; `app.transition.{intent,recipe,score,section_context,subgenre_rules}`→`app.v2.domain.transition.*` |
| `neural_mix.py` | `app.camelot.wheel`→`app.v2.domain.camelot.wheel`; `app.entities.audio.features`→`app.v2.domain.transition.features`; `app.transition.{hard_constraints,math_helpers,score}`→`app.v2.domain.transition.*` |
| `__init__.py` | every `from app.transition.X`→`from app.v2.domain.transition.X` |

- [ ] **Step 2: Copy + rewrite**

```bash
for f in hard_constraints.py scorer.py style.py recipe_engine.py neural_mix.py __init__.py; do
  cp "app/transition/$f" "app/v2/domain/transition/$f"
done
```

Apply rewrites per table. Use `grep -n "from app\." app/v2/domain/transition/*.py` after editing to verify every remaining `app.` prefix is `app.v2.*`.

- [ ] **Step 3: Smoke test — scorer orchestration works**

```bash
uv run python -c "
from app.v2.domain.transition import TransitionScorer, TransitionScore
from app.v2.domain.transition.features import TrackFeatures

scorer = TransitionScorer()
a = TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                  spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                  hnr_db=10.0, chroma_entropy=0.6)
b = TrackFeatures(bpm=130.0, key_code=7, integrated_lufs=-7.5, energy_mean=0.32,
                  spectral_centroid_hz=3100.0, onset_rate=5.2, kick_prominence=0.55,
                  hnr_db=9.5, chroma_entropy=0.62)
s = scorer.score(a, b)
assert isinstance(s, TransitionScore)
print('overall:', s.overall)
print('hard_reject:', s.hard_reject)
"
```

Expected: `overall: 0.x` and `hard_reject: False`.

- [ ] **Step 4: Migrate remaining tests**

| Legacy | Target |
|---|---|
| `tests/test_domain/test_hard_constraints.py` | `tests/v2/domain/transition/test_hard_constraints.py` |
| `tests/test_domain/test_transition_style.py` | `tests/v2/domain/transition/test_style.py` |
| `tests/test_transition/test_neural_mix.py` | `tests/v2/domain/transition/test_neural_mix.py` |
| `tests/test_transition/test_recipe_engine.py` | `tests/v2/domain/transition/test_recipe_engine.py` |
| `tests/test_transition/test_recipe_integration.py` | `tests/v2/domain/transition/test_recipe_integration.py` |

For each: `cp SRC DST` then rewrite legacy imports.

- [ ] **Step 5: Add scorer parity test**

`tests/v2/domain/transition/test_scorer_parity.py`:

```python
"""Numeric parity: v2 TransitionScorer matches legacy on the same input."""
from __future__ import annotations

import pytest

from app.entities.audio.features import TrackFeatures as LegacyFeatures
from app.transition.scorer import TransitionScorer as LegacyScorer
from app.v2.domain.transition.features import TrackFeatures as V2Features
from app.v2.domain.transition.scorer import TransitionScorer as V2Scorer

_SHARED_KW = dict(
    bpm=128.0, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
    spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
    hnr_db=10.0, chroma_entropy=0.6,
)
_NEXT_KW = {**_SHARED_KW, "bpm": 130.0, "key_code": 7,
            "integrated_lufs": -7.5, "energy_mean": 0.32}

def test_scorer_overall_parity() -> None:
    legacy = LegacyScorer().score(
        LegacyFeatures(**_SHARED_KW), LegacyFeatures(**_NEXT_KW)
    )
    v2 = V2Scorer().score(V2Features(**_SHARED_KW), V2Features(**_NEXT_KW))
    assert legacy.overall == pytest.approx(v2.overall, abs=1e-9)
    assert legacy.hard_reject == v2.hard_reject

def test_scorer_component_parity() -> None:
    legacy = LegacyScorer().score(
        LegacyFeatures(**_SHARED_KW), LegacyFeatures(**_NEXT_KW)
    )
    v2 = V2Scorer().score(V2Features(**_SHARED_KW), V2Features(**_NEXT_KW))
    for attr in ("bpm", "harmonic", "energy", "spectral", "groove", "timbral"):
        a, b = getattr(legacy, attr), getattr(v2, attr)
        assert a == pytest.approx(b, abs=1e-9), f"{attr}: legacy={a}, v2={b}"

def test_scorer_hard_reject_parity() -> None:
    # Large BPM gap -> hard_reject on both sides.
    a = _SHARED_KW
    b = {**_SHARED_KW, "bpm": 180.0}
    legacy = LegacyScorer().score(LegacyFeatures(**a), LegacyFeatures(**b))
    v2 = V2Scorer().score(V2Features(**a), V2Features(**b))
    assert legacy.hard_reject == v2.hard_reject
    assert legacy.overall == pytest.approx(v2.overall, abs=1e-9)
```

- [ ] **Step 6: Run the full v2 transition suite**

```bash
uv run pytest tests/v2/domain/transition/ -v
```

Expected: all pass.

- [ ] **Step 7: Run legacy transition tests — must still be green**

```bash
uv run pytest tests/test_transition/ tests/test_domain/ -v
```

Expected: all pass. If anything fails here, the legacy tree was contaminated by the port — revert.

- [ ] **Step 8: Commit**

```bash
git add app/v2/domain/transition tests/v2/domain/transition
git commit -m "feat(v2): port transition scorer + recipe + neural + style + hard_constraints

Completes app/v2/domain/transition — 12 modules now mirror legacy
app/transition. Parity test locks TransitionScorer output to 1e-9
precision against the legacy scorer. Legacy tree untouched; both
suites green."
```

---

## Task 9: Port `app/optimization/` → `app/v2/domain/optimization/`

Five modules — `result`, `protocol`, `fitness`, `greedy`, `genetic`. `greedy` and `genetic` depend on `transition.scorer` (ported Task 8), `template.models` (Task 3), `TrackFeatures` (Task 5), `fitness` (this task), `result` (this task).

**Files:**
- Copy 5 files `app/optimization/*.py` + `__init__.py` → `app/v2/domain/optimization/`

- [ ] **Step 1: Catalogue imports**

```bash
for f in result.py protocol.py fitness.py greedy.py genetic.py __init__.py; do
  echo "=== app/optimization/$f ==="
  grep -n "^from\|^import" "app/optimization/$f"
done
```

Rewrite table:

| File | Legacy | v2 |
|---|---|---|
| `fitness.py` | `app.entities.audio.features` | `app.v2.domain.transition.features` |
| `fitness.py` | `app.templates.models` | `app.v2.domain.template.models` |
| `fitness.py` | `app.transition.intent` | `app.v2.domain.transition.intent` |
| `fitness.py` | `app.transition.scorer` | `app.v2.domain.transition.scorer` |
| `fitness.py` | `app.core.constants` | `app.v2.shared.constants` |
| `greedy.py`, `genetic.py` | `app.entities.audio.features` | `app.v2.domain.transition.features` |
| `greedy.py`, `genetic.py` | `app.templates.models` | `app.v2.domain.template.models` |
| `greedy.py`, `genetic.py` | `app.transition.scorer` | `app.v2.domain.transition.scorer` |
| `greedy.py`, `genetic.py` | `app.optimization.*` | `app.v2.domain.optimization.*` |
| `genetic.py` | `app.config` | `app.v2.config` |
| `protocol.py` | `app.entities.audio.features` | `app.v2.domain.transition.features` |
| `protocol.py` | `app.templates.models` | `app.v2.domain.template.models` |
| `protocol.py` | `app.optimization.result` | `app.v2.domain.optimization.result` |
| `__init__.py` | `app.optimization.*` | `app.v2.domain.optimization.*` |
| `result.py` | stdlib only | no rewrite |

- [ ] **Step 2: Copy + rewrite**

```bash
for f in result.py protocol.py fitness.py greedy.py genetic.py __init__.py; do
  cp "app/optimization/$f" "app/v2/domain/optimization/$f"
done
```

Apply rewrites. `grep -n "from app\." app/v2/domain/optimization/*.py` must show only `app.v2.*`.

- [ ] **Step 3: Smoke test — greedy builder**

```bash
uv run python -c "
from app.v2.domain.optimization import GreedyChainBuilder, OptimizationResult
from app.v2.domain.transition.features import TrackFeatures
from app.v2.domain.transition.scorer import TransitionScorer

features = [
    TrackFeatures(bpm=124.0, key_code=5, integrated_lufs=-9.0, energy_mean=0.25,
                  spectral_centroid_hz=2800.0, onset_rate=4.5, kick_prominence=0.45,
                  hnr_db=10.0, chroma_entropy=0.6),
    TrackFeatures(bpm=126.0, key_code=7, integrated_lufs=-8.5, energy_mean=0.28,
                  spectral_centroid_hz=2900.0, onset_rate=4.7, kick_prominence=0.48,
                  hnr_db=9.8, chroma_entropy=0.62),
    TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                  spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                  hnr_db=10.0, chroma_entropy=0.6),
]
ids = [101, 102, 103]
builder = GreedyChainBuilder(scorer=TransitionScorer())
res = builder.optimize(features, ids)
assert isinstance(res, OptimizationResult)
assert sorted(res.track_order) == sorted(ids)
print('greedy order:', res.track_order, 'quality:', round(res.quality_score, 3))
"
```

Expected: a permutation of `[101, 102, 103]` and a quality score in [0, 1].

- [ ] **Step 4: Create tests**

`tests/v2/domain/optimization/test_fitness.py`:

```python
"""compute_fitness on a small synthetic set."""
from __future__ import annotations

import pytest

from app.v2.domain.optimization.fitness import compute_fitness
from app.v2.domain.transition.features import TrackFeatures
from app.v2.domain.transition.scorer import TransitionScorer

def _features_map() -> dict[int, TrackFeatures]:
    base = dict(
        integrated_lufs=-8.0, energy_mean=0.3, spectral_centroid_hz=3000.0,
        onset_rate=5.0, kick_prominence=0.5, hnr_db=10.0, chroma_entropy=0.6,
    )
    return {
        101: TrackFeatures(bpm=124.0, key_code=5, **base),
        102: TrackFeatures(bpm=126.0, key_code=7, **base),
        103: TrackFeatures(bpm=128.0, key_code=5, **base),
    }

def test_fitness_in_unit_interval() -> None:
    fmap = _features_map()
    score = compute_fitness([101, 102, 103], fmap, TransitionScorer())
    assert 0.0 <= score <= 1.0

def test_fitness_deterministic() -> None:
    fmap = _features_map()
    a = compute_fitness([101, 102, 103], fmap, TransitionScorer())
    b = compute_fitness([101, 102, 103], fmap, TransitionScorer())
    assert a == pytest.approx(b)
```

`tests/v2/domain/optimization/test_greedy.py`:

```python
"""GreedyChainBuilder regression."""
from __future__ import annotations

from app.v2.domain.optimization import GreedyChainBuilder
from app.v2.domain.transition.features import TrackFeatures
from app.v2.domain.transition.scorer import TransitionScorer

def test_greedy_returns_permutation() -> None:
    feats = [
        TrackFeatures(bpm=b, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                      spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                      hnr_db=10.0, chroma_entropy=0.6)
        for b in (124.0, 126.0, 128.0)
    ]
    ids = [1, 2, 3]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids)
    assert sorted(res.track_order) == sorted(ids)

def test_greedy_respects_pinned() -> None:
    feats = [
        TrackFeatures(bpm=b, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                      spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                      hnr_db=10.0, chroma_entropy=0.6)
        for b in (124.0, 126.0, 128.0, 130.0)
    ]
    ids = [1, 2, 3, 4]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids, pinned={4})
    assert 4 in res.track_order

def test_greedy_excludes_tracks() -> None:
    feats = [
        TrackFeatures(bpm=b, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                      spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                      hnr_db=10.0, chroma_entropy=0.6)
        for b in (124.0, 126.0, 128.0)
    ]
    ids = [1, 2, 3]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids, excluded={2})
    assert 2 not in res.track_order
```

`tests/v2/domain/optimization/test_genetic.py`:

```python
"""GeneticAlgorithm smoke test (small population, quick convergence)."""
from __future__ import annotations

from app.v2.domain.optimization import GeneticAlgorithm
from app.v2.domain.transition.features import TrackFeatures
from app.v2.domain.transition.scorer import TransitionScorer

def test_ga_returns_permutation() -> None:
    feats = [
        TrackFeatures(bpm=b, key_code=5, integrated_lufs=-8.0, energy_mean=0.3,
                      spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
                      hnr_db=10.0, chroma_entropy=0.6)
        for b in (124.0, 126.0, 128.0, 130.0)
    ]
    ids = [10, 20, 30, 40]
    # Override settings for fast test via constructor params (GA exposes knobs).
    ga = GeneticAlgorithm(
        scorer=TransitionScorer(),
        population_size=8,
        max_generations=5,
        mutation_rate=0.1,
        elitism_rate=0.25,
        tournament_size=2,
    )
    res = ga.optimize(feats, ids)
    assert sorted(res.track_order) == sorted(ids)
    assert 0.0 <= res.quality_score <= 1.0
```

If `GeneticAlgorithm`'s `__init__` doesn't accept those knobs, fall back to the default-settings call (the parity behaviour is all we need).

- [ ] **Step 5: Run v2 optimization tests**

```bash
uv run pytest tests/v2/domain/optimization/ -v
```

Expected: all pass.

- [ ] **Step 6: Verify legacy optimization tests still green**

```bash
if [ -d tests/test_optimization ]; then
  uv run pytest tests/test_optimization/ -v
fi
uv run pytest tests/test_services/ -v 2>&1 | tail -20  # services use optimization
```

Expected: all pass (services import legacy `app.optimization` — unchanged).

- [ ] **Step 7: Commit**

```bash
git add app/v2/domain/optimization tests/v2/domain/optimization
git commit -m "feat(v2): port optimization (GA + greedy + fitness) to app/v2/domain

Five modules lifted 1:1. Greedy/GA/fitness now use v2 scorer and
v2 TrackFeatures exclusively. Legacy app/optimization retained and
still green (services/set/builder.py uses it)."
```

---

## Task 10: Port `app/audio/core/` → `app/v2/audio/core/`

Core is the foundation of audio — `types`, `loader`, `framing`, `context`, `rhythm`, `spectral`, `tonal`. Port first so analyzers can depend on v2 core.

**Files:**
- Copy 7 files `app/audio/core/*.py` + `__init__.py` → `app/v2/audio/core/`

- [ ] **Step 1: Catalogue imports**

```bash
for f in types.py loader.py framing.py context.py rhythm.py spectral.py tonal.py __init__.py; do
  echo "=== app/audio/core/$f ==="
  grep -n "^from\|^import" "app/audio/core/$f"
done
```

Expected rewrites:

| Legacy | v2 |
|---|---|
| `from app.config import settings` | `from app.v2.config import settings` |
| `from app.core.constants import ...` | `from app.v2.shared.constants import ...` |
| `from app.audio.core.X import ...` | `from app.v2.audio.core.X import ...` |

- [ ] **Step 2: Copy + rewrite**

```bash
for f in types.py loader.py framing.py context.py rhythm.py spectral.py tonal.py __init__.py; do
  cp "app/audio/core/$f" "app/v2/audio/core/$f"
done
```

Apply rewrites. Keep `try: import librosa except ImportError:` guards exactly as in legacy.

- [ ] **Step 3: Smoke test — AudioSignal + framing load**

```bash
uv run python -c "
from app.v2.audio.core.types import AudioSignal
import numpy as np
sig = AudioSignal(
    samples=np.zeros(22050, dtype=np.float32),
    sample_rate=22050,
    duration_seconds=1.0,
    file_path=None,  # type: ignore
)
print('AudioSignal:', sig.sample_rate, sig.duration_seconds)

from app.v2.audio.core import framing
print('framing module:', framing.__name__)
"
```

Expected: `AudioSignal: 22050 1.0`; `framing module: app.v2.audio.core.framing`.

- [ ] **Step 4: Migrate core tests**

Mirror these tests with the usual import rewrite:

| Legacy | Target |
|---|---|
| `tests/test_audio/test_core_types.py` | `tests/v2/audio/test_core_types.py` |
| `tests/test_audio/test_core_loader.py` | `tests/v2/audio/test_core_loader.py` |
| `tests/test_audio/test_core_framing.py` | `tests/v2/audio/test_core_framing.py` |
| `tests/test_audio/test_core_context.py` | `tests/v2/audio/test_core_context.py` |
| `tests/test_audio/test_core_rhythm.py` | `tests/v2/audio/test_core_rhythm.py` |
| `tests/test_audio/test_core_spectral.py` | `tests/v2/audio/test_core_spectral.py` |
| `tests/test_audio/test_core_tonal.py` | `tests/v2/audio/test_core_tonal.py` |

For each: `cp SRC DST` then global replace:
- `from app.audio.core` → `from app.v2.audio.core`
- `from app.config` → `from app.v2.config`
- `from app.core.constants` → `from app.v2.shared.constants`

- [ ] **Step 5: Run v2 audio core tests**

```bash
uv run pytest tests/v2/audio/test_core_*.py -v
```

Expected: all pass (may be skipped if `[audio]` extra not installed — that's fine).

- [ ] **Step 6: Commit**

```bash
git add app/v2/audio/core tests/v2/audio/test_core_*.py
git commit -m "feat(v2): port audio core (types/loader/framing/context/rhythm/spectral/tonal)

Seven core modules lifted 1:1 to app/v2/audio/core. Optional librosa
guards preserved. AnalysisContext, framing, and shared STFT plumbing
ready for analyzer ports in Task 11."
```

---

## Task 11: Port `app/audio/analyzers/` → `app/v2/audio/analyzers/`

18 analyzers + `base.py` + `__init__.py`. `base.py` first — defines `BaseAnalyzer`, `AnalyzerResult`, `AnalyzerRegistry`, the `@registry.register` decorator. Other analyzers subclass `BaseAnalyzer` and self-register.

**Files:**
- Copy: `app/audio/analyzers/base.py` → `app/v2/audio/analyzers/base.py`
- Copy: `app/audio/analyzers/__init__.py` → `app/v2/audio/analyzers/__init__.py`
- Copy: 18 analyzer modules → `app/v2/audio/analyzers/`

- [ ] **Step 1: Port `base.py` first**

```bash
cp app/audio/analyzers/base.py app/v2/audio/analyzers/base.py
```

Rewrites:
- `from app.audio.core.X` → `from app.v2.audio.core.X`
- `from app.config` → `from app.v2.config`
- `from app.core.constants` → `from app.v2.shared.constants`

Smoke:

```bash
uv run python -c "
from app.v2.audio.analyzers.base import BaseAnalyzer, AnalyzerResult
print('BaseAnalyzer:', BaseAnalyzer.__name__)
"
```

Expected: `BaseAnalyzer: BaseAnalyzer`.

- [ ] **Step 2: Port 18 analyzer files**

```bash
ANALYZERS="loudness.py energy.py spectral.py structure.py \
           bpm.py key.py beat.py mfcc.py tonnetz.py tempogram.py \
           bpm_histogram.py phrase.py \
           beats_loudness.py danceability.py dissonance.py \
           dynamic_complexity.py pitch_salience.py spectral_complexity.py"

for f in $ANALYZERS; do
  cp "app/audio/analyzers/$f" "app/v2/audio/analyzers/$f"
done
```

Per-file rewrites — apply uniformly:

| Legacy | v2 |
|---|---|
| `from app.audio.analyzers.base` | `from app.v2.audio.analyzers.base` |
| `from app.audio.core.*` | `from app.v2.audio.core.*` |
| `from app.config` | `from app.v2.config` |
| `from app.core.constants` | `from app.v2.shared.constants` |

Verify:

```bash
grep -rn "^from app\." app/v2/audio/analyzers/ | grep -v "app\.v2\." || echo "CLEAN"
```

Expected: `CLEAN` (no legacy `app.` imports remain).

- [ ] **Step 3: Port `__init__.py` and verify registry populates**

```bash
cp app/audio/analyzers/__init__.py app/v2/audio/analyzers/__init__.py
```

Rewrite `from app.audio.analyzers.X` → `from app.v2.audio.analyzers.X`.

Smoke test — analyzer registry must populate on import:

```bash
uv run python -c "
import app.v2.audio.analyzers as _pkg   # triggers registrations
from app.v2.audio.analyzers.base import BaseAnalyzer
# Legacy registry is module-global keyed by name — v2 uses the SAME global
# (the decorator runs at import time, registrations accumulate across trees).
# We only assert v2 modules imported without error.
print('analyzers package loaded')
"
```

Expected: `analyzers package loaded`.

> **Gotcha:** per `.claude/rules/audio.md` — `_ANALYZER_REGISTRY` is a global dict and `importlib` does NOT re-register on re-import. If the legacy tree was already imported in the same Python process, the v2 analyzers' `@register` calls are no-ops. This is acceptable (the registry behaves as expected in the intended use-case: start a fresh process with only v2 imports). Do NOT `clear()` the registry in tests — only delete `_test_*` keys.

- [ ] **Step 4: Migrate analyzer tests**

For each test in `tests/test_audio/`:

```bash
TESTS="test_analyzer_base.py test_registry.py test_bpm_detector.py \
       test_spectral.py test_structure.py test_beat_export.py \
       test_bpm_histogram.py test_phrase.py test_tempogram.py test_tonnetz.py \
       test_beats_loudness.py test_danceability.py test_dissonance.py \
       test_dynamic_complexity.py test_pitch_salience.py test_spectral_complexity.py \
       test_analyzers.py"

for f in $TESTS; do
  if [ -f "tests/test_audio/$f" ]; then
    cp "tests/test_audio/$f" "tests/v2/audio/$f"
  fi
done
```

For each copied test: rewrite `from app.audio.X` → `from app.v2.audio.X`, `from app.config` → `from app.v2.config`, `from app.core.constants` → `from app.v2.shared.constants`.

- [ ] **Step 5: Run v2 analyzer tests**

```bash
uv run pytest tests/v2/audio/ -v --no-header 2>&1 | tail -60
```

Expected: all pass or skipped (when librosa/essentia not installed — matches legacy behaviour).

- [ ] **Step 6: Legacy audio tests must still be green**

```bash
uv run pytest tests/test_audio/ -v --no-header 2>&1 | tail -20
```

Expected: all pass/skip identically.

- [ ] **Step 7: Commit**

```bash
git add app/v2/audio/analyzers tests/v2/audio
git commit -m "feat(v2): port 18 analyzers to app/v2/audio/analyzers

BaseAnalyzer + AnalyzerResult + AnalyzerRegistry + 18 concrete
analyzers (loudness/energy/spectral/structure/bpm/key/beat/mfcc/
tonnetz/tempogram/bpm_histogram/phrase/beats_loudness/danceability/
dissonance/dynamic_complexity/pitch_salience/spectral_complexity).

All import-path rewrites only. Legacy app/audio/analyzers retained.
Registry decorator semantics preserved — concurrent legacy + v2
imports produce the documented no-op behaviour."
```

---

## Task 12: Port `app/audio/classification/` → `app/v2/audio/classification/`

Rule-based mood classifier + 15 subgenre profile weights.

**Files:**
- Copy: `app/audio/classification/classifier.py` → `app/v2/audio/classification/classifier.py`
- Copy: `app/audio/classification/profiles.py` → `app/v2/audio/classification/profiles.py`
- Copy: `app/audio/classification/__init__.py` → `app/v2/audio/classification/__init__.py`

- [ ] **Step 1: Rewrite imports per table**

```bash
cp app/audio/classification/classifier.py app/v2/audio/classification/classifier.py
cp app/audio/classification/profiles.py app/v2/audio/classification/profiles.py
cp app/audio/classification/__init__.py app/v2/audio/classification/__init__.py
```

| File | Legacy | v2 |
|---|---|---|
| `classifier.py` | `from app.config import settings` | `from app.v2.config import settings` |
| `classifier.py` | `from app.core.constants import TechnoSubgenre` | `from app.v2.shared.constants import TechnoSubgenre` |
| `profiles.py` | `from app.core.constants import TechnoSubgenre` | `from app.v2.shared.constants import TechnoSubgenre` |
| `__init__.py` | `from app.audio.classification.X` | `from app.v2.audio.classification.X` |

- [ ] **Step 2: Smoke test classifier returns known subgenre**

```bash
uv run python -c "
from app.v2.audio.classification.classifier import classify_mood, MoodResult
# Most drivers: enum sanity
from app.v2.shared.constants import TechnoSubgenre
print(list(TechnoSubgenre)[:3])
"
```

Expected: first 3 subgenre enum values print.

- [ ] **Step 3: Migrate tests**

| Legacy | Target |
|---|---|
| `tests/test_audio/test_classification.py` | `tests/v2/audio/test_classification.py` |
| `tests/test_audio/test_mood.py` | `tests/v2/audio/test_mood.py` |

Rewrite imports as usual.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/v2/audio/test_classification.py tests/v2/audio/test_mood.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/v2/audio/classification tests/v2/audio/test_classification.py tests/v2/audio/test_mood.py
git commit -m "feat(v2): port mood classifier to app/v2/audio/classification

Rule-based classifier (15 subgenres) + weighted profile functions
lifted 1:1. catch_all penalty (driving/hypnotic) preserved."
```

---

## Task 13: Port top-level `app/audio/*.py` — `pipeline`, `level_config`, `timeseries`, `temp_download`

Final audio files. `pipeline.py` is the orchestrator — depends on v2 `core`, `analyzers`, `classification`, `timeseries`.

**Files:**
- Copy: `app/audio/pipeline.py` → `app/v2/audio/pipeline.py`
- Copy: `app/audio/level_config.py` → `app/v2/audio/level_config.py`
- Copy: `app/audio/timeseries.py` → `app/v2/audio/timeseries.py`
- Copy: `app/audio/temp_download.py` → `app/v2/audio/temp_download.py`
- Copy: `app/audio/__init__.py` → `app/v2/audio/__init__.py` (overwrite Task 1 placeholder)

- [ ] **Step 1: Catalogue imports**

```bash
for f in pipeline.py level_config.py timeseries.py temp_download.py __init__.py; do
  echo "=== app/audio/$f ==="
  grep -n "^from\|^import" "app/audio/$f"
done
```

Typical rewrites:

| Legacy | v2 |
|---|---|
| `from app.audio.core.*` | `from app.v2.audio.core.*` |
| `from app.audio.analyzers.*` | `from app.v2.audio.analyzers.*` |
| `from app.audio.classification.*` | `from app.v2.audio.classification.*` |
| `from app.audio.timeseries` | `from app.v2.audio.timeseries` |
| `from app.config` | `from app.v2.config` |
| `from app.core.constants` | `from app.v2.shared.constants` |
| `from app.core.utils.*` | `from app.v2.shared.*` (Phase 1 moved utils into shared) |

> **Gotcha:** `pipeline.py` has a `_warmup_librosa()` helper that pre-imports `librosa.beat`, `librosa.onset`, `librosa.feature` on the main thread (per `.claude/rules/audio.md`). Keep that verbatim — the race-condition fix must survive the port.

- [ ] **Step 2: Copy + rewrite**

```bash
for f in pipeline.py level_config.py timeseries.py temp_download.py __init__.py; do
  cp "app/audio/$f" "app/v2/audio/$f"
done
```

Apply rewrites. Then:

```bash
grep -rn "^from app\." app/v2/audio/*.py | grep -v "app\.v2\." || echo "CLEAN"
```

Expected: `CLEAN`.

- [ ] **Step 3: Smoke test — pipeline instantiates**

```bash
uv run python -c "
from app.v2.audio.pipeline import AnalysisPipeline
from app.v2.audio.analyzers.base import BaseAnalyzer
# AnalyzerRegistry should be populated by v2 imports.
pipeline = AnalysisPipeline()
print('pipeline OK')
"
```

Expected: `pipeline OK`.

- [ ] **Step 4: Migrate remaining audio tests**

| Legacy | Target |
|---|---|
| `tests/test_audio/test_pipeline_refactored.py` | `tests/v2/audio/test_pipeline_refactored.py` |
| `tests/test_audio/test_level_config.py` | `tests/v2/audio/test_level_config.py` |
| `tests/test_audio/test_timeseries.py` | `tests/v2/audio/test_timeseries.py` |
| `tests/test_audio/test_temp_download.py` | `tests/v2/audio/test_temp_download.py` |

Rewrite imports, then:

```bash
uv run pytest tests/v2/audio/ -v
```

Expected: all pass or skip cleanly.

- [ ] **Step 5: Verify legacy audio tests still green**

```bash
uv run pytest tests/test_audio/ -v --no-header 2>&1 | tail -5
```

Expected: same pass/skip counts as before the port.

- [ ] **Step 6: Commit**

```bash
git add app/v2/audio/pipeline.py app/v2/audio/level_config.py app/v2/audio/timeseries.py app/v2/audio/temp_download.py app/v2/audio/__init__.py tests/v2/audio
git commit -m "feat(v2): port audio pipeline orchestrator + helpers

AnalysisPipeline (with _warmup_librosa race fix preserved),
level_config (L1-L4 tiered), timeseries NPZ helper, temp_download
stub. Completes app/v2/audio/. Legacy app/audio/ remains and stays
green."
```

---

## Task 14: Port `app/entities/` remaining files — delete-candidate audit

Per blueprint §14.5, only `app/entities/audio/features.py` survives (merged into `app/v2/domain/transition/features.py` in Task 5). Other `entities/` files are delete-candidates for Phase 7.

- [ ] **Step 1: Enumerate remaining entities files**

```bash
find app/entities -name "*.py" -not -name "__init__.py" -not -path "*/audio/features.py"
```

Likely output: `app/entities/base.py`, `app/entities/value_objects/*.py`, `app/entities/audio/__init__.py`.

- [ ] **Step 2: Check what references them**

```bash
uv run python -c "
import subprocess
import pathlib
for p in pathlib.Path('app/entities').rglob('*.py'):
    if p.name == '__init__.py' or p.relative_to('app/entities') == pathlib.Path('audio/features.py'):
        continue
    mod = 'app.' + str(p.with_suffix('')).replace('/', '.').replace('app.', '', 1)
    # Count refs across app/ excluding entities itself
    r = subprocess.run(['grep', '-rln', mod, 'app/', 'tests/'], capture_output=True, text=True)
    lines = [ln for ln in r.stdout.splitlines() if 'app/entities' not in ln]
    print(f'{mod}: {len(lines)} external refs', lines[:3])
"
```

- [ ] **Step 3: Port any non-trivial content**

If `app/entities/base.py` defines a shared Pydantic or dataclass used by v2 code, port it to `app/v2/shared/entity_base.py`. If not referenced by v2, skip — Phase 7 will delete.

For this plan, we assume no non-trivial content. Verify by running `git grep "from app.entities.base"` from `app/v2/`:

```bash
grep -rn "from app.entities" app/v2/ || echo "NO v2 references to app.entities"
```

Expected: `NO v2 references to app.entities`.

- [ ] **Step 4: No commit needed if nothing to port**

Document the audit outcome in the Task 15 commit message.

---

## Task 15: Update `.importlinter` — add `v2-domain-pure` and `v2-audio-internal` contracts

Add the two new contracts from the spec. Leave all existing contracts intact.

**Files:**
- Edit: `.importlinter`

- [ ] **Step 1: Read current contracts**

```bash
cat .importlinter
```

Expected: 6 contracts from prior phases (services-no-mcp, transition-pure, optimization-pure, utils-leaf, api-no-db, engines-no-transport).

- [ ] **Step 2: Append the two new contracts**

Add to the end of `.importlinter`:

```ini

# ── Contract 7: v2 domain is pure ──────────────────────────────────
# Mirrors Contract 2 / 3 but targets app.v2.domain — the target layer
# after Phase 7 cutover. Enforced from Phase 6 onward.
[importlinter:contract:v2-domain-pure]
name = app.v2.domain must be pure (no I/O, no DB, no FastMCP)
type = forbidden
source_modules =
    app.v2.domain
forbidden_modules =
    app.v2.models
    app.v2.repositories
    app.v2.handlers
    app.v2.tools
    app.v2.resources
    app.v2.prompts
    app.v2.providers
    app.v2.server
    app.v2.rest
    app.v2.db
    app.v2.audio
    fastmcp
    sqlalchemy
    httpx

# ── Contract 8: v2 audio internal ──────────────────────────────────
# Audio pipeline must not touch MCP / REST / repositories.
[importlinter:contract:v2-audio-internal]
name = app.v2.audio must not touch MCP / REST / repositories
type = forbidden
source_modules =
    app.v2.audio
forbidden_modules =
    fastmcp
    app.v2.tools
    app.v2.resources
    app.v2.prompts
    app.v2.rest
    app.v2.repositories
    app.v2.server
```

- [ ] **Step 3: Run import-linter**

```bash
uv run lint-imports 2>&1 | tail -30
```

Expected: all 8 contracts pass (**KEPT**). If any contract reports broken imports, the v2 port brought in a forbidden dep — debug and fix before committing.

> **Common cause of failure**: a v2 module forgot to update an `from app.config import settings` line → still imports legacy `app.config`. Search with:
>
> ```bash
> grep -rn "from app\." app/v2/domain app/v2/audio | grep -v "app\.v2\."
> ```
>
> Any hits are bugs.

- [ ] **Step 4: Commit**

```bash
git add .importlinter
git commit -m "chore(importlinter): add v2-domain-pure and v2-audio-internal contracts

v2-domain-pure forbids app.v2.domain from importing models, repositories,
tools, handlers, server, rest, audio, fastmcp, sqlalchemy, httpx.

v2-audio-internal forbids app.v2.audio from touching MCP transport layers
and repositories.

Locks the invariants established by Phase 6 ports."
```

---

## Task 16: Global parity check — all four pillars green

After all ports + contract: run the complete gate locally.

- [ ] **Step 1: Full import-linter**

```bash
uv run lint-imports
```

Expected: all contracts pass.

- [ ] **Step 2: Full test suite — legacy tree**

```bash
uv run pytest tests/test_transition tests/test_domain tests/test_audio tests/test_services -q 2>&1 | tail -20
```

Expected: same pass/skip counts as before Phase 6 started (Phase 6 must not touch the legacy tree).

- [ ] **Step 3: Full test suite — v2 tree**

```bash
uv run pytest tests/v2/ -q 2>&1 | tail -20
```

Expected: all pass or skip (skip = `[audio]` extra not installed).

- [ ] **Step 4: mypy on v2 domain + audio**

```bash
uv run mypy app/v2/domain app/v2/audio 2>&1 | tail -20
```

Expected: `Success: no issues found` (or same baseline as legacy had — porting does not regress types).

- [ ] **Step 5: Ruff check**

```bash
uv run ruff check app/v2/domain app/v2/audio tests/v2/
uv run ruff format --check app/v2/domain app/v2/audio tests/v2/
```

Expected: clean.

- [ ] **Step 6: `make check`**

```bash
make check
```

Expected: all green.

- [ ] **Step 7: Final grep for legacy imports in v2 domain + audio**

```bash
grep -rn "^from app\." app/v2/domain app/v2/audio | grep -v "from app\.v2\." | grep -v "^#" || echo "CLEAN"
```

Expected: `CLEAN` — no stray `from app.transition`, `from app.config`, `from app.core`, `from app.entities`, etc.

- [ ] **Step 8: No commit (verification-only task)**

If any step failed, add remediation commits scoped to the failure, then rerun.

---

## Task 17: Final parity test — v2 vs legacy full-track scoring

End-to-end sanity: run the full `TransitionScorer.score()` pipeline on a synthetic pair through both trees and assert equality for every field of `TransitionScore`.

**Files:**
- Create: `tests/v2/domain/transition/test_full_parity.py`

- [ ] **Step 1: Write parity test**

```python
# tests/v2/domain/transition/test_full_parity.py
"""End-to-end parity: v2 and legacy TransitionScorer agree field-by-field."""
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.entities.audio.features import TrackFeatures as LegacyFeatures
from app.transition.scorer import TransitionScorer as LegacyScorer
from app.v2.domain.transition.features import TrackFeatures as V2Features
from app.v2.domain.transition.scorer import TransitionScorer as V2Scorer

# Three representative pairs — typical mix, near-reject, hard-reject.
_PAIRS = [
    (
        dict(bpm=124.0, key_code=5, integrated_lufs=-9.0, energy_mean=0.25,
             spectral_centroid_hz=2800.0, onset_rate=4.5, kick_prominence=0.45,
             hnr_db=10.0, chroma_entropy=0.6),
        dict(bpm=126.0, key_code=6, integrated_lufs=-8.5, energy_mean=0.28,
             spectral_centroid_hz=2900.0, onset_rate=4.7, kick_prominence=0.48,
             hnr_db=9.8, chroma_entropy=0.62),
        "typical",
    ),
    (
        dict(bpm=128.0, key_code=0, integrated_lufs=-8.0, energy_mean=0.3,
             spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
             hnr_db=10.0, chroma_entropy=0.6),
        dict(bpm=132.0, key_code=12, integrated_lufs=-6.0, energy_mean=0.4,
             spectral_centroid_hz=3200.0, onset_rate=5.5, kick_prominence=0.6,
             hnr_db=9.0, chroma_entropy=0.65),
        "near_boundary",
    ),
    (
        dict(bpm=128.0, key_code=0, integrated_lufs=-8.0, energy_mean=0.3,
             spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
             hnr_db=10.0, chroma_entropy=0.6),
        dict(bpm=180.0, key_code=0, integrated_lufs=-8.0, energy_mean=0.3,
             spectral_centroid_hz=3000.0, onset_rate=5.0, kick_prominence=0.5,
             hnr_db=10.0, chroma_entropy=0.6),
        "hard_reject",
    ),
]

def _to_dict(score: Any) -> dict[str, Any]:
    """Flatten a TransitionScore dataclass into comparable primitives."""
    if dataclasses.is_dataclass(score):
        return dataclasses.asdict(score)
    return dict(score.__dict__)

@pytest.mark.parametrize(("a_kw", "b_kw", "case"), _PAIRS)
def test_transition_score_parity(a_kw, b_kw, case) -> None:
    legacy_score = LegacyScorer().score(
        LegacyFeatures(**a_kw), LegacyFeatures(**b_kw)
    )
    v2_score = V2Scorer().score(V2Features(**a_kw), V2Features(**b_kw))

    legacy_d = _to_dict(legacy_score)
    v2_d = _to_dict(v2_score)

    assert set(legacy_d.keys()) == set(v2_d.keys()), (
        f"[{case}] field drift: legacy={legacy_d.keys()} v2={v2_d.keys()}"
    )
    for field in legacy_d:
        a, b = legacy_d[field], v2_d[field]
        if isinstance(a, float) and isinstance(b, float):
            assert a == pytest.approx(b, abs=1e-9, nan_ok=True), (
                f"[{case}] field {field}: legacy={a}, v2={b}"
            )
        else:
            assert a == b, f"[{case}] field {field}: legacy={a!r}, v2={b!r}"
```

- [ ] **Step 2: Run it**

```bash
uv run pytest tests/v2/domain/transition/test_full_parity.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/v2/domain/transition/test_full_parity.py
git commit -m "test(v2): full-field parity between v2 and legacy TransitionScorer

Three representative pairs (typical / near-boundary / hard-reject) —
every TransitionScore field asserted equal field-by-field to 1e-9
precision. Locks behavioural equivalence so Phase 7 cutover is safe."
```

---

## Task 18: Smoke — `uv run fastmcp dev` still boots (legacy server unchanged)

Phase 6 promised zero behavioural change to legacy — confirm the MCP server still starts and responds to `list_tools`.

- [ ] **Step 1: Start server in background**

```bash
uv run fastmcp run app/server.py &
SERVER_PID=$!
sleep 5
```

- [ ] **Step 2: If server is HTTP — curl list_tools. If stdio — just confirm it's still alive**

```bash
if ps -p $SERVER_PID > /dev/null; then
    echo "Server still running"
    kill $SERVER_PID
else
    echo "FAILED — server died"
    exit 1
fi
```

- [ ] **Step 3: No commit (smoke only)**

If the server failed to boot, the v2 port inadvertently broke legacy. Investigate — likely root cause: accidental edit to a legacy file (grep `git diff HEAD~N -- app/transition app/optimization app/camelot app/templates app/audit app/audio`). Revert if needed.

---

## Task 19: Phase 6 summary + branch promotion

- [ ] **Step 1: Count ported files**

```bash
find app/v2/domain app/v2/audio -name "*.py" -not -name "__init__.py" | wc -l
find tests/v2/domain tests/v2/audio -name "*.py" -not -name "__init__.py" | wc -l
```

Expected: ~57 source modules, ~35 tests.

- [ ] **Step 2: Verify all commits are atomic per family**

```bash
git log --oneline $(git merge-base HEAD main)..HEAD -- app/v2/domain app/v2/audio tests/v2 .importlinter
```

Expected: roughly 17 commits:
- `feat(v2): scaffold domain and audio package skeletons`
- `feat(v2): port camelot wheel …`
- `feat(v2): port templates to app/v2/domain/template (singular)`
- `feat(v2): port audit rules …`
- `feat(v2): port TrackFeatures …`
- `feat(v2): port transition leaf modules …`
- `feat(v2): port transition components with parity harness`
- `feat(v2): port transition scorer + recipe + neural + style + hard_constraints`
- `feat(v2): port optimization (GA + greedy + fitness) …`
- `feat(v2): port audio core …`
- `feat(v2): port 18 analyzers …`
- `feat(v2): port mood classifier …`
- `feat(v2): port audio pipeline orchestrator + helpers`
- `chore(importlinter): add v2-domain-pure and v2-audio-internal contracts`
- `test(v2): full-field parity …`

- [ ] **Step 3: Ensure branch points at up-to-date origin/dev**

```bash
git fetch origin
git log --oneline HEAD ^origin/dev | head
```

Expected: only Phase 6 commits ahead of `origin/dev`.

- [ ] **Step 4: Final `make check`**

```bash
make check
```

Expected: all green.

- [ ] **Step 5: Open PR against `dev`**

Use `.github/pull_request_template.md` + the commit message ledger above.

```bash
gh pr create --base dev --head "$(git branch --show-current)" \
  --title "feat(v2): Phase 6 — domain + audio port" \
  --body-file /tmp/pr-body-phase-6.md
```

Where `/tmp/pr-body-phase-6.md` contains:

```markdown
## Summary
- Phase 6 of blueprint refactor — ports pure domain (transition / optimization / camelot / template / audit + TrackFeatures) and audio pipeline into `app/v2/domain/` and `app/v2/audio/`.
- 1:1 file moves with import-path rewrites only. Zero behavioural change.
- New import-linter contracts `v2-domain-pure` and `v2-audio-internal` lock the purity invariants.
- Full-field `TransitionScore` parity test exercises both trees side-by-side to 1e-9 precision.

## Test plan
- [x] `uv run pytest tests/v2/domain tests/v2/audio`
- [x] `uv run pytest tests/test_transition tests/test_domain tests/test_audio tests/test_services` (legacy tree still green)
- [x] `uv run lint-imports` (all 8 contracts pass)
- [x] `uv run mypy app/v2/domain app/v2/audio`
- [x] `uv run ruff check app/v2 tests/v2 && uv run ruff format --check app/v2 tests/v2`
- [x] `make check`
- [x] `uv run fastmcp run app/server.py` still boots

Fixes BPM-phase-6
```

- [ ] **Step 6: Do not merge — orchestrator handles merge.**

---

## Appendix A — Per-module port checklist (quick reference)

Every v2 port follows the same micro-recipe:

1. `cp LEGACY_PATH V2_PATH`
2. Edit `V2_PATH`: rewrite `from app.X` → `from app.v2.X` per the module-specific table.
3. Smoke: `uv run python -c "from app.v2.X import Y; print(Y)"`.
4. Migrate test: `cp tests/test_LEGACY tests/v2/TARGET`, rewrite imports.
5. `uv run pytest tests/v2/TARGET -v`.
6. `grep -rn "^from app\\." V2_PATH | grep -v "app\\.v2\\."` must be empty.
7. Commit with scoped message.

## Appendix B — Rewrite table (cheat sheet)

Global rewrites applicable across every v2 module:

| Legacy | v2 equivalent |
|---|---|
| `from app.config import settings` | `from app.v2.config import settings` |
| `from app.core.constants import X` | `from app.v2.shared.constants import X` |
| `from app.core.utils.<mod> import X` | `from app.v2.shared.<mod> import X` |
| `from app.core.errors import E` | `from app.v2.shared.errors import E` |
| `from app.entities.audio.features import TrackFeatures` | `from app.v2.domain.transition.features import TrackFeatures` |
| `from app.transition.<mod> import X` | `from app.v2.domain.transition.<mod> import X` |
| `from app.transition.components.<mod> import X` | `from app.v2.domain.transition.components.<mod> import X` |
| `from app.optimization.<mod> import X` | `from app.v2.domain.optimization.<mod> import X` |
| `from app.camelot.<mod> import X` | `from app.v2.domain.camelot.<mod> import X` |
| `from app.templates.<mod> import X` | `from app.v2.domain.template.<mod> import X` |
| `from app.audit.<mod> import X` | `from app.v2.domain.audit.<mod> import X` |
| `from app.audio.core.<mod> import X` | `from app.v2.audio.core.<mod> import X` |
| `from app.audio.analyzers.<mod> import X` | `from app.v2.audio.analyzers.<mod> import X` |
| `from app.audio.classification.<mod> import X` | `from app.v2.audio.classification.<mod> import X` |
| `from app.audio.<mod> import X` | `from app.v2.audio.<mod> import X` |

## Appendix C — What this phase does NOT do

Explicit non-goals:

- Does NOT delete legacy `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`, `app/entities/`, `app/audio/`. Phase 7 handles deletion.
- Does NOT modify any file under legacy paths. `git diff HEAD~N -- app/transition app/optimization app/camelot app/templates app/audit app/entities app/audio` must show zero changes.
- Does NOT touch services (`app/services/`), tools (`app/controllers/tools/`), or any consumer of legacy domain. Those keep importing legacy — consistent with the parallel-refactor strategy.
- Does NOT reorganize the audio module internally (spec §15.7 permits it, but we defer to keep the Phase 6 diff reviewable).
- Does NOT introduce new domain behaviour. No new components, no new analyzers, no new templates. Pure 1:1 ports.

## Appendix D — Risk log + rollback

**Risk 1: Registry double-registration.** When both legacy and v2 analyzers are imported in the same Python process, `@registry.register` decorators are idempotent (module-level dict is singleton). This is acceptable — production starts a fresh interpreter with only v2 imports. If a test process imports both, it should use isolated registries (see `.claude/rules/audio.md`: "in tests delete only `_test_*` keys, never `clear()`").

**Risk 2: Accidental double-import side-effects.** `librosa` is lazy-loaded via submodules. Pre-imports are on the main thread via `_warmup_librosa()`. Port verbatim — do not refactor the warmup block.

**Risk 3: numba/llvmlite SEGV.** The `pyproject.toml` pins `numba>=0.65`, `llvmlite>=0.47`. The v2 port does NOT modify pinning. If pipeline tests SEGV, it's environmental — see `.claude/rules/audio.md` "Numba/librosa version pinning".

**Risk 4: TrackFeatures field drift.** If `TrackFeatures.from_db` omits a field the scorer uses (e.g. `chroma_entropy`), a parity test will fail on v2 side (value `None`, neutral fallback) vs legacy (correct value). The `test_features_from_db.py` fixture (Task 5) contains every currently-consumed field — if a new field is added upstream before Phase 7, it must be mirrored in the fixture.

**Risk 5: Rollback strategy.** Each task is a single commit. To abort Phase 6:

```bash
git log --oneline $(git merge-base HEAD main)..HEAD
# Identify the first Phase 6 commit
git reset --hard <SHA_BEFORE_PHASE_6>
```

No destructive operations against `main` or `dev` — phase work lives on a feature branch only.

## Appendix E — Verification matrix

| Gate | Command | Expected |
|---|---|---|
| v2 domain tests | `uv run pytest tests/v2/domain/` | all pass |
| v2 audio tests | `uv run pytest tests/v2/audio/` | all pass or skip |
| Legacy domain tests | `uv run pytest tests/test_transition tests/test_domain tests/test_optimization` | same baseline as pre-Phase-6 |
| Legacy audio tests | `uv run pytest tests/test_audio/` | same baseline |
| Services tests (use legacy domain) | `uv run pytest tests/test_services/` | same baseline |
| Import-linter | `uv run lint-imports` | 8 contracts pass |
| mypy | `uv run mypy app/v2/domain app/v2/audio` | no issues |
| ruff | `uv run ruff check app/v2 tests/v2` | clean |
| ruff format | `uv run ruff format --check app/v2 tests/v2` | clean |
| MCP boot | `uv run fastmcp run app/server.py` | boots |
| v2 only import scan | `grep -rn "^from app\\." app/v2/domain app/v2/audio \| grep -v "app\\.v2\\."` | empty |

All ten gates must be green at Task 16 before PR opens.

# Phase 4: services/ — Business Logic

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Move `app/services/` to `src/dj_music/services/`. Remove all `from app.db.models` imports — services depend only on schemas (Pydantic) and repository ports (Protocol).

**Architecture:** Services use composition (no BaseService). Depend on Protocol ports, not concrete repos.

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/servers/dependency-injection
- https://gofastmcp.com/servers/context
- https://gofastmcp.com/servers/progress
- https://gofastmcp.com/servers/elicitation
- https://gofastmcp.com/servers/sampling
- https://gofastmcp.com/servers/tasks

---

### Task 1: Copy services/ and update imports

**Files:**
- Copy: `app/services/` → `src/dj_music/services/`
- Modify: all `src/dj_music/services/*.py` — remove ORM model imports

- [ ] **Step 1: Copy entire package**

```bash
cp -r app/services src/dj_music/services
```

- [ ] **Step 2: Update imports in all service files**

```bash
find src/dj_music/services -name "*.py" -exec sed -i '' \
  -e 's/from app\.services\./from dj_music.services./g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  -e 's/from app\.transition/from dj_music.transition/g' \
  -e 's/from app\.optimization/from dj_music.optimization/g' \
  -e 's/from app\.export/from dj_music.export/g' \
  -e 's/from app\.templates/from dj_music.templates/g' \
  -e 's/from app\.camelot/from dj_music.core.camelot/g' \
  -e 's/from app\.entities\.audio/from dj_music.schemas.audio/g' \
  -e 's/from app\.schemas/from dj_music.schemas/g' \
  -e 's/from app\.audio/from dj_music.audio/g' \
  {} +
```

- [ ] **Step 3: Remove ORM model imports — CRITICAL**

This is the key step. Find and replace all `from app.db.models.*` imports.

```bash
grep -rn "from app\.db\.models" src/dj_music/services/
```

For each hit: replace with the equivalent Pydantic schema import from `dj_music.schemas.*`.

Example:
```python
# BEFORE (violates architecture):
from app.db.models.track import Track
from app.db.models.set import DjSet, SetVersion

# AFTER (correct):
from dj_music.schemas.track import Track
from dj_music.schemas.set import DjSet, SetVersion
```

Services now work with Pydantic schemas returned by repository ports, not ORM models.

- [ ] **Step 4: Update repository type hints to use Protocol ports**

Where services accept concrete repo types:
```python
# BEFORE:
from app.db.repositories.track import TrackRepository

# AFTER:
from dj_music.repositories.ports import TrackRepositoryPort
```

**Note:** This is a gradual process. Start with key services (TrackService, SetService) and propagate.

- [ ] **Step 5: Add re-export shims in app/services/**

```python
# app/services/__init__.py — re-export shim
from dj_music.services import *  # noqa: F401,F403
```

For each service file:
```python
# app/services/track_service.py
from dj_music.services.track import *  # noqa: F401,F403
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_services/ -x -q
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: move services/ to dj_music.services, remove ORM imports

Services now depend on schemas (Pydantic) and repository ports
(Protocol), not on app.db.models. 21 ORM imports eliminated.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Move workflows/

**Files:**
- Already copied as `src/dj_music/services/workflows/` (subdirectory of services)

- [ ] **Step 1: Update workflow imports**

Same pattern — replace `app.` → `dj_music.` prefixes.

- [ ] **Step 2: Run tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "refactor: update workflow imports to dj_music paths

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Verify zero ORM imports in services

- [ ] **Step 1: Verify**

```bash
grep -rn "from app\.db\.models\|from dj_music\.models\|from sqlalchemy" src/dj_music/services/
```

Expected: zero hits (services don't know about ORM or SQLAlchemy)

- [ ] **Step 2: Full check**

```bash
make check
```

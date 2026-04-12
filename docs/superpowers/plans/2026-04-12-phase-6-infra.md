# Phase 6: models/, ym/, engines/, api/ — Infrastructure + Runtime

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Move remaining packages to `src/dj_music/`: ORM models, YM client, engines, REST API.

**Architecture:** Flat top-level packages. models/ = ORM only. ym/ = HTTP client. engines/ = runtime singletons. api/ = FastAPI REST wrapper.

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/servers/storage-backends
- https://gofastmcp.com/servers/lifespan
- https://gofastmcp.com/deployment/running-server
- https://gofastmcp.com/deployment/http
- https://gofastmcp.com/integrations/fastapi

---

### Task 1: Move models/ (ORM)

**Files:**
- Copy: `app/db/models/` → `src/dj_music/models/`

- [ ] **Step 1: Copy**

```bash
cp -r app/db/models src/dj_music/models
```

- [ ] **Step 2: Update internal imports**

```bash
find src/dj_music/models -name "*.py" -exec sed -i '' \
  -e 's/from app\.db\.models\./from dj_music.models./g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  {} +
```

- [ ] **Step 3: Update repositories to import from new models path**

```bash
find src/dj_music/repositories -name "*.py" -exec sed -i '' \
  -e 's/from app\.db\.models\./from dj_music.models./g' \
  {} +
```

- [ ] **Step 4: Shims in app/db/models/**

```python
# app/db/models/__init__.py
from dj_music.models import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests, commit**

```bash
uv run pytest tests/test_models/ tests/test_repositories/ -x -q
git add -A && git commit -m "refactor: move db/models/ to dj_music.models

ORM models on top-level. Repositories updated to import from
dj_music.models. Re-export shims in app/db/models/.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Move ym/ (Yandex Music client)

- [ ] **Step 1: Copy**

```bash
cp -r app/ym src/dj_music/ym
```

- [ ] **Step 2: Update imports**

```bash
find src/dj_music/ym -name "*.py" -exec sed -i '' \
  -e 's/from app\.ym\./from dj_music.ym./g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  {} +
```

- [ ] **Step 3: Shims, tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "refactor: move ym/ to dj_music.ym

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Move engines/

- [ ] **Step 1: Copy**

```bash
cp -r app/engines src/dj_music/engines
```

- [ ] **Step 2: Update imports, shims, tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "refactor: move engines/ to dj_music.engines

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Move api/ (FastAPI REST wrapper)

- [ ] **Step 1: Copy**

```bash
cp -r app/api src/dj_music/api
```

- [ ] **Step 2: Update imports**

```bash
find src/dj_music/api -name "*.py" -exec sed -i '' \
  -e 's/from app\.api\./from dj_music.api./g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  -e 's/from app\.server/from dj_music.server/g' \
  {} +
```

- [ ] **Step 3: Shims, tests, commit**

```bash
uv run pytest tests/test_api/ -x -q && git add -A && git commit -m "refactor: move api/ to dj_music.api

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Move migrations/

- [ ] **Step 1: Copy**

```bash
cp -r app/db/migrations src/dj_music/migrations
```

- [ ] **Step 2: Update alembic env.py to use new model paths**

Edit `src/dj_music/migrations/env.py`:
```python
from dj_music.models.base import Base
target_metadata = Base.metadata
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: move migrations/ to dj_music.migrations

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Final Phase 6 verification

- [ ] **Step 1: Verify all infra packages**

```bash
ls -d src/dj_music/models src/dj_music/ym src/dj_music/engines src/dj_music/api src/dj_music/migrations
```

- [ ] **Step 2: Full check**

```bash
make check
```

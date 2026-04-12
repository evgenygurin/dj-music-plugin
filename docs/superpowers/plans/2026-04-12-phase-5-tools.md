# Phase 5: tools/, prompts/, resources/, middleware/ — MCP Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Move MCP presentation layer from `app/controllers/` to flat top-level packages: `tools/`, `prompts/`, `resources/`, `middleware/`.

**Architecture:** FileSystemProvider scans `tools/` for @tool, `prompts/` for @prompt, `resources/` for @resource. Middleware in `middleware/`.

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/servers/server
- https://gofastmcp.com/servers/tools
- https://gofastmcp.com/servers/middleware
- https://gofastmcp.com/servers/pagination
- https://gofastmcp.com/servers/visibility
- https://gofastmcp.com/servers/composition
- https://gofastmcp.com/servers/testing
- https://gofastmcp.com/servers/providers/filesystem
- https://gofastmcp.com/servers/transforms/transforms
- https://gofastmcp.com/servers/transforms/namespace
- https://gofastmcp.com/servers/transforms/prompts-as-tools
- https://gofastmcp.com/servers/transforms/resources-as-tools

---

### Task 1: Move tools/

**Files:**
- Copy: `app/controllers/tools/` → `src/dj_music/tools/`
- Copy: `app/controllers/tools/_shared/` → `src/dj_music/tools/_shared/`
- Copy: `app/controllers/tools/yandex/` → `src/dj_music/tools/yandex/`
- Add: `src/dj_music/tools/visibility.py` (from `app/bootstrap/visibility.py`)

- [ ] **Step 1: Copy**

```bash
cp -r app/controllers/tools src/dj_music/tools
cp app/bootstrap/visibility.py src/dj_music/tools/visibility.py
```

- [ ] **Step 2: Update imports**

```bash
find src/dj_music/tools -name "*.py" -exec sed -i '' \
  -e 's/from app\.controllers\.tools\./from dj_music.tools./g' \
  -e 's/from app\.controllers\.dependencies\./from dj_music.di./g' \
  -e 's/from app\.controllers\./from dj_music.tools./g' \
  -e 's/from app\.services\./from dj_music.services./g' \
  -e 's/from app\.schemas/from dj_music.schemas/g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  {} +
```

- [ ] **Step 3: Shims in app/controllers/tools/**

- [ ] **Step 4: Run tool tests**

```bash
uv run pytest tests/test_tools/ tests/test_mcp/ -x -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move controllers/tools/ to dj_music.tools

FileSystemProvider will scan tools/ for @tool handlers.
Includes _shared/, yandex/, visibility.py.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Move prompts/

- [ ] **Step 1: Copy**
```bash
cp -r app/controllers/prompts src/dj_music/prompts
```

- [ ] **Step 2: Update imports, shims, test, commit**

```bash
git add -A && git commit -m "refactor: move prompts/ to dj_music.prompts

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Move resources/

- [ ] **Step 1: Copy**
```bash
cp -r app/controllers/resources src/dj_music/resources
```

- [ ] **Step 2: Update imports, shims, test, commit**

```bash
git add -A && git commit -m "refactor: move resources/ to dj_music.resources

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Create middleware/

**Files:**
- Create: `src/dj_music/middleware/__init__.py`
- Create: `src/dj_music/middleware/request_id.py`
- Create: `src/dj_music/middleware/registry.py` (from `app/bootstrap/middleware.py`)
- Create: `src/dj_music/middleware/transforms.py` (from `app/bootstrap/transforms.py`)
- Copy: `app/controllers/middleware.py` → `src/dj_music/middleware/error_handler.py`

- [ ] **Step 1: Create middleware package**

```bash
mkdir -p src/dj_music/middleware
```

- [ ] **Step 2: Create request_id middleware**

```python
# src/dj_music/middleware/request_id.py
"""RequestID middleware — generates trace ID, sets in contextvars."""

from contextvars import ContextVar
from uuid import uuid4

from fastmcp.server.middleware import Middleware, MiddlewareContext

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class RequestIdMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        request_id = str(uuid4())
        request_id_var.set(request_id)
        return await call_next(context)
```

- [ ] **Step 3: Copy and update registry + transforms**

```bash
cp app/bootstrap/middleware.py src/dj_music/middleware/registry.py
cp app/bootstrap/transforms.py src/dj_music/middleware/transforms.py
```

Update imports in copied files.

- [ ] **Step 4: Run tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "feat: create middleware/ with RequestId, registry, transforms

Custom RequestIdMiddleware with contextvars.
FastMCP built-in middleware registration in registry.py.
Namespace + P→T + R→T transforms in transforms.py.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Move elicitation + controller schemas

- [ ] **Step 1: Copy remaining controller files**

```bash
cp app/controllers/elicitation.py src/dj_music/tools/elicitation.py
cp -r app/controllers/schemas src/dj_music/tools/schemas
```

- [ ] **Step 2: Update imports, shims, test, commit**

---

### Task 6: Final Phase 5 verification

- [ ] **Step 1: Verify structure**

```bash
ls src/dj_music/tools/ src/dj_music/prompts/ src/dj_music/resources/ src/dj_music/middleware/
```

- [ ] **Step 2: Full check**

```bash
make check
```

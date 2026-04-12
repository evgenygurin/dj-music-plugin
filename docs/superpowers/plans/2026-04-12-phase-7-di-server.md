# Phase 7: di/ + server.py — DI Composition Root + Entry Point

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create `src/dj_music/di/` (DI factories) and `src/dj_music/server.py` (entry point with server builder). Add final import-linter contracts for `dj_music`.

**Architecture:** DI = composition root. 4-level chain: Session → Repo → Service → Tool. server.py assembles FastMCP with FileSystemProvider scanning tools/+prompts/+resources/.

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/servers/dependency-injection
- https://gofastmcp.com/servers/server
- https://gofastmcp.com/servers/providers/filesystem
- https://gofastmcp.com/integrations/claude-code

---

### Task 1: Create di/ package

**Files:**
- Create: `src/dj_music/di/__init__.py`
- Create: `src/dj_music/di/db.py`
- Create: `src/dj_music/di/repos.py`
- Create: `src/dj_music/di/services.py`
- Create: `src/dj_music/di/audio.py`
- Create: `src/dj_music/di/external.py`
- Create: `src/dj_music/di/uow.py`
- Create: `src/dj_music/di/lifespans.py` (from `app/bootstrap/lifespans.py`)
- Create: `src/dj_music/di/sampling.py` (from `app/bootstrap/sampling.py`)

- [ ] **Step 1: Copy DI factories from controllers/dependencies/**

```bash
mkdir -p src/dj_music/di
cp app/controllers/dependencies/db.py src/dj_music/di/db.py
cp app/controllers/dependencies/repos.py src/dj_music/di/repos.py
cp app/controllers/dependencies/services.py src/dj_music/di/services.py
cp app/controllers/dependencies/audio.py src/dj_music/di/audio.py
cp app/controllers/dependencies/external.py src/dj_music/di/external.py
cp app/controllers/dependencies/uow.py src/dj_music/di/uow.py
cp app/bootstrap/lifespans.py src/dj_music/di/lifespans.py
cp app/bootstrap/sampling.py src/dj_music/di/sampling.py
touch src/dj_music/di/__init__.py
```

- [ ] **Step 2: Update all imports**

```bash
find src/dj_music/di -name "*.py" -exec sed -i '' \
  -e 's/from app\.controllers\.dependencies\./from dj_music.di./g' \
  -e 's/from app\.bootstrap\./from dj_music.di./g' \
  -e 's/from app\.db\.repositories\./from dj_music.repositories./g' \
  -e 's/from app\.db\.session/from dj_music.repositories.session/g' \
  -e 's/from app\.services\./from dj_music.services./g' \
  -e 's/from app\.ym\./from dj_music.ym./g' \
  -e 's/from app\.audio\./from dj_music.audio./g' \
  -e 's/from app\.config/from dj_music.core.config/g' \
  -e 's/from app\.core\./from dj_music.core./g' \
  {} +
```

- [ ] **Step 3: Deduplicate build_ym_client()**

Ensure only ONE `build_ym_client()` in `di/external.py`:

```python
# src/dj_music/di/external.py
from dj_music.core.config import settings
from dj_music.ym.client import YandexMusicClient

def build_ym_client() -> YandexMusicClient:
    """Single factory for YM client — used in lifespan."""
    return YandexMusicClient(
        token=settings.ym_token,
        base_url=settings.ym_base_url,
    )
```

- [ ] **Step 4: Shims in app/controllers/dependencies/ and app/bootstrap/**

- [ ] **Step 5: Run tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "refactor: create dj_music.di — DI composition root

Factories for db session, repos, services, audio, external, uow.
Lifespans and sampling moved from bootstrap/.
build_ym_client() deduplicated to single factory.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create server.py entry point

**Files:**
- Create: `src/dj_music/server.py`

- [ ] **Step 1: Create server.py merging server_builder logic**

```python
# src/dj_music/server.py
"""FastMCP server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp run src/dj_music/server.py
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider

from dj_music.core.config import settings
from dj_music.core.logging import setup_logging
from dj_music.core.observability import setup_sentry
from dj_music.di.lifespans import build_server_lifespan
from dj_music.middleware.registry import register_middleware
from dj_music.middleware.transforms import build_transforms
from dj_music.tools.visibility import apply_visibility_policy

logger = logging.getLogger(__name__)

def build_mcp_server() -> FastMCP:
    """Build the production FastMCP server."""
    setup_logging(json=not settings.debug)
    error_callback = setup_sentry(settings.sentry_dsn)

    root = Path(__file__).resolve().parent

    mcp = FastMCP(
        name=settings.server_name,
        instructions="DJ techno music library management, set building, YM integration.",
        providers=[
            FileSystemProvider(root / "tools"),
            FileSystemProvider(root / "prompts"),
            FileSystemProvider(root / "resources"),
        ],
        transforms=build_transforms(),
        lifespan=build_server_lifespan(),
        list_page_size=settings.pagination_size,
        on_duplicate="warn",
        mask_error_details=not settings.debug,
    )

    register_middleware(mcp, error_callback=error_callback)
    apply_visibility_policy(mcp)
    return mcp

mcp = build_mcp_server()
```

- [ ] **Step 2: Update app/server.py to import from new location**

```python
# app/server.py — shim
from dj_music.server import mcp  # noqa: F401
```

- [ ] **Step 3: Verify server starts**

```bash
uv run fastmcp list src/dj_music/server.py --tools 2>&1 | head -10
```
Expected: lists tools

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: create dj_music.server — new entry point

FileSystemProvider scans tools/, prompts/, resources/.
Merges server_builder logic into server.py.
app/server.py shim for backward compat.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Add import-linter contracts for dj_music

**Files:**
- Modify: `.importlinter`

- [ ] **Step 1: Add all 6 contracts from spec**

Append to `.importlinter`:

```ini
# ── dj_music contracts ──────────────────────────────

[importlinter:contract:dj-schemas-pure]
name = Schemas must not depend on services or infrastructure
type = forbidden
source_modules = dj_music.schemas
forbidden_modules =
    dj_music.services
    dj_music.ym
    dj_music.tools
    dj_music.engines
    sqlalchemy
    httpx
    fastmcp
    fastapi

[importlinter:contract:dj-services-no-infra]
name = Services use ports not infrastructure
type = forbidden
source_modules =
    dj_music.services
    dj_music.services.workflows
forbidden_modules =
    dj_music.models
    dj_music.ym
    dj_music.tools
    sqlalchemy
    httpx
    fastmcp

[importlinter:contract:dj-core-leaf]
name = Core must not depend on any app layer
type = forbidden
source_modules = dj_music.core
forbidden_modules =
    dj_music.schemas
    dj_music.services
    dj_music.ym
    dj_music.tools
    dj_music.engines

[importlinter:contract:dj-tools-no-infra]
name = Tools depend on services not infrastructure
type = forbidden
source_modules =
    dj_music.tools
    dj_music.resources
    dj_music.prompts
forbidden_modules =
    dj_music.models
    dj_music.repositories

[importlinter:contract:dj-engines-no-transport]
name = Engines must not depend on tools or persistence
type = forbidden
source_modules = dj_music.engines
forbidden_modules =
    dj_music.tools
    dj_music.ym
    dj_music.repositories

[importlinter:contract:dj-pure-domain]
name = Transition, optimization, export, templates must be pure
type = forbidden
source_modules =
    dj_music.transition
    dj_music.optimization
    dj_music.export
    dj_music.templates
forbidden_modules =
    dj_music.models
    dj_music.repositories
    dj_music.services
    dj_music.tools
    dj_music.ym
    dj_music.engines
    sqlalchemy
    httpx
    fastmcp
```

- [ ] **Step 2: Run import-linter**

```bash
uv run lint-imports
```
Expected: all contracts pass (both app and dj_music)

- [ ] **Step 3: Commit**

```bash
git add .importlinter && git commit -m "feat: add 6 import-linter contracts for dj_music

schemas-pure, services-no-infra, core-leaf, tools-no-infra,
engines-no-transport, pure-domain.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

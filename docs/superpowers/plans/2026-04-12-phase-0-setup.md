# Phase 0: Project Setup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create `src/dj_music/` root package, update pyproject.toml, remove ghost directories, prepare import-linter.

**Architecture:** New root `src/dj_music/` alongside existing `app/`. Both coexist during migration.

**Tech Stack:** Python 3.12+, uv, pyproject.toml

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/getting-started/welcome
- https://gofastmcp.com/getting-started/installation
- https://gofastmcp.com/more/settings
- https://gofastmcp.com/deployment/server-configuration

---

### Task 1: Create src/dj_music/ root package

**Files:**
- Create: `src/dj_music/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/dj_music
```

- [ ] **Step 2: Create root __init__.py**

```python
# src/dj_music/__init__.py
"""DJ Music Plugin — MCP server for DJ techno music library management."""

__version__ = "0.7.0"
```

- [ ] **Step 3: Verify structure**

```bash
ls -la src/dj_music/
```
Expected: `__init__.py` exists

---

### Task 2: Update pyproject.toml for dual-package layout

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add src to packages**

Add `packages` configuration so both `app` and `dj_music` are importable:

```toml
[tool.setuptools.packages.find]
where = [".", "src"]

[tool.setuptools.package-dir]
dj_music = "src/dj_music"
```

Or if using uv/hatch, add to `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["app", "src/dj_music"]
```

- [ ] **Step 2: Verify both packages importable**

```bash
uv run python -c "import app; import dj_music; print('Both importable')"
```
Expected: `Both importable`

- [ ] **Step 3: Commit**

```bash
git add src/ pyproject.toml
git commit -m "chore: create src/dj_music/ root package for migration

Both app/ and dj_music/ coexist during migration.
Phase 8 will remove app/ once all code is moved.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Remove ghost directories

**Files:**
- Delete: `app/domain/` (contains only empty dirs + CLAUDE.md)
- Delete: `app/mcp/` (contains only CLAUDE.md + empty dirs)
- Delete: `app/repositories/` (contains only CLAUDE.md + empty dir)
- Delete: `app/models/` (contains only CLAUDE.md)
- Delete: `app/migrations/` (contains only CLAUDE.md + empty dir — real migrations are at `app/db/migrations/`)
- Delete: `app/utils/` (contains only CLAUDE.md)

- [ ] **Step 1: Verify ghost dirs contain no real code**

```bash
find app/domain app/mcp app/repositories app/models app/migrations app/utils -name "*.py" -not -name "CLAUDE.md" 2>/dev/null
```
Expected: empty output (no Python files)

- [ ] **Step 2: Remove ghost directories**

```bash
rm -rf app/domain app/mcp app/repositories app/models app/migrations app/utils
```

- [ ] **Step 3: Run tests to verify nothing broke**

```bash
uv run pytest -x -q 2>&1 | tail -5
```
Expected: all tests pass (ghost dirs had no code)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove 6 ghost directories (no code, only CLAUDE.md stubs)

app/domain/, app/mcp/, app/repositories/, app/models/,
app/migrations/, app/utils/ — artifacts from refactor-v2.
Real code lives in app/db/, app/controllers/, app/services/, etc.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Prepare import-linter for new root

**Files:**
- Modify: `.importlinter`

- [ ] **Step 1: Add dj_music to root_packages**

```ini
[importlinter]
root_packages =
    app
    dj_music
include_external_packages = True
```

Keep all existing contracts — they still apply to `app`.
New contracts for `dj_music` will be added in Phase 7 when all code is moved.

- [ ] **Step 2: Run import-linter**

```bash
uv run lint-imports
```
Expected: all existing contracts pass

- [ ] **Step 3: Run full check**

```bash
make check
```
Expected: lint + typecheck + arch + tests all pass

- [ ] **Step 4: Commit**

```bash
git add .importlinter
git commit -m "chore: add dj_music to import-linter root_packages

Prepares for migration. Existing app/ contracts unchanged.
New dj_music contracts will be added in Phase 7.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Final verification

- [ ] **Step 1: Verify complete Phase 0 state**

```bash
# Structure exists
test -f src/dj_music/__init__.py && echo "OK: root package"

# Ghost dirs removed
test ! -d app/domain && test ! -d app/mcp && echo "OK: ghosts removed"

# Both importable
uv run python -c "import app; import dj_music; print('OK: both importable')"

# All tests pass
uv run pytest -x -q 2>&1 | tail -3
```

Expected: all OK

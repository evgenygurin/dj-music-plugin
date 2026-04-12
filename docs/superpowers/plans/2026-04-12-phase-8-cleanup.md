# Phase 8: Cleanup — Remove shims, app/, update docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Remove all re-export shims, delete `app/` package, update all docs/rules/CLAUDE.md, final verification.

**Architecture:** After this phase, only `src/dj_music/` exists. `app/` is gone.

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/clients/client
- https://gofastmcp.com/clients/transports
- https://gofastmcp.com/cli/overview
- https://gofastmcp.com/cli/running
- https://gofastmcp.com/integrations/claude-code
- https://gofastmcp.com/integrations/mcp-json-configuration

---

### Task 1: Update all test imports

**Files:**
- Modify: all `tests/**/*.py`

- [ ] **Step 1: Bulk replace app → dj_music in tests**

```bash
find tests -name "*.py" -exec sed -i '' \
  -e 's/from app\./from dj_music./g' \
  -e 's/import app\./import dj_music./g' \
  {} +
```

- [ ] **Step 2: Handle special cases**

Some tests may import `app.server` or `app.api.server`:
```bash
grep -rn "from app\.\|import app\." tests/ | head -20
```

Fix remaining hits manually.

- [ ] **Step 3: Run all tests**

```bash
uv run pytest -x -q
```
Expected: all pass with `dj_music` imports

- [ ] **Step 4: Commit**

```bash
git add tests/ && git commit -m "refactor: update all test imports from app → dj_music

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Update panel MCP_HTTP_URL and start scripts

**Files:**
- Modify: `start.sh`
- Modify: `.mcp.json`
- Modify: `panel/.env.example`

- [ ] **Step 1: Update start.sh**

```bash
# Change uvicorn target
sed -i '' 's|app.api.server:api|dj_music.api.server:api|g' start.sh
```

- [ ] **Step 2: Update .mcp.json**

Update server command path:
```json
{
  "mcpServers": {
    "dj-music": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/dj_music/server.py"]
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add start.sh .mcp.json panel/.env.example
git commit -m "chore: update start scripts and MCP config for dj_music path

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Remove app/ package

**Files:**
- Delete: `app/` (entire directory)

- [ ] **Step 1: Verify no remaining imports from app/**

```bash
grep -rn "from app\.\|import app\." src/ tests/ panel/ start.sh .mcp.json 2>/dev/null
```
Expected: zero hits

- [ ] **Step 2: Remove app/**

```bash
rm -rf app/
```

- [ ] **Step 3: Remove app from import-linter**

Edit `.importlinter` — remove `app` from `root_packages` and all `app.*` contracts:

```ini
[importlinter]
root_packages =
    dj_music
include_external_packages = True
```

Remove all old `[importlinter:contract:services-no-mcp]` etc. contracts that reference `app.`.

- [ ] **Step 4: Update pyproject.toml**

Remove `app` from packages, keep only `src/dj_music`:

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 5: Run full check**

```bash
uv run pytest -x -q
uv run lint-imports
uv run ruff check
uv run mypy src/dj_music/
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: remove app/ package — migration complete

All code now lives in src/dj_music/. 6 import-linter contracts
enforce dependency rule. Zero re-export shims remaining.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Update CLAUDE.md and .claude/rules/

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.claude/rules/*.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update CLAUDE.md**

Replace all `app/` paths with `src/dj_music/`:
- `app/controllers/` → `tools/`, `prompts/`, `resources/`
- `app/services/` → `services/`
- `app/db/models/` → `models/`
- `app/db/repositories/` → `repositories/`
- `app/core/` → `core/`
- `app/config.py` → `core/config/`
- `app/server.py` → `server.py`
- `app/bootstrap/` → `di/` + `middleware/`

Update architecture diagram, commands, and file references.

- [ ] **Step 2: Update .claude/rules/ files**

Each rule file references `app/` paths — update to `dj_music/`:
- `tools.md`, `services.md`, `repositories.md`, `models.md`
- `audio.md`, `panel.md`, `config.md`, `tests.md`
- `rest-api.md`, `resources.md`, `gotchas.md`

- [ ] **Step 3: Update docs/architecture.md**

Replace architecture diagram with new flat structure.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs: update all docs/rules for dj_music structure

CLAUDE.md, .claude/rules/, docs/architecture.md updated.
All app/ references replaced with src/dj_music/ paths.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Final verification

- [ ] **Step 1: Verify no app/ references remain**

```bash
# No app/ directory
test ! -d app && echo "OK: app/ removed"

# No app imports in code
grep -rn "from app\.\|import app\." src/ tests/ 2>/dev/null | wc -l
# Expected: 0

# No app in import-linter
grep "app\." .importlinter | wc -l
# Expected: 0
```

- [ ] **Step 2: Verify structure**

```bash
ls src/dj_music/
```

Expected:
```text
__init__.py  api/  audio/  core/  di/  engines/  export/
middleware/  migrations/  models/  optimization/  prompts/
repositories/  resources/  schemas/  server.py  services/
templates/  tools/  transition/  ym/
```

- [ ] **Step 3: Run everything**

```bash
make check
uv run fastmcp list src/dj_music/server.py --tools 2>&1 | wc -l
```

Expected: all checks pass, ~50+ tools listed

- [ ] **Step 4: Final commit**

```bash
git add -A && git commit -m "chore: Clean Architecture migration complete

src/dj_music/ — 20 top-level packages, 6 import-linter contracts,
zero ORM imports in services, Entity-First schemas, flat structure.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

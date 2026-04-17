# Phase 7 — Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atomically swap `app/v2/` into `app/`, delete ~9000 LOC of legacy code and 15 dead DB tables, rewrite all project documentation, and tag `v1.0.0 "The Blueprint"` — all while keeping BFS/L5 VM campaigns running with at most one short graceful downtime window.

**Architecture:** This is a DESTRUCTIVE phase. Every task is either a file move, a delete, a docs rewrite, or a verification checkpoint. Atomicity is enforced by branching strategy: all work happens on `cutover/v1.0.0`, merged into `dev` only after green `make check` + VM smoke test, then PR'd `dev → main` (never direct push — project rule). Every destructive task has a rollback procedure that reverts via `git reset --hard <pre-task-SHA>` or `git revert`. `git mv` is used everywhere it preserves history.

**Tech Stack:** Python 3.12, git ≥ 2.42 (for reliable rename detection), SQLAlchemy 2.0 async, Alembic, FastMCP v3+, pytest, ruff, mypy, import-linter, gh CLI, ssh (VM operations).

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§13, 14, 15.8, 17, 18.1.

---

## File Structure

This phase *removes* far more than it creates. Below is a summary of moves, deletions, and rewrites — one table per bucket.

### Files deleted outright (per blueprint §13.1)

```text
app/engines/                       # 8 files — experimental dead code
app/ym/                            # 5 files — replaced by app/v2/providers/yandex/
app/infrastructure/                # 2 files — unused stub
app/api/services/ym_audio_proxy.py # Panel goes direct; no proxy
app/api/services/tool_registry.py  # Use MCP list_tools directly
app/api/services/signed_url_cache.py
app/controllers/tools/decks.py     # 8 tools — Engines-dependent
app/controllers/tools/mixer.py     # 7 tools — Engines-dependent
app/controllers/tools/monitoring.py
app/controllers/tools/audio_atomic.py
app/controllers/tools/run_tool.py  # BM25SearchTransform replaces
app/schemas/deck.py
app/schemas/mixer.py
app/services/                      # entire tree, 39 files
app/controllers/dependencies/      # replaced by app/v2/server/di.py
app/controllers/tools/             # flat tree replaced by app/v2/tools/
app/clients/                       # empty stub
app/bootstrap/                     # replaced by app/v2/server/
app/api/                           # replaced by app/v2/rest/
app/ym/                            # redundant: also in bullet above
app/providers/                     # old re-exports; v2 has real impl
app/schemas/                       # replaced by app/v2/schemas/
app/entities/                      # merged into app/v2/domain/
app/transition/                    # moved to app/v2/domain/transition/
app/optimization/                  # moved to app/v2/domain/optimization/
app/camelot/                       # moved to app/v2/domain/camelot/
app/templates/                     # moved to app/v2/domain/template/
app/audit/                         # moved to app/v2/domain/audit/
app/audio/                         # re-homed under app/v2/audio/
app/controllers/                   # dirs emptied → removed
app/core/                          # replaced by app/v2/shared/
app/db/                            # replaced by app/v2/db/ + app/v2/models/ + app/v2/repositories/
app/config.py                      # replaced by app/v2/config/
app/server.py                      # replaced by app/v2/server.py
app/telemetry.py                   # merged into app/v2/server/observability.py
app/_version.py                    # replaced by app/v2/_version.py
```

### Renamed (atomic swap, preserves history via `git mv`)

```text
app/           → app/v1_legacy/    # stash for one release cycle
app/v2/        → app/              # the new home
tests/v2/      → tests/             # replace legacy tests directory entirely
tests/         → tests/v1_legacy/  # same stash pattern (pre-swap)
```

(Net effect: `app/v2/` becomes `app/`, `tests/v2/` becomes `tests/`, and legacy equivalents are staged under `*_legacy/` dirs for one release cycle before final deletion.)

### DB tables dropped (Alembic migration)

```text
spotify_metadata
spotify_album_metadata
spotify_artist_metadata
spotify_playlist_metadata
spotify_audio_features
beatport_metadata
soundcloud_metadata
embeddings
transition_candidates
dj_saved_loops
dj_cue_points
dj_beatgrid_change_points
dj_set_constraints
dj_set_feedback
labels
track_labels
app_exports
```

> Post-drop: **31 live tables** (down from 44).
> NOTE: `labels` + `track_labels` count as two tables in the migration, but blueprint §13.2 lists them as one line. Total table count dropped: 16 (blueprint rounds to "15"). Both counts are reconciled in Task 6.

### Files rewritten (docs)

```text
CLAUDE.md                          # project root — full rewrite
docs/architecture.md               # full rewrite
docs/tool-catalog.md               # full rewrite
docs/structure.md                  # full rewrite
docs/panel-guide.md                # minor update (panel not refactored)
docs/audio-pipeline.md             # update paths only
docs/domain-glossary.md            # update paths only
docs/transition-scoring.md         # update paths (no semantic change)
docs/ym-api-guide.md               # rename → docs/provider-yandex-guide.md, update paths
.claude/rules/audio.md             # path updates
.claude/rules/bootstrap.md         # rewrite → app/server/
.claude/rules/config.md            # rewrite → app/config/
.claude/rules/entities.md          # rewrite → app/domain/
.claude/rules/gotchas.md           # path updates
.claude/rules/logging.md           # path updates
.claude/rules/models.md            # rewrite → app/models/
.claude/rules/optimization.md      # rewrite → app/domain/optimization/
.claude/rules/panel.md             # unchanged paths
.claude/rules/prompts.md           # rewrite → app/prompts/
.claude/rules/providers.md         # rewrite → app/providers/ + app/registry/provider.py
.claude/rules/rest-api.md          # rewrite → app/rest/
.claude/rules/resources.md         # rewrite → app/resources/
.claude/rules/repositories.md      # rewrite → app/repositories/
.claude/rules/services.md          # DELETED — no services layer anymore
.claude/rules/supabase.md          # unchanged
.claude/rules/tests.md             # path updates
.claude/rules/tools.md             # rewrite — 13 tools instead of 88
.claude/rules/transitions.md       # path updates only
.claude/rules/workflows.md         # DELETED — no workflows layer anymore
.claude/rules/ym.md                # rename → .claude/rules/provider-yandex.md
.claude/rules/git.md               # unchanged
.claude/rules/testing.md           # unchanged
CHANGELOG.md                       # add [1.0.0] entry
```

### Config files updated

```text
pyproject.toml                     # [project.scripts], [tool.setuptools]...
alembic.ini                        # script_location stays, but remove any reference to old paths in env.py
app/db/migrations/env.py           # -> now lives at app/db/migrations/env.py after swap; re-target target_metadata
start.sh                           # entrypoints (app.server → app.server)
scripts/*.py                       # all scripts re-import from app.* (no more app.v2.*)
scripts/compat_shims.py            # NEW — one-release bridging of old tool names
panel/.env.example                 # unchanged (MCP_HTTP_URL semantic preserved)
Makefile                           # unchanged if targets already use app/
.githooks/pre-push                 # unchanged
.importlinter                      # remove "v2-backflow-gate", all app.v2.* → app.*; keep domain-pure etc.
.claude/settings.json              # no change
```

---

## Task 1: Pre-flight — verify all Phase 1-6 work is merged and healthy

**Files:** none (verification only)

**Rollback:** N/A — purely observational.

- [ ] **Step 1: Confirm current branch + clean tree**

```bash
git fetch --all --prune
git status
git branch --show-current
```

Expected: working tree clean; current branch is `dev`; `origin/dev` is fully fetched.

- [ ] **Step 2: Verify all Phase 1–6 branches are merged into `dev`**

```bash
for phase in phase-1-foundation phase-2-persistence phase-3-tools \
             phase-4-resources-prompts phase-5-server phase-6-domain-audio; do
  printf "%-30s " "$phase"
  if git merge-base --is-ancestor "refactor/${phase}" dev 2>/dev/null; then
    echo "MERGED"
  else
    echo "MISSING — STOP"
  fi
done
```

Expected: `MERGED` for all six. If any missing → **abort Phase 7** and resolve.

- [ ] **Step 3: Confirm `make check` green on `dev`**

```bash
git checkout dev
git pull --ff-only
make check
```

Expected: all of `ruff check`, `ruff format --check`, `mypy app/`, `mypy app/v2/`, `lint-imports`, `pytest` pass. Time budget: 5–10 min.

- [ ] **Step 4: Confirm BFS/L5 campaign healthy on VM**

```bash
ssh root@155.212.128.27 "systemctl is-active dj-bfs dj-l5 && \
  tail -n 20 /var/log/dj-bfs.log && \
  tail -n 20 /var/log/dj-l5.log"
```

Expected: both services `active`; log tails show recent progress timestamps within last 10 min. If degraded → pause campaigns via `systemctl stop` before continuing; do not start cutover on a broken VM.

- [ ] **Step 5: Confirm staging DB health + backup**

```bash
# Supabase project ID (per memory): bowosphlnghhgaulcyfm
uv run python -c "
from app.v2.config import get_settings
import asyncio, asyncpg
async def main():
    s = get_settings()
    conn = await asyncpg.connect(s.database.url.replace('postgresql+asyncpg://','postgresql://'))
    print(await conn.fetchval('select now()'))
    await conn.close()
asyncio.run(main())
"
```

Expected: a recent UTC timestamp.

- [ ] **Step 6: Trigger a fresh Supabase logical backup**

```bash
# Managed by Supabase — manual PITR point just before destructive phase.
# If gh-managed: gh workflow run supabase-backup.yml
# Otherwise (default for this repo): use Supabase dashboard → Database → Backups → "Take backup now"
# Record the backup ID in /tmp/phase-7-backup-id.txt for rollback reference.
```

Expected: a backup snapshot newer than the pre-flight check. **Do NOT proceed without this.**

- [ ] **Step 7: Record pre-cutover SHAs for rollback**

```bash
git rev-parse dev > /tmp/phase-7-pre-dev-sha.txt
git rev-parse origin/main > /tmp/phase-7-pre-main-sha.txt
cat /tmp/phase-7-pre-dev-sha.txt /tmp/phase-7-pre-main-sha.txt
```

Expected: two 40-char SHAs, stored for emergency revert.

- [ ] **Step 8: Capture current tool list for smoke-test comparison**

```bash
uv run python -c "
import asyncio, json
from app.server import build_mcp_server
from fastmcp.client import Client

async def main():
    mcp = build_mcp_server()
    async with Client(mcp) as c:
        tools = sorted(t.name for t in await c.list_tools())
        print(json.dumps(tools, indent=2))
asyncio.run(main())
" > /tmp/phase-7-pre-tools.json
wc -l /tmp/phase-7-pre-tools.json
```

Expected: current `app/` (pre-swap) tool count. Used later to verify the new 13-tool surface still covers everything via shims.

- [ ] **Step 9: Print decision summary and STOP for user confirmation**

```text
Pre-flight summary:
  Phase 1–6 merged:  YES
  make check green:  YES
  BFS/L5 healthy:    YES
  DB backup taken:   <backup-id>
  Pre-dev SHA:       <sha>
  Old tool count:    <n>
  Current branch:    dev
Proceed with Phase 7 cutover? Requires user GO signal.
```

This step does not commit anything. No rollback needed.

---

## Task 2: Create `cutover/v1.0.0` branch

**Files:** none (git-only).

**Rollback:** `git branch -D cutover/v1.0.0` (safe — no commits yet).

- [ ] **Step 1: Create branch from verified `dev`**

```bash
git checkout dev
git checkout -b cutover/v1.0.0
```

Expected: branch `cutover/v1.0.0` created and checked out; tracks nothing yet.

- [ ] **Step 2: Push empty branch as a tracking anchor**

```bash
git push -u origin cutover/v1.0.0
```

Expected: remote branch created. All Phase 7 work commits here until final merge.

- [ ] **Step 3: Verify `cutover/v1.0.0` is exactly `dev` HEAD**

```bash
git diff dev..cutover/v1.0.0 --stat
```

Expected: empty diff (identical trees).

---

## Task 3: Write `scripts/compat_shims.py` — bridging old tool names

**Files:**
- Create: `scripts/compat_shims.py`
- Test: `tests/scripts/test_compat_shims.py`
- Modify: `scripts/vm_import_and_analyze.py`, `scripts/vm_analyze.py`, `scripts/ym_bfs_expand.py`

**Rollback:** `git revert <commit-sha>` (single atomic commit at end of task).

**Purpose:** VM campaigns call ~8 legacy tools by name (e.g. `import_tracks`, `analyze_track`, `classify_mood`, `find_similar_tracks`). After cutover, those tools are replaced by `entity_*` dispatches with different signatures. The shim layer translates old calls → new calls **for one release cycle only**, so BFS/L5 keeps working without stopping to rewrite campaign scripts in the same PR.

- [ ] **Step 1: Enumerate legacy tool names called from `scripts/`**

```bash
grep -rhoE "(mcp_call|call_tool|session.call_tool|client\.call_tool)\s*\(\s*['\"][a-z_]+['\"]" scripts/ \
  | grep -oE "['\"][a-z_]+['\"]" | sort -u > /tmp/phase-7-script-tool-names.txt
cat /tmp/phase-7-script-tool-names.txt
```

Expected: ~8–12 tool names such as `import_tracks`, `analyze_track`, `analyze_batch`, `classify_mood`, `find_similar_tracks`, `get_library_stats`, `download_tracks`, `audit_playlist`.

- [ ] **Step 2: Write failing test for each shim**

```python
# tests/scripts/test_compat_shims.py
"""Tests for legacy tool-name → new-tool translation shims.

Each test constructs input in the old shape and asserts the shim dispatches
to the right new tool with the right args.
"""
import pytest
from scripts.compat_shims import dispatch_legacy

LEGACY = [
    "import_tracks",
    "analyze_track",
    "analyze_batch",
    "classify_mood",
    "find_similar_tracks",
    "download_tracks",
    "get_library_stats",
    "audit_playlist",
]

@pytest.mark.parametrize("name", LEGACY)
def test_shim_registered(name: str) -> None:
    assert dispatch_legacy.is_registered(name), f"No shim for {name}"

@pytest.mark.asyncio
async def test_import_tracks_shim_calls_entity_create(fake_client) -> None:
    await dispatch_legacy(fake_client, "import_tracks",
                          {"track_refs": ["ym:123"], "playlist_id": 42})
    assert fake_client.last_call == ("entity_create",
        {"entity": "track",
         "data": {"provider_refs": ["ym:123"]},
         "link": {"playlist_id": 42}})

@pytest.mark.asyncio
async def test_analyze_track_shim_calls_compute(fake_client) -> None:
    await dispatch_legacy(fake_client, "analyze_track", {"track_id": 7, "level": 3})
    assert fake_client.last_call == ("compute_analyze",
        {"entity": "track_features", "ids": [7], "level": 3})

@pytest.mark.asyncio
async def test_classify_mood_shim(fake_client) -> None:
    await dispatch_legacy(fake_client, "classify_mood", {"track_ids": [1, 2]})
    assert fake_client.last_call == ("compute_classify",
        {"entity": "track_features", "ids": [1, 2]})

@pytest.mark.asyncio
async def test_find_similar_tracks_shim(fake_client) -> None:
    await dispatch_legacy(fake_client, "find_similar_tracks",
                          {"track_id": 9, "limit": 20})
    assert fake_client.last_call == ("provider_search",
        {"provider": "yandex", "kind": "similar", "seed_track_id": 9, "limit": 20})
```

Create `tests/scripts/__init__.py` and a `conftest.py` exposing a `fake_client` fixture that records the last `call_tool()` invocation.

- [ ] **Step 3: Implement `scripts/compat_shims.py`**

```python
"""Legacy tool-name shim layer.

Bridges old MCP tool names (88-tool surface, pre-v1.0.0) onto the new
13-tool blueprint surface (entity_*, provider_*, compute_*, ...) for one
release cycle. Deleted after the post-cutover sunset (see plan Task 19).

Used only from scripts/. NOT imported by app/ — production code always
calls new tools directly.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ShimFn = Callable[["Client", dict[str, Any]], Awaitable[Any]]
_REGISTRY: dict[str, ShimFn] = {}

def register(name: str) -> Callable[[ShimFn], ShimFn]:
    def deco(fn: ShimFn) -> ShimFn:
        if name in _REGISTRY:
            raise ValueError(f"Shim already registered: {name}")
        _REGISTRY[name] = fn
        return fn
    return deco

async def dispatch_legacy(client: "Client", name: str, args: dict[str, Any]) -> Any:
    """Call `name` on `client`, translating if it's a legacy name."""
    shim = _REGISTRY.get(name)
    if shim is None:
        # Pass-through — `name` is already a new (blueprint) tool name.
        return await client.call_tool(name, args)
    return await shim(client, args)

dispatch_legacy.is_registered = lambda n: n in _REGISTRY  # type: ignore[attr-defined]

# ── Per-tool shims ──────────────────────────────────────────────────

@register("import_tracks")
async def _import_tracks(client, args):
    refs = args.pop("track_refs", [])
    playlist_id = args.pop("playlist_id", None)
    payload = {"entity": "track", "data": {"provider_refs": refs}}
    if playlist_id is not None:
        payload["link"] = {"playlist_id": playlist_id}
    return await client.call_tool("entity_create", payload)

@register("analyze_track")
async def _analyze_track(client, args):
    tid = args["track_id"]
    return await client.call_tool("compute_analyze", {
        "entity": "track_features",
        "ids": [tid],
        "level": args.get("level", 3),
    })

@register("analyze_batch")
async def _analyze_batch(client, args):
    ids = args.get("track_ids") or []
    return await client.call_tool("compute_analyze", {
        "entity": "track_features",
        "ids": ids,
        "level": args.get("level", 3),
    })

@register("classify_mood")
async def _classify_mood(client, args):
    ids = args.get("track_ids") or []
    return await client.call_tool("compute_classify", {
        "entity": "track_features",
        "ids": ids,
    })

@register("find_similar_tracks")
async def _find_similar(client, args):
    return await client.call_tool("provider_search", {
        "provider": "yandex",
        "kind": "similar",
        "seed_track_id": args["track_id"],
        "limit": args.get("limit", 20),
    })

@register("download_tracks")
async def _download_tracks(client, args):
    refs = args.get("track_refs") or []
    return await client.call_tool("entity_create", {
        "entity": "audio_file",
        "data": {"provider_refs": refs},
    })

@register("get_library_stats")
async def _get_library_stats(client, args):
    return await client.call_tool("entity_aggregate", {
        "entity": "track",
        "group_by": ["status", "mood"],
    })

@register("audit_playlist")
async def _audit_playlist(client, args):
    return await client.read_resource(
        f"playlist://{args['playlist_id']}/audit"
    )
```

- [ ] **Step 4: Patch campaign scripts to route through `dispatch_legacy`**

In each of `scripts/vm_import_and_analyze.py`, `scripts/vm_analyze.py`, `scripts/ym_bfs_expand.py`, replace direct `await client.call_tool(name, args)` calls with:

```python
from scripts.compat_shims import dispatch_legacy
...
result = await dispatch_legacy(client, name, args)
```

- [ ] **Step 5: Run shim tests**

```bash
uv run pytest tests/scripts/ -v
```

Expected: all parametrized + per-shim tests green.

- [ ] **Step 6: Dry-run a shim end-to-end against current (pre-cutover) `app/`**

```bash
uv run python -c "
import asyncio
from fastmcp.client import Client
from app.server import build_mcp_server
from scripts.compat_shims import dispatch_legacy

async def main():
    mcp = build_mcp_server()
    async with Client(mcp) as c:
        # Still talks to the old tool (pass-through), because current tree
        # has 'import_tracks' registered. After cutover, the shim rewrites to
        # entity_create. Either path must work.
        await dispatch_legacy(c, 'get_library_stats', {})
        print('shim pass-through OK')
asyncio.run(main())
"
```

Expected: `shim pass-through OK`.

- [ ] **Step 7: Commit**

```bash
git add scripts/compat_shims.py scripts/vm_import_and_analyze.py scripts/vm_analyze.py \
        scripts/ym_bfs_expand.py tests/scripts/
git commit -m "chore(scripts): add compat shims for legacy tool names

Bridges old 88-tool surface to new 13-tool blueprint for one release.
BFS/L5 campaigns keep running through cutover unchanged.
Shims deleted in post-v1.0.0 sunset (see phase-7 plan Task 19)."
```

**Rollback for this task:**
```bash
git revert HEAD                    # removes shim layer, reverts scripts
```

---

## Task 4: Stop BFS/L5 on VM gracefully

**Files:** none (remote operations).

**Rollback:** immediately restart with `systemctl start dj-bfs dj-l5`.

- [ ] **Step 1: Send `SIGTERM` to each process (graceful drain)**

```bash
ssh root@155.212.128.27 "systemctl stop dj-bfs && systemctl stop dj-l5"
```

Expected: `systemd` reports both services `inactive (dead)` within 30–60 s (graceful drain — any in-flight track finishes).

- [ ] **Step 2: Verify no stragglers**

```bash
ssh root@155.212.128.27 "pgrep -fa vm_import_and_analyze || true; \
                          pgrep -fa vm_analyze || true; \
                          pgrep -fa ym_bfs_expand || true"
```

Expected: empty output. If anything lingers, `kill -TERM <pid>` and wait.

- [ ] **Step 3: Tag the last processed track ID for resume verification**

```bash
ssh root@155.212.128.27 "
  grep -oE 'track=[0-9]+' /var/log/dj-bfs.log | tail -n 1 > /tmp/bfs-last-track.txt
  grep -oE 'track=[0-9]+' /var/log/dj-l5.log  | tail -n 1 > /tmp/l5-last-track.txt
  cat /tmp/bfs-last-track.txt /tmp/l5-last-track.txt
"
```

Expected: two `track=<id>` lines. Used in Task 18 smoke test to confirm restart picks up from here.

- [ ] **Step 4: Announce downtime window in ops channel**

```text
Cutover window opening: BFS/L5 paused.
ETA to restart: ~90 min (Tasks 5–18).
Reference: cutover/v1.0.0 branch.
```

No commit.

---

## Task 5: Update documentation — `CLAUDE.md` rewrite

**Files:**
- Modify: `CLAUDE.md` (full rewrite)

**Rollback:** `git checkout HEAD -- CLAUDE.md`.

**Note on order:** documentation rewrites come BEFORE the filesystem swap so that the swap commit and the docs commit are separately reviewable. The new docs describe the post-swap layout and will pass `make check` (docs are not compiled).

- [ ] **Step 1: Read current `CLAUDE.md` for tone and structure**

```bash
wc -l CLAUDE.md
sed -n '1,80p' CLAUDE.md
```

- [ ] **Step 2: Rewrite `CLAUDE.md`**

Replace the whole file with a version describing the new tree. Key sections (preserve the project's existing tone — Russian-first):

```markdown
# DJ Music Plugin

// Всегда думай по-русски и отвечай по-русски, если только явно не просят другое.

## Quick Start

```bash
uv sync --all-extras
make check
uv run fastmcp run app/server.py --reload
cd panel && bun dev
./start.sh
```

## Цель проекта

MCP-сервер для управления DJ techno библиотекой, построения оптимизированных сетов и интеграции с платформами музыки. Включает веб-панель для мониторинга и аналитики.

- Спецификация: @REQUIREMENTS.md
- Blueprint: @docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md

## Архитектура v1.0.0 (Blueprint)

```text
Interface:   app/tools/  (13 generic tools)
             app/resources/  (18 resources)
             app/prompts/  (6 prompt workflows)
             app/rest/  (thin FastAPI wrapper)
Registry:    app/registry/  (EntityRegistry, ProviderRegistry)
Handlers:    app/handlers/  (side-effecting business logic)
Domain:      app/domain/  (transition, optimization, camelot, template, audit)
Persistence: app/models/, app/repositories/, app/db/
Providers:   app/providers/yandex/  (MusicProvider adapter)
Audio:       app/audio/  (analyzers, pipeline)
Shared:      app/shared/  (errors, ids, time, pagination, filters)
Config:      app/config/  (split by domain)
Server:      app/server/  (FastMCP composition root, middleware, DI)
```

**Dependency rule (закреплено import-linter):**
- `tools → handlers → repositories → models`
- `domain/*` pure (no DB / HTTP / FastMCP / SQLAlchemy)
- `providers/*` implement `app/registry/provider.py:Provider` protocol
- `shared/*` leaf — not importable by anything in `app/`

## Документация

- @docs/architecture.md — слои, data flow, middleware pipeline
- @docs/domain-glossary.md — DJ терминология
- @docs/tool-catalog.md — 13 generic tools (entity_*, provider_*, compute_*, ...)
- @docs/audio-pipeline.md — анализаторы, pipeline, mood classifier
- @docs/provider-yandex-guide.md — YM provider adapter
- @docs/transition-scoring.md — 6-компонентная формула
- @docs/panel-guide.md — Panel архитектура
- @docs/structure.md — полная структура + DB schema

## Команды

```bash
uv run pytest -v
uv run ruff check && uv run ruff format --check
uv run mypy app/
uv run lint-imports
uv run alembic upgrade head
make check
```

## Правила

- Один файл = одна ответственность.
- Все datetime-операции через `app/shared/time.py`.
- Magic numbers запрещены — только `settings.*` и `app/shared/constants.py`.
- Context injection: `ctx: Context = CurrentContext()  # noqa: B008`.
- DI параметры: `svc: MyHandler = Depends(get_my_handler)`.
- Tools: описания ≤50 слов.
- Prompts: возвращают `PromptResult(messages=[...], description="...")`.
- Resources: возвращают `dict[str, Any]` (FastMCP сериализует).
- Visibility: per-session через `ctx.enable_components(tags={...})`.
- Structured output: Pydantic-модели из `app/schemas/`.
```bash

Keep sections "Команды" and "Правила" — these are internal convention notes; update only the paths (e.g. `app/core/utils/time.py` → `app/shared/time.py`, `app/core/constants.py` → `app/shared/constants.py`).

- [ ] **Step 3: Verify front-matter still loads in Claude Code harness**

```bash
head -n 20 CLAUDE.md
grep -c "^## " CLAUDE.md         # expect 6–8 sections
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): rewrite for v1.0.0 blueprint architecture

Describes the post-cutover tree (app/tools/, app/handlers/, app/domain/,
app/registry/, app/providers/). No path references to app/v2/ anymore.
Keeps existing tone: Russian-first, Quick Start, command table."
```

---

## Task 6: Rewrite `docs/architecture.md`

**Files:**
- Modify: `docs/architecture.md` (full rewrite)

**Rollback:** `git checkout HEAD -- docs/architecture.md`.

- [ ] **Step 1: Rewrite with new tree**

Sections to include (map each to blueprint §):

1. System Overview ASCII diagram — updated to show `app/tools/`, `app/handlers/`, `app/registry/`, `app/providers/yandex/`, `app/domain/`. Replace old boxes (`services/`, `controllers/`) with new ones.
2. Panel & REST API Layer — minimal changes; references `app/rest/` instead of `app/api/`.
3. Middleware Pipeline — reference `app/server/middleware/*.py` (§11 of blueprint has the canonical 16-entry list; copy verbatim).
4. Data Flow: Tool Call Lifecycle — update DI chain to `app/server/di.py` and remove `controllers/dependencies/`.
5. Startup Flow — `fastmcp run app/server.py`; `app/server/lifespan.py` composes DB + provider + analyzer + cache.
6. Key Architectural Decisions — extend the table from the old doc with: EntityRegistry, ProviderRegistry, 13 generic tools, Django-style filters, UoW pattern.

- [ ] **Step 2: Validate section anchors referenced from other docs**

```bash
grep -rhn "docs/architecture.md#" docs/ .claude/ CLAUDE.md || true
```

Fix any references that hit sections that were renamed in the rewrite.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs(architecture): rewrite for v1.0.0 blueprint

New diagram, middleware pipeline per blueprint §11, Tool Call Lifecycle
updated for EntityRegistry + handler dispatch. Decisions table extended
with the seven blueprint-era architectural choices."
```

---

## Task 7: Rewrite `docs/tool-catalog.md`

**Files:**
- Modify: `docs/tool-catalog.md` (full rewrite)

**Rollback:** `git checkout HEAD -- docs/tool-catalog.md`.

- [ ] **Step 1: Replace contents with 13-tool surface (blueprint §7)**

Structure the doc as:

```markdown
# MCP Tool Catalog

13 generic tools, parameterized by `entity` + dispatched to handlers via `EntityRegistry`.

## Entity tools (6)

| Tool | Purpose | Params |
|---|---|---|
| `entity_list` | list/filter/search | entity, filter?, sort?, page?, search? |
| `entity_get` | single read | entity, id |
| `entity_create` | insert | entity, data, link? |
| `entity_update` | modify | entity, id, data |
| `entity_delete` | soft/hard delete | entity, id, force? |
| `entity_aggregate` | group/count | entity, group_by, metric? |

## Provider tools (3)

| Tool | Purpose | Params |
|---|---|---|
| `provider_read` | get from external | provider, kind, ref |
| `provider_write` | push to external | provider, kind, ref, data |
| `provider_search` | search platform | provider, kind, query \| seed_track_id |

## Compute tools (2)

| Tool | Purpose | Params |
|---|---|---|
| `compute_analyze` | run handler pipeline | entity, ids, level? |
| `compute_classify` | rule-based tagging | entity, ids |

Plus: `sync_playlist`, `admin_unlock_namespace`.

## Entity registry

Registered in `app/registry/entity.py:register_default_entities()` at lifespan startup:

| entity key | model | handler |
|---|---|---|
| track | `models.Track` | default CRUD |
| playlist | `models.Playlist` | default CRUD |
| set | `models.DJSet` | default CRUD |
| set_version | `models.SetVersion` | `handlers.set_version_build.handle` on create |
| transition | `models.Transition` | default CRUD |
| track_features | `models.TrackFeaturesComputed` | `handlers.track_features_analyze.handle` on create |
| audio_file | `models.AudioFile` | `handlers.audio_file_download.handle` on create |
| track_feedback | `models.TrackFeedback` | default CRUD |
| track_affinity | `models.TrackAffinity` | `handlers.track_affinity_refresh.handle` on create |
| transition_history | `models.TransitionHistory` | default CRUD |
| scoring_profile | `models.ScoringProfile` | default CRUD |
```

- [ ] **Step 2: Add "Legacy name → new call" migration table**

This is critical for downstream VM script maintainers:

```markdown
## Migration from pre-v1.0.0 tool names

| Old tool | New call |
|---|---|
| `list_tracks` | `entity_list(entity="track", filter={...})` |
| `get_track` | `entity_get(entity="track", id=...)` |
| `manage_tracks` | `entity_{create\|update\|delete}(entity="track", ...)` |
| `analyze_track` / `analyze_batch` | `compute_analyze(entity="track_features", ids=...)` |
| `classify_mood` | `compute_classify(entity="track_features", ids=...)` |
| `import_tracks` | `entity_create(entity="track", data={provider_refs:...})` |
| `download_tracks` | `entity_create(entity="audio_file", data={provider_refs:...})` |
| `find_similar_tracks` | `provider_search(provider="yandex", kind="similar", seed_track_id=...)` |
| `build_set` | `entity_create(entity="set_version", data={template, ...})` |
| `deliver_set` | `entity_create(entity="delivery", data={set_id, ...})` (handler) |
| `score_transitions` | `compute_score(entity="transition", pairs=...)` |
| `sync_playlist` | unchanged |
| `unlock_tools` | `admin_unlock_namespace(category=...)` |
| `search_platform` | `provider_search(provider, kind, query)` |
| `platform_playlists` | `provider_read/write(provider="yandex", kind="playlist", ...)` |
| `platform_liked_tracks` | `provider_read/write(provider="yandex", kind="liked", ...)` |
```

- [ ] **Step 3: Commit**

```bash
git add docs/tool-catalog.md
git commit -m "docs(tool-catalog): rewrite for 13-tool blueprint surface

Replaces 88-tool flat listing with entity_*, provider_*, compute_*
taxonomy. Adds legacy-name migration table for external consumers."
```

---

## Task 8: Rewrite `docs/structure.md` + path-touch smaller docs

**Files:**
- Modify: `docs/structure.md` (full rewrite)
- Modify: `docs/domain-glossary.md` (path touches only)
- Modify: `docs/transition-scoring.md` (path touches only)
- Modify: `docs/audio-pipeline.md` (path touches only)
- Modify: `docs/panel-guide.md` (update MCP endpoint names)
- Modify: `docs/vm-deployment.md` (update script references + tool names)
- Rename: `docs/ym-api-guide.md` → `docs/provider-yandex-guide.md`

**Rollback:** `git checkout HEAD -- docs/`.

- [ ] **Step 1: Rewrite `docs/structure.md` directory tree section**

Replace the "Directory Tree" block with the new layout per blueprint §3. Sections 2 (DB schema) and 3 (constraints) — update table list (drop the 15 deleted tables; confirm 31 live tables).

- [ ] **Step 2: Update DB schema tables section of `docs/structure.md`**

Delete these entries:
- `spotify_metadata`, `spotify_album_metadata`, `spotify_artist_metadata`, `spotify_playlist_metadata`, `spotify_audio_features`
- `beatport_metadata`
- `soundcloud_metadata`
- `embeddings`
- `transition_candidates`
- `dj_saved_loops`
- `dj_cue_points`
- `dj_beatgrid_change_points`
- `dj_set_constraints`
- `dj_set_feedback`
- `labels`, `track_labels`
- `app_exports`

Update Section 4 "Approximate Volumes" table count from 46 → 31 (drops 15 dead tables per blueprint §13.2).

- [ ] **Step 3: Path-touch smaller docs**

Apply sed-equivalent replacements (use Edit tool, not sed):

```text
app/core/utils/time.py      → app/shared/time.py
app/core/constants.py       → app/shared/constants.py
app/core/errors.py          → app/shared/errors.py
app/entities/audio/features.py → app/domain/transition/features.py
app/transition/             → app/domain/transition/
app/optimization/           → app/domain/optimization/
app/camelot/                → app/domain/camelot/
app/templates/              → app/domain/template/
app/audit/                  → app/domain/audit/
app/services/               → app/handlers/
app/clients/ym/             → app/providers/yandex/
app/ym/                     → app/providers/yandex/
app/controllers/tools/      → app/tools/
app/controllers/resources/  → app/resources/
app/controllers/prompts/    → app/prompts/
app/controllers/dependencies/ → app/server/di.py
app/bootstrap/              → app/server/
app/db/models/              → app/models/
app/db/repositories/        → app/repositories/
app/api/                    → app/rest/
```

For each of `docs/domain-glossary.md`, `docs/transition-scoring.md`, `docs/audio-pipeline.md`:

```bash
# Use Grep then Edit — DO NOT use sed (project rule).
grep -n "app/core/" docs/domain-glossary.md
# ...then Edit to replace each hit.
```

- [ ] **Step 4: Rename `docs/ym-api-guide.md` → `docs/provider-yandex-guide.md`**

```bash
git mv docs/ym-api-guide.md docs/provider-yandex-guide.md
```

Update its opening line: `# Yandex Music API Guide` → `# Provider — Yandex Music`.

Update cross-references:

```bash
grep -rln "ym-api-guide.md" CLAUDE.md docs/ .claude/
```

Replace each hit with `provider-yandex-guide.md`.

- [ ] **Step 5: Update `docs/panel-guide.md`**

The panel stays on Supabase direct reads + REST API for mutations. Only change the `Server Actions` table: update MCP tool names per the migration table in `docs/tool-catalog.md`:

- `classify_mood` → `entity_update(entity="track_features", data={level: 3})` (classification triggered by handler)
- `analyze_track` → `entity_create(entity="track_features")` (handler runs pipeline)
- `searchPlatform` action calls `provider_search`
- `importTracks` → `entity_create(entity="track", data={source, provider_ids})`
- `buildSet` → `entity_create(entity="set_version", data={set_id, track_order})`
- `deliverSet` → separate `deliver_set` tool becomes `entity_create(entity="set_version")` + file export handler side-effect
- `syncPlaylist` → `playlist_sync` (unchanged name)

- [ ] **Step 6: Update `docs/vm-deployment.md`**

The VM continues running BFS + L5 loops with new tool names. Make these edits:

a. `scripts/vm_import_and_analyze.py` now drives analysis via:
```text
entity_create(entity="track_features", data={track_ids: [...], level: 5})
```
Update the CLI invocation table + example output block to reflect the new payload shape.

b. `scripts/ym_bfs_expand.py` now uses:
```text
provider_search(provider="yandex_music", query=..., type="tracks")
provider_read(provider="yandex_music", entity="track", params={similar_to: ...})
entity_create(entity="track", data={source: "yandex_music", provider_ids: [...]})
```

c. Update the *systemd-run pattern* section: the service binary path changes from `/opt/dj-music/.venv/bin/python -u /opt/dj-music/scripts/vm_import_and_analyze.py` to the same thing — no change, but note the underlying Python now imports `app.handlers.track_features_analyze` (new path).

d. Remove any references to `app.services.*` in the troubleshooting section; replace with `app.handlers.*` and `app.server.middleware.*`.

e. Verify no `app.ym.client` / `app.ym.rate_limiter` references remain; replace with `app.providers.yandex.client` / `app.providers.yandex.rate_limiter`.

- [ ] **Step 7: Verify no lingering references to v2**

```bash
grep -rln "app/v2" docs/ CLAUDE.md
```

Expected: empty output.

- [ ] **Step 8: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: update structure/glossary/scoring/audio/panel/vm for v1.0.0

Directory tree rewritten, DB schema dropped 15 dead tables (46→31),
paths updated from app/core, app/services, app/controllers, app/bootstrap
to app/shared, app/handlers, app/tools+resources+prompts, app/server.
panel-guide: MCP endpoint names refreshed for polymorphic CRUD.
vm-deployment: script tool-name updates + systemd path confirmations.
Renamed ym-api-guide.md → provider-yandex-guide.md."
```

---

## Task 9: Rewrite `.claude/rules/*.md`

**Files:**
- Modify: `.claude/rules/audio.md`, `bootstrap.md`, `config.md`, `entities.md`, `gotchas.md`, `logging.md`, `models.md`, `optimization.md`, `prompts.md`, `providers.md`, `rest-api.md`, `resources.md`, `repositories.md`, `tests.md`, `tools.md`, `transitions.md`
- Delete: `.claude/rules/services.md`, `.claude/rules/workflows.md`
- Rename: `.claude/rules/ym.md` → `.claude/rules/provider-yandex.md`

**Rollback:** `git checkout HEAD -- .claude/rules/`.

- [ ] **Step 1: Delete obsolete rule files**

```bash
git rm .claude/rules/services.md .claude/rules/workflows.md
```

Rationale: no `app/services/` or `app/services/workflows/` layer anymore. Handlers ≠ services; prompts replace workflows.

- [ ] **Step 2: Rename YM rule**

```bash
git mv .claude/rules/ym.md .claude/rules/provider-yandex.md
```

Update first heading: `# Yandex Music Client` → `# Provider — Yandex Music`. Update path references inside:
- `app/clients/ym/` → `app/providers/yandex/`
- `YandexMusicClient` → remains
- Add: "This adapter implements `app/registry/provider.py:Provider` protocol."

- [ ] **Step 3: Rewrite `.claude/rules/tools.md`**

Replace whole file with rules for the 13-tool surface:

```markdown
# MCP Tools

- 13 generic tools: `entity_*`, `provider_*`, `compute_*`, `sync_playlist`, `admin_unlock_namespace`
- Use `@tool` decorator (FileSystemProvider auto-discovers `app/tools/`)
- One file per tool: `app/tools/entity/list.py`, `app/tools/provider/read.py`, etc.
- Entity tools dispatch via `app/registry/entity.py:EntityRegistry`
- Provider tools dispatch via `app/registry/provider.py:ProviderRegistry`
- Compute tools dispatch to handlers: `app/handlers/*.py`
- Return typed Pydantic models (from `app/schemas/`) for structuredContent
- `tags={ToolCategory.CORE.value}` — always use StrEnum from `app/shared/taxonomy.py`
- Annotations: `ANNOTATIONS_READ_ONLY` / `ANNOTATIONS_WRITE` / ... (from `app/shared/taxonomy.py`)
- Title: `title="Human Readable Name"` — REQUIRED
- Icons + meta — `icons=ICON_*`, `meta=TOOL_META`
- Visibility: default via `app/server/visibility.py`; per-session via `ctx.enable_components(tags={...})`
- Context injection: `ctx: Context = CurrentContext()  # noqa: B008`
- DI: `handler=Depends(get_my_handler)` — never `Annotated[..., Depends(...)]`

## Gotchas

- `entity_create(entity="track_features")` invokes `handlers/track_features_analyze.py` (side effects)
- `entity_create(entity="set_version")` invokes `handlers/set_version_build.py` (GA/greedy)
- `sync_playlist` direction + conflict_strategy unchanged from v0 contract
- BM25SearchTransform provides `run_tool` synthetic tool for free — do NOT write one
```

- [ ] **Step 4: Rewrite `.claude/rules/resources.md`, `prompts.md`, `repositories.md`, `models.md`, `bootstrap.md`, `config.md`, `entities.md`, `optimization.md`, `providers.md`, `rest-api.md`**

For each:
- Update paths (see Task 8 mapping).
- Drop mentions of `app/services/`, `app/controllers/`, `app/bootstrap/`.
- Point to new locations.

Example rewrite for `.claude/rules/bootstrap.md`:

```markdown
# Server composition

`app/server/app.py` — `build_mcp_server()`. Call order:

```python
mcp = FastMCP(
    providers=[FileSystemProvider(mcp_dir)],
    transforms=build_pre_constructor_transforms(),
    lifespan=build_server_lifespan(),
    sampling_handler=sampling_handler,
)
register_post_constructor_transforms(mcp)
register_middleware(mcp)
apply_visibility_policy(mcp)
```

## Lifespans (`app/server/lifespan.py`)

```python
return db_lifespan | provider_lifespan | analyzer_lifespan \
       | entity_registry_lifespan | cache_lifespan
```

| Lifespan | Keys |
|---|---|
| db_lifespan | db_engine, db_session_factory |
| provider_lifespan | provider_registry |
| entity_registry_lifespan | entity_registry |
| analyzer_lifespan | analyzer_registry |
| cache_lifespan | response_cache, transition_cache |
```bash

- [ ] **Step 5: Touch path-only files**

For `.claude/rules/gotchas.md`, `logging.md`, `tests.md`, `transitions.md`, `audio.md`: Grep for old paths and Edit each hit.

- [ ] **Step 6: Scan for stale references**

```bash
grep -rln "app/services\|app/controllers\|app/bootstrap\|app/core\|app/v2" .claude/rules/
```

Expected: empty.

- [ ] **Step 7: Commit**

```bash
git add .claude/rules/
git commit -m "docs(rules): rewrite .claude/rules for v1.0.0 blueprint

Deleted services.md, workflows.md (layers gone).
Renamed ym.md → provider-yandex.md.
Rewrote tools.md for 13-tool surface, bootstrap.md for app/server/,
config.md for split-per-domain layout. Path touches throughout."
```

---

## Task 10: Delete dead code group 1 — `app/engines/`, `app/infrastructure/`, `app/clients/`

**Files:**
- Delete: `app/engines/` (8 files, 348 LOC)
- Delete: `app/infrastructure/` (2 files, 97 LOC)
- Delete: `app/clients/` (empty package)

**Rollback:** `git reset --hard HEAD~1` (single commit, tree still has `app/v2/` intact).

- [ ] **Step 1: Confirm no live imports**

```bash
grep -rln "from app.engines\|from app.infrastructure\|from app.clients" \
    app/ tests/ scripts/ panel/ 2>/dev/null
```

Expected: empty. (Phase 6 cleaned these up; this step is a paranoia check.)

- [ ] **Step 2: Delete**

```bash
git rm -r app/engines app/infrastructure app/clients
```

- [ ] **Step 3: Delete matching tests**

```bash
[ -d tests/test_engines ] && git rm -r tests/test_engines
[ -d tests/test_infrastructure ] && git rm -r tests/test_infrastructure
true  # idempotent — ok if no such dirs
```

- [ ] **Step 4: Run `make check` to confirm nothing blows up**

```bash
make check
```

Expected: all green. If anything fails → `git reset --hard HEAD` and investigate the import graph.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: delete app/engines, app/infrastructure, app/clients

Dead code per blueprint §13.1. Engines was an experimental live-DJ
simulator; infrastructure was an unused stub; clients was empty."
```

---

## Task 11: Delete dead code group 2 — `app/ym/` + `app/api/services/*`

**Files:**
- Delete: `app/ym/` (5 files, 792 LOC) — superseded by `app/v2/providers/yandex/`
- Delete: `app/api/services/ym_audio_proxy.py` (~150 LOC)
- Delete: `app/api/services/tool_registry.py` (~100 LOC)
- Delete: `app/api/services/signed_url_cache.py` (~50 LOC)

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: Verify `app/ym/` not imported by anything we keep**

```bash
grep -rln "from app.ym\|import app.ym" \
    app/controllers app/services app/bootstrap app/api tests/ 2>/dev/null \
    | grep -v "app/ym/"  # exclude self-imports
```

Expected: empty. If anything hits → Phase 6 missed it; abort + fix.

- [ ] **Step 2: Delete**

```bash
git rm -r app/ym
git rm app/api/services/ym_audio_proxy.py \
       app/api/services/tool_registry.py \
       app/api/services/signed_url_cache.py
```

- [ ] **Step 3: Verify `app/api/services/` is now empty or deletable**

```bash
ls app/api/services/ || true
```

If only `__init__.py` left → `git rm -r app/api/services/`.

- [ ] **Step 4: `make check`**

```bash
make check
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: delete app/ym and api service proxies

app/ym replaced by app/v2/providers/yandex (adapter).
ym_audio_proxy removed — panel streams directly from Supabase signed URLs.
tool_registry removed — use MCP list_tools instead.
signed_url_cache obsolete without proxy."
```

---

## Task 12: Delete dead code group 3 — `app/controllers/tools/{decks,mixer,monitoring,audio_atomic,run_tool}.py` + schemas

**Files:**
- Delete: `app/controllers/tools/decks.py` (8 tools)
- Delete: `app/controllers/tools/mixer.py` (7 tools)
- Delete: `app/controllers/tools/monitoring.py`
- Delete: `app/controllers/tools/audio_atomic.py`
- Delete: `app/controllers/tools/run_tool.py`
- Delete: `app/schemas/deck.py`
- Delete: `app/schemas/mixer.py`

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: Verify none of these tools are registered as required**

```bash
grep -rln "decks\|mixer\|monitoring_status\|run_tool" \
    app/bootstrap/visibility.py app/bootstrap/transforms.py
```

Expected: tags only in `_DISABLED_AT_STARTUP` set. If tools are wired into a workflow — abort and extract the logic first.

- [ ] **Step 2: Delete**

```bash
git rm app/controllers/tools/decks.py \
       app/controllers/tools/mixer.py \
       app/controllers/tools/monitoring.py \
       app/controllers/tools/audio_atomic.py \
       app/controllers/tools/run_tool.py \
       app/schemas/deck.py \
       app/schemas/mixer.py
```

- [ ] **Step 3: Delete matching tests**

```bash
git rm -f tests/test_tools/test_decks.py \
         tests/test_tools/test_mixer.py \
         tests/test_tools/test_monitoring.py \
         tests/test_tools/test_audio_atomic.py \
         tests/test_tools/test_run_tool.py 2>/dev/null || true
```

- [ ] **Step 4: Update `.importlinter` — remove `engines-no-transport` contract**

```bash
# That contract referenced a now-deleted directory.
# Apply with Edit tool.
```

In `.importlinter`, locate the contract block `[importlinter:contract:engines-no-transport]` and delete it in full.

- [ ] **Step 5: `make check`**

```bash
make check
```

Expected: green. Tool count in `uv run pytest tests/test_tools/` drops by 5×N tests.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete deprecated tool files and schemas

decks/mixer/monitoring (engines-dependent) were unreachable.
audio_atomic folded into entity_create(entity=track_features) pattern.
run_tool superseded by FastMCP BM25SearchTransform synthetic tool.
Dropped engines-no-transport importlinter contract."
```

---

## Task 13: Delete `app/services/` tree — 39 files

**Files:**
- Delete: `app/services/` (entire tree, ~7000 LOC)

**Rollback:** `git reset --hard HEAD~1` — recovers `app/services/`. Be careful: this commit is large (~7000 LOC of deletions). If a subsequent task reveals we still need something, cherry-pick just that file back rather than full reset.

- [ ] **Step 1: Grep for remaining imports of `app.services` from `app/` (not `app/v2/`)**

```bash
grep -rln "from app.services\|import app.services" app/ \
    | grep -v "app/services/\|app/v2/"
```

Expected: empty. Phase 3 and Phase 5 should have rerouted everything.

If ANY non-v2 importer remains → stop. Cutover cannot proceed until those are migrated (probably a Phase-3 leftover).

- [ ] **Step 2: Confirm `app/v2/handlers/` covers all services**

```bash
ls app/v2/handlers/ | wc -l           # handlers count
```

Expected: 6 (per blueprint §5.2: `track_import`, `audio_file_download`, `track_features_analyze`, `track_features_classify`, `set_version_build`, `set_deliver`, `track_affinity_refresh`, `playlist_distribute`). Some phases may add more; 6–9 is acceptable.

- [ ] **Step 3: Delete `app/services/`**

```bash
git rm -r app/services
```

- [ ] **Step 4: Delete matching test directories**

```bash
git rm -rf tests/test_services || true
```

- [ ] **Step 5: `make check`**

```bash
make check
```

Expected: green. This is the big-delete commit; a lot of test files disappear with it.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete app/services tree (39 files, ~7000 LOC)

Per blueprint §13.1. Logic redistributed in Phase 3 + Phase 5:
- CRUD-like services → generic entity_* tools
- Side-effecting services → app/v2/handlers/
- Query helpers → app/v2/repositories/track.py
- Workflows → app/v2/prompts/*_workflow.py
- adaptive_arc, set_narrative → app/v2/resources/set.py
All live callers rerouted; this is dead weight."
```

---

## Task 14: Delete `app/controllers/` flat tree + `app/bootstrap/` + `app/api/` + `app/schemas/`

**Files:**
- Delete: `app/controllers/` (tools, resources, prompts, dependencies, middleware.py, elicitation.py)
- Delete: `app/bootstrap/` (8 files)
- Delete: `app/api/` (everything that wasn't already deleted in Task 11)
- Delete: `app/schemas/` (everything that wasn't already deleted in Task 12)

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: Verify nothing outside these dirs + `app/v2/` imports them**

```bash
for pkg in app.controllers app.bootstrap app.api app.schemas; do
  echo "== $pkg =="
  grep -rln "from ${pkg}\|import ${pkg}" app/ scripts/ tests/ panel/ 2>/dev/null \
    | grep -v "app/controllers/\|app/bootstrap/\|app/api/\|app/schemas/\|app/v2/"
done
```

Expected: empty for each. If anything remains, it's a leftover — STOP and fix.

- [ ] **Step 2: Delete**

```bash
git rm -r app/controllers app/bootstrap app/api app/schemas
```

- [ ] **Step 3: Delete matching tests**

```bash
for d in tests/test_tools tests/test_resources tests/test_prompts \
         tests/test_bootstrap tests/test_api tests/test_schemas \
         tests/test_controllers; do
  [ -d "$d" ] && git rm -r "$d"
done
```

- [ ] **Step 4: `make check`**

```bash
make check
```

Expected: green. At this point `app/` contains only `app/v2/` + leaf files (`audio/`, `db/models/`, `db/repositories/`, `transition/`, `optimization/`, `camelot/`, `templates/`, `audit/`, `entities/`, `core/`, `config.py`, `server.py`, `telemetry.py`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: delete app/controllers, app/bootstrap, app/api, app/schemas

Replaced by app/v2/{tools,resources,prompts,server,rest,schemas}.
Final pre-swap cleanup — next task moves v2 → top-level."
```

---

## Task 15: Delete `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`, `app/entities/`, `app/audio/`, `app/core/`, `app/db/`, `app/config.py`, `app/server.py`, `app/telemetry.py`, `app/_version.py`

**Files:**
- Delete: all of the above — they have been mirrored into `app/v2/` in Phases 2, 5, 6.

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: Sanity-check mirror parity**

```bash
for d in transition optimization camelot templates audit entities audio core db; do
  old_count=$(find "app/${d}" -type f -name "*.py" 2>/dev/null | wc -l)
  new_count=$(find "app/v2/domain/${d}" -type f -name "*.py" 2>/dev/null | wc -l)
  # Some map differently: audio → app/v2/audio; db → app/v2/db + models + repositories.
  echo "${d}: old=${old_count}"
done
```

Just print for awareness. Don't gate on it — the migration map (blueprint §14) already governs.

- [ ] **Step 2: Verify no imports from `app.<legacy>` outside `app/v2/`**

```bash
for pkg in app.transition app.optimization app.camelot app.templates app.audit \
           app.entities app.audio app.core app.db app.server app.telemetry app._version; do
  hits=$(grep -rln "^from ${pkg}\|^import ${pkg}" app/ scripts/ tests/ 2>/dev/null \
         | grep -v "app/v2/\|app/${pkg#app.}/" || true)
  [ -n "$hits" ] && echo "LEAK: ${pkg} → ${hits}"
done
echo "scan done"
```

Expected: `scan done` with no `LEAK:` lines.

- [ ] **Step 3a: PRESERVE `app/db/migrations/` — move into v2 tree before deletion**

```bash
# Critical: migrations live at app/db/migrations/ in legacy tree but
# app/v2/db/ only has session.py + seed.py per Phase 2 Task 20. We must
# relocate migrations/ BEFORE deleting the rest of app/db/, otherwise
# Alembic loses its version history and post-cutover `alembic upgrade
# head` breaks because script_location in alembic.ini points at
# app/db/migrations/ — a path that becomes valid again only AFTER
# Task 16's app/v2/ → app/ swap if migrations live under app/v2/db/.

git mv app/db/migrations/ app/v2/db/migrations/
git commit -m "refactor(db): move alembic migrations to v2 tree before legacy delete

Preserves migration version history across the cutover. alembic.ini
continues pointing at 'app/db/migrations/' which becomes valid again
after Task 16's app/v2/ → app/ swap."
```

Verify `app/db/` now contains only items Step 3b will delete (no `migrations/`):

```bash
ls app/db/
```

Expected output must NOT contain `migrations`. Typical remainder:
`__init__.py  models/  repositories/  seed.py  session.py`.

- [ ] **Step 3b: Delete legacy domain + infra dirs (migrations preserved)**

```bash
git rm -r app/transition app/optimization app/camelot app/templates \
          app/audit app/entities app/audio app/core app/db
git rm app/config.py app/server.py app/telemetry.py app/_version.py
# `app/providers/` legacy re-exports (blueprint §13.1):
[ -d app/providers ] && git rm -r app/providers
```

- [ ] **Step 4: Delete matching test trees**

```bash
for d in tests/test_transition tests/test_optimization tests/test_camelot \
         tests/test_templates tests/test_audit tests/test_entities \
         tests/test_audio tests/test_core tests/test_db tests/test_models \
         tests/test_repositories tests/test_domain tests/test_ym \
         tests/acceptance; do
  [ -d "$d" ] && git rm -r "$d"
done
```

(Note: `tests/acceptance` is deleted because its contents test pre-v1.0.0 tool names; the replacement lives at `tests/v2/acceptance/` and will become `tests/acceptance/` in Task 17.)

- [ ] **Step 5: `make check`** — this is the critical moment

```bash
make check
```

Expected: green. `app/` now effectively contains only `app/v2/` (with `app/v2/db/migrations/` relocated in Step 3a) and `app/__init__.py`. Alembic still finds migrations via the original `app/db/migrations/` path — they'll be there again after Task 16's swap moves `app/v2/db/migrations/` back to `app/db/migrations/`.

If `make check` fails: this is the most dangerous point. Before rollback, inspect:

```bash
uv run pytest --co 2>&1 | tail -30
uv run mypy app/ 2>&1 | head -20
```

Identify whether it's (a) missing import → rollback and patch, or (b) a test under `tests/` that still references legacy paths → add it to the delete list in Step 4 and retry.

If all else fails:

```bash
git reset --hard HEAD~1   # back to pre-Task-15 state
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete legacy app/transition, /optimization, /camelot, /templates, /audit, /entities, /audio, /core, /db, config.py, server.py, telemetry.py

All mirrored under app/v2/ by Phases 5 + 6. app/ now contains only
app/v2/ plus its package init — next task is the atomic swap."
```

---

## Task 16: ATOMIC SWAP — `app/` → `app/v1_legacy/`, `app/v2/` → `app/`

**Files:**
- Move: `app/__init__.py` → `app/v1_legacy/__init__.py` (+ anything else left)
- Move: `app/v2/` → `app/`
- Move: `tests/` → `tests/v1_legacy/`
- Move: `tests/v2/` → `tests/`

**Rollback:** This is the most dangerous task. Rollback must be planned — see "Rollback" block at end of this task.

**Critical:** All three renames must happen in one commit. A half-swapped tree leaves the repo in a broken state. Use `git mv` so rename detection is preserved.

- [ ] **Step 1: Confirm the tree is minimal**

```bash
ls app/
# Expected: __init__.py v2/
ls tests/
# Expected: __init__.py conftest.py v2/ (plus maybe scripts/)
```

If there are unexpected files — STOP and investigate. They're leftovers from Task 15.

- [ ] **Step 2: Stash `app/__init__.py` + any root leftovers into `v1_legacy/`**

```bash
mkdir -p /tmp/phase-7-swap-backup
cp -a app /tmp/phase-7-swap-backup/app.before
cp -a tests /tmp/phase-7-swap-backup/tests.before
```

(Filesystem-level backup — insurance beyond git.)

- [ ] **Step 3: Atomic rename (ordering matters)**

```bash
# 1. Stash legacy out of the way.
git mv app app_TEMP_v1_legacy
# 2. Rename new tree up.
git mv app_TEMP_v1_legacy/v2 app
# 3. What remains of app_TEMP_v1_legacy is the old root shell.
git mv app_TEMP_v1_legacy app/v1_legacy
# (We move the remaining legacy shell INTO the new tree so it's under
# the same package and can be importlinter-gated. See blueprint §15.8
# "stash for one release cycle".)
```

- [ ] **Step 4: Same pattern for tests**

```bash
git mv tests tests_TEMP_v1_legacy
git mv tests_TEMP_v1_legacy/v2 tests
git mv tests_TEMP_v1_legacy tests/v1_legacy
```

- [ ] **Step 5: Verify tree shape**

```bash
ls app/
# Expected: __init__.py shared/ config/ registry/ repositories/
#           handlers/ tools/ resources/ prompts/ schemas/ models/
#           domain/ providers/ audio/ db/ server/ rest/ server.py
#           v1_legacy/
ls tests/
# Expected: __init__.py conftest.py + new tests tree + v1_legacy/
```

- [ ] **Step 6: Rewrite `app/__init__.py`**

Remove the `0.0.0-v2` marker. Replace with:

```python
"""DJ Music Plugin — v1.0.0 "The Blueprint" architecture.

See docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md.
"""
from app._version import __version__  # noqa: F401
```

- [ ] **Step 7: Delete `app/v1_legacy/v2/` leftover**

After the two `git mv` juggles above, `app/v1_legacy/` might contain a weird `v2/` child (the source of step 3.2). Verify + clean:

```bash
ls app/v1_legacy/
# If v2/ is present — it's empty (contents already moved). Remove.
[ -d app/v1_legacy/v2 ] && git rm -r app/v1_legacy/v2
[ -d tests/v1_legacy/v2 ] && git rm -r tests/v1_legacy/v2
```

- [ ] **Step 8: Quarantine `app/v1_legacy/` via importlinter**

Edit `.importlinter` — replace the old `v2-backflow-gate` contract with a new one:

```ini
[importlinter:contract:legacy-sunset]
name = app.v1_legacy must not be imported by anything in app
type = forbidden
source_modules =
    app.shared
    app.config
    app.registry
    app.repositories
    app.handlers
    app.tools
    app.resources
    app.prompts
    app.schemas
    app.models
    app.domain
    app.providers
    app.audio
    app.db
    app.server
    app.rest
forbidden_modules =
    app.v1_legacy
```

- [ ] **Step 9: Verify package import works**

```bash
uv run python -c "
import app
print(app.__version__)
from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.server import build_mcp_server  # main entrypoint
print('import OK')
"
```

Expected: `1.0.0` and `import OK`. If this fails — **immediate rollback**.

- [ ] **Step 10: Commit (large — but atomic)**

```bash
git add -A
git commit -m "refactor(!!!): atomic cutover — app/v2 → app, legacy to app/v1_legacy

The blueprint is live. app/ is the new home; old code quarantined
under app/v1_legacy/ for one release cycle (deleted in post-v1.0.0
sunset). Tests mirror: tests/v2 → tests, old → tests/v1_legacy.

Updated .importlinter with legacy-sunset gate (no app/* may import
v1_legacy)."
```

**Rollback procedure for Task 16:**

If anything after this commit goes catastrophically wrong:

```bash
# 1. Back out commit (keeps working tree).
git revert HEAD --no-edit

# 2. If revert is too surgical and tree is broken, do a hard reset:
git reset --hard /tmp/phase-7-pre-dev-sha.txt-contents

# 3. Restore filesystem-level backup:
rm -rf app tests
cp -a /tmp/phase-7-swap-backup/app.before app
cp -a /tmp/phase-7-swap-backup/tests.before tests

# 4. Push -f to cutover/v1.0.0 (this branch never touched main):
git push --force-with-lease origin cutover/v1.0.0
```

DO NOT push -f to `dev` or `main`. The cutover branch is cheap to recreate.

---

## Task 17: Update `pyproject.toml`, `alembic.ini`, `start.sh`, scripts, Makefile

**Files:**
- Modify: `pyproject.toml`
- Modify: `alembic.ini`
- Modify: `start.sh`
- Modify: `Makefile` (if it references old paths)
- Modify: `scripts/vm_import_and_analyze.py`, `scripts/vm_analyze.py`, `scripts/ym_bfs_expand.py` (other scripts as needed)
- Modify: `panel/.env.example` (sanity-check only; semantics unchanged)

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: `pyproject.toml` — update `[project.scripts]` + package discovery**

Use Read first to see current layout, then Edit:

Typical changes:
```toml
# Before:
[project.scripts]
dj-mcp = "app.v2.server:main"

# After:
[project.scripts]
dj-mcp = "app.server:main"
```

Also update:
- `[tool.mypy]` → `files = ["app/"]` (drop `app/v2/` if listed separately).
- `[tool.ruff] src = ["app", "tests"]` (drop `app/v2`, `tests/v2`).
- `[tool.pytest.ini_options] testpaths = ["tests"]` (drop `tests/v2`).
- `[tool.setuptools.packages.find] include = ["app*"]` (unchanged; already covers `app/v1_legacy/*` — that's fine).
- Version bump: `version = "1.0.0"`.

- [ ] **Step 2: `alembic.ini`**

```ini
# Before:
script_location = app/v2/db/migrations
# After:
script_location = app/db/migrations
```

And update `app/db/migrations/env.py` `target_metadata` import path:

```python
# Before:
from app.v2.models.base import Base
# After:
from app.models.base import Base
```

- [ ] **Step 3: `start.sh`**

```bash
# Before:
uv run uvicorn app.v2.rest.server:api --port 8000
# After:
uv run uvicorn app.rest.server:api --port 8000

# Before:
uv run fastmcp run app/v2/server.py
# After:
uv run fastmcp run app/server.py
```

- [ ] **Step 4: `Makefile`**

Check lines like `mypy app/ app/v2/` → `mypy app/`, and any `pytest tests/ tests/v2/` → `pytest tests/`.

- [ ] **Step 5: Scripts — purge `app.v2` imports**

```bash
grep -rln "app\.v2\|app/v2" scripts/
```

For each file: replace `app.v2.<x>` → `app.<x>`.

Critically for BFS/L5:
- `scripts/vm_import_and_analyze.py`
- `scripts/vm_analyze.py`
- `scripts/ym_bfs_expand.py`

These use `compat_shims` (Task 3) — the shim path stays stable (`from scripts.compat_shims import dispatch_legacy`), but any `from app.v2.server import build_mcp_server` must become `from app.server import build_mcp_server`.

- [ ] **Step 6: Panel**

```bash
cat panel/.env.example
```

Confirm `MCP_HTTP_URL=http://localhost:8000` unchanged. No edits needed unless it references old paths (it shouldn't).

- [ ] **Step 7: `make check`**

```bash
make check
```

Expected: green across the board. This is the functional verification that the swap is complete.

- [ ] **Step 8: Smoke-start the new server locally**

```bash
timeout 10 uv run fastmcp run app/server.py > /tmp/phase-7-server-boot.log 2>&1 &
sleep 5
grep -E "(started|ready|error)" /tmp/phase-7-server-boot.log | head -5
pkill -f "fastmcp run app/server.py"
```

Expected: log shows startup messages, no tracebacks.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml alembic.ini start.sh Makefile \
        app/db/migrations/env.py \
        scripts/ panel/.env.example
git commit -m "chore: bump version to 1.0.0, retarget entrypoints to app/

pyproject.toml, alembic.ini, start.sh, Makefile, scripts/* now point
to app/ instead of app/v2/. Version = 1.0.0 (The Blueprint)."
```

---

## Task 18: Run the Alembic migration for dropped tables

**Files:**
- Uses: existing migration from Phase 2 (`app/db/migrations/versions/*_drop_dead_tables.py`)

**Rollback:** Alembic down-migration; **crucial pre-requirement:** DB backup from Task 1 Step 6 is available.

> Blueprint §13.2 lists 15 tables + `app_exports` (16 rows), implemented in Phase 2 as a single migration. The migration has been on staging since Phase 2 — this task applies to **production** (Supabase main DB).

- [ ] **Step 1: Dry-run on staging branch**

```bash
# Supabase branch — safe copy of prod schema.
# Managed via Supabase MCP: create a branch, apply migration, verify.
uv run python -c "
import asyncio
from app.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    s = get_settings()
    e = create_async_engine(s.database.url_staging)
    async with e.connect() as c:
        res = await c.execute(text(
            \"select tablename from pg_tables where schemaname='public' order by tablename;\"
        ))
        tables = [r[0] for r in res]
        print(f'staging has {len(tables)} tables')
        for t in tables: print('  ', t)
asyncio.run(main())
"
```

Expected: 31 tables (already migrated by Phase 2). If 44 tables → staging was NOT migrated in Phase 2; STOP and fix there first.

- [ ] **Step 2: Take explicit snapshot of production DB**

Already done in Task 1 Step 6. Verify backup file/id is still referenced:

```bash
cat /tmp/phase-7-backup-id.txt
```

- [ ] **Step 3: Apply migration to production**

```bash
DJ_DATABASE_URL="$(grep -E '^DJ_DATABASE_URL' .env.production)" \
  uv run alembic upgrade head
```

Expected: `INFO [alembic.runtime.migration] Running upgrade ...` messages; exits zero.

- [ ] **Step 4: Verify production table count**

```bash
uv run python -c "
import asyncio
from app.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    s = get_settings()
    e = create_async_engine(s.database.url)
    async with e.connect() as c:
        res = await c.execute(text(
            \"select count(*) from information_schema.tables \"
            \"where table_schema='public';\"
        ))
        n = res.scalar_one()
        print(f'production has {n} tables')
        assert n == 31, f'expected 31, got {n}'
asyncio.run(main())
"
```

Expected: `production has 31 tables` and assertion passes.

- [ ] **Step 5: Commit Alembic stamp (if applicable)**

If `alembic_version` row changed on prod, no commit needed (it's a DB-side change). If any `app/db/migrations/versions/*.py` file changed as a side effect of re-generating metadata — STOP, that's suspicious.

- [ ] **Step 6: Do NOT push yet — we still need smoke test before merging**

No commit in this task.

**Rollback:**
```bash
uv run alembic downgrade -1
# If that fails, restore from /tmp/phase-7-backup-id.txt via Supabase dashboard.
```

---

## Task 19: Smoke-test the new tree with `scripts/smoke_test_all_tools.py`

**Files:**
- Create: `scripts/smoke_test_all_tools.py`

**Rollback:** `git reset --hard HEAD~1`.

- [ ] **Step 1: Write smoke test script**

```python
"""Smoke-test every tool in the new (v1.0.0) tree.

For each tool:
- call_tool with a minimal valid payload
- assert: no exception; response has expected shape
- collect failures and report at end

Run: uv run python scripts/smoke_test_all_tools.py
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

from fastmcp.client import Client
from app.server import build_mcp_server

ADMIN_UNLOCK_ALL = ("admin_unlock_namespace", {"action": "unlock", "namespace": "all"})

SMOKE_CASES: list[tuple[str, dict[str, Any]]] = [
    ADMIN_UNLOCK_ALL,
    # Entity tools — read-only smokes.
    ("entity_list", {"entity": "track", "limit": 5}),
    ("entity_list", {"entity": "playlist", "limit": 5}),
    ("entity_list", {"entity": "set", "limit": 5}),
    ("entity_list", {"entity": "set_version", "limit": 5}),
    ("entity_list", {"entity": "transition", "limit": 5}),
    ("entity_list", {"entity": "track_features", "limit": 5}),
    ("entity_list", {"entity": "audio_file", "limit": 5}),
    ("entity_list", {"entity": "track_feedback", "limit": 5}),
    ("entity_list", {"entity": "track_affinity", "limit": 5}),
    ("entity_list", {"entity": "scoring_profile", "limit": 5}),
    ("entity_list", {"entity": "transition_history", "limit": 5}),
    ("entity_aggregate", {"entity": "track", "group_by": ["status"]}),
    # Provider — read-only.
    ("provider_search", {"provider": "yandex", "kind": "tracks", "query": "radar", "limit": 3}),
    # Compute — dry-run level 0 if supported, else skip.
    ("compute_classify", {"entity": "track_features", "ids": [], "dry_run": True}),
]

async def main() -> int:
    mcp = build_mcp_server()
    fails: list[tuple[str, str]] = []
    async with Client(mcp) as client:
        for name, args in SMOKE_CASES:
            try:
                result = await client.call_tool(name, args)
                print(f"OK   {name}  →  {type(result).__name__}")
            except Exception as e:  # noqa: BLE001
                fails.append((name, repr(e)))
                print(f"FAIL {name}  →  {e!r}")
    if fails:
        print(f"\n{len(fails)} smoke failures:")
        for n, err in fails:
            print(f"  {n}: {err}")
        return 1
    print(f"\nAll {len(SMOKE_CASES)} smokes passed.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: Run locally**

```bash
uv run python scripts/smoke_test_all_tools.py
```

Expected: `All N smokes passed.` exit 0.

If a smoke fails — this is the whole point of the exercise. Fix the failing tool OR the smoke assertion OR the test payload, and iterate. Do NOT merge without all smokes green.

- [ ] **Step 3: Run on staging VM**

```bash
scp scripts/smoke_test_all_tools.py root@155.212.128.27:/opt/dj-music-plugin/scripts/
ssh root@155.212.128.27 "cd /opt/dj-music-plugin && git fetch && git checkout cutover/v1.0.0 \
  && uv sync --all-extras && uv run python scripts/smoke_test_all_tools.py"
```

Expected: green on VM.

- [ ] **Step 4: Compare tool surface — new vs pre-cutover**

```bash
uv run python -c "
import asyncio, json
from fastmcp.client import Client
from app.server import build_mcp_server

async def main():
    mcp = build_mcp_server()
    async with Client(mcp) as c:
        tools = sorted(t.name for t in await c.list_tools())
        print(json.dumps(tools, indent=2))
asyncio.run(main())
" > /tmp/phase-7-post-tools.json

diff <(jq -r '.[]' /tmp/phase-7-pre-tools.json | sort) \
     <(jq -r '.[]' /tmp/phase-7-post-tools.json | sort) \
     | head -40
```

Expected: lots of removed (-) lines (old 88-tool surface), fewer added (+) lines (new 13-tool surface). Every removed tool should map to a shim in `scripts/compat_shims.py` (Task 3).

- [ ] **Step 5: Commit smoke test script**

```bash
git add scripts/smoke_test_all_tools.py
git commit -m "test: add scripts/smoke_test_all_tools.py for cutover verification

Minimal per-tool invocation suite. Runs in ~10s locally + on VM.
Called from Phase 7 Task 19; re-used on every release going forward."
```

---

## Task 20: Restart BFS/L5 on VM with new tree

**Files:** none (remote operations).

**Rollback:** `ssh root@155.212.128.27 "git checkout dev && systemctl restart dj-bfs dj-l5"` — return VM to the known-good `dev` branch.

- [ ] **Step 1: Sync the cutover branch to VM**

```bash
ssh root@155.212.128.27 "
  cd /opt/dj-music-plugin
  git fetch --all
  git checkout cutover/v1.0.0
  git reset --hard origin/cutover/v1.0.0
  uv sync --all-extras
"
```

- [ ] **Step 2: Run Alembic on VM's view of the DB** (same Supabase URL → should be no-op)

```bash
ssh root@155.212.128.27 "cd /opt/dj-music-plugin && uv run alembic upgrade head"
```

Expected: `alembic already at head`.

- [ ] **Step 3: Smoke-test on VM one more time**

```bash
ssh root@155.212.128.27 "cd /opt/dj-music-plugin && \
  uv run python scripts/smoke_test_all_tools.py"
```

Expected: green.

- [ ] **Step 4: Restart services**

```bash
ssh root@155.212.128.27 "systemctl start dj-bfs && systemctl start dj-l5 && \
  sleep 5 && systemctl is-active dj-bfs dj-l5"
```

Expected: both `active`.

- [ ] **Step 5: Tail logs for 2 minutes**

```bash
ssh root@155.212.128.27 "timeout 120 tail -f /var/log/dj-bfs.log /var/log/dj-l5.log" \
  | tee /tmp/phase-7-vm-bootstrap.log
```

Expected: new tracks processed, no `ImportError`, no `AttributeError`, no `Unknown tool` messages. Look for:
```bash
[N/M] track=<id> OK in X.Xs (ok=... fail=...)
```

- [ ] **Step 6: Verify shim path is exercised**

The log should show lines like:
```text
compat_shim: import_tracks → entity_create(entity=track, ...)
```

If not — maybe the shims aren't called (shim-bypass is actually fine; confirm no legacy tool names appear in the dispatch).

- [ ] **Step 7: Declare campaigns healthy**

If Steps 4–6 stay green for 5 minutes: **announce cutover complete in ops channel**.

No commit.

---

## Task 21: Merge `cutover/v1.0.0` → `dev` via PR

**Files:** none (git workflow only).

**Rollback:** `gh pr close <num>` — safe, PR is retryable.

- [ ] **Step 1: Open PR via `gh`**

```bash
cat > /tmp/phase-7-pr-body.md <<'EOF'
## Summary
- Atomic cutover: `app/v2/` → `app/`, legacy stashed at `app/v1_legacy/`.
- Deleted ~9000 LOC of dead code per blueprint §13.1.
- Dropped 15 dead DB tables (44 → 31) per blueprint §13.2.
- Rewrote docs: CLAUDE.md, architecture.md, tool-catalog.md, structure.md, .claude/rules/*.
- BFS/L5 VM campaigns restarted with new tool surface via `scripts/compat_shims.py`.

## Test plan
- [x] `make check` green locally
- [x] `scripts/smoke_test_all_tools.py` green locally + on staging VM
- [x] BFS/L5 services `active` on VM for >5 min, tracks processing
- [x] No lingering `app/v2` or `app.v2` references in code or docs
- [x] DB table count = 31
- [x] `uv run lint-imports` green with new `legacy-sunset` contract

Refs: `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§13, 14, 15.8
EOF

gh pr create \
  --base dev \
  --head cutover/v1.0.0 \
  --title "cutover(v1.0.0): atomic swap to blueprint architecture" \
  --body-file /tmp/phase-7-pr-body.md
```

Expected: PR URL printed. Record it.

- [ ] **Step 2: CI must pass**

```bash
gh pr view --json statusCheckRollup --jq '.statusCheckRollup[] | "\(.name): \(.conclusion // .state)"'
```

Expected: all checks `SUCCESS`.

- [ ] **Step 3: Self-review the diff**

```bash
gh pr diff | wc -l
gh pr diff | less  # manual skim, look for surprises
```

This PR is LARGE (thousands of deletions, hundreds of renames). Review with skepticism; focus on:
- Anything NEW (positive diff) that isn't a simple path/doc rewrite.
- Missing `v1_legacy/` quarantine — if legacy files ended up at `app/` root, abort.

- [ ] **Step 4: Merge via squash**

```bash
gh pr merge --squash --delete-branch
```

Expected: branch deleted; `dev` now contains cutover.

- [ ] **Step 5: Verify `dev` green**

```bash
git checkout dev
git pull --ff-only
make check
```

Expected: green.

---

## Task 22: Merge `dev` → `main` via PR, tag `v1.0.0`, GitHub release

**Files:** none (git workflow + tag).

**Rollback:** `git revert <squash-commit>` on main; retry. Do NOT hard-reset `main`.

- [ ] **Step 1: Create `dev → main` release PR**

```bash
cat > /tmp/phase-7-release-pr.md <<'EOF'
# Release — v1.0.0 "The Blueprint"

Promotes the blueprint architecture to production.

See PR <insert-cutover-pr-number> for cutover details.

## Release Notes
- **Architecture:** `app/tools/`, `app/handlers/`, `app/registry/`, `app/domain/`, `app/providers/`
- **Tool surface:** 88 → 13 generic tools (entity_*, provider_*, compute_*)
- **Schema:** 44 → 31 tables (15 dead dropped)
- **Legacy:** `app/v1_legacy/` quarantined for one release; deleted post-1.1.0

## Checklist
- [x] `dev` fully green (lint, mypy, import-linter, pytest)
- [x] Smoke test green
- [x] VM campaigns running
EOF

gh pr create \
  --base main \
  --head dev \
  --title "release: v1.0.0 — The Blueprint" \
  --body-file /tmp/phase-7-release-pr.md
```

- [ ] **Step 2: CI must pass on the `dev → main` PR**

Same `gh pr view` check.

- [ ] **Step 3: Squash-merge**

```bash
gh pr merge --squash --delete-branch=false  # keep dev branch
```

Expected: `main` now has cutover.

- [ ] **Step 4: Tag `v1.0.0`**

```bash
git checkout main
git pull --ff-only
git tag -a v1.0.0 -m "v1.0.0 — The Blueprint

Atomic cutover to blueprint architecture per
docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md.

13 generic tools replace 88; 31 DB tables replace 44; ~9000 LOC deleted.
Legacy quarantined at app/v1_legacy/; slated for deletion in v1.1.0."
git push origin v1.0.0
```

Expected: tag pushed.

- [ ] **Step 5: Create GitHub Release**

```bash
cat > /tmp/phase-7-release-notes.md <<'EOF'
## v1.0.0 — "The Blueprint"

First major release. Implements the blueprint architecture from
[blueprint spec](./docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md).

### Breaking changes (MCP tool surface)

88 tools consolidated into 13 generic ones:

| New | Replaces |
|---|---|
| `entity_list` / `entity_get` / `entity_create` / `entity_update` / `entity_delete` / `entity_aggregate` | `list_tracks`, `get_track`, `manage_tracks`, `list_playlists`, `manage_playlist`, `list_sets`, `manage_set`, `get_library_stats`, `audit_playlist`, ... |
| `provider_read` / `provider_write` / `provider_search` | `platform_playlists`, `platform_liked_tracks`, `search_platform`, `get_platform_tracks`, `find_similar_tracks`, ... |
| `compute_analyze` / `compute_classify` | `analyze_track`, `analyze_batch`, `classify_mood` |
| `sync_playlist`, `admin_unlock_namespace` | same names, refactored internals |

Legacy names still work through `scripts/compat_shims.py` for one release
(deletion scheduled for v1.1.0).

### DB schema

15 dead tables dropped. See §13.2 of the blueprint spec for the list.

### Documentation

`CLAUDE.md`, `docs/architecture.md`, `docs/tool-catalog.md`, `docs/structure.md`, and all `.claude/rules/*.md` rewritten to reflect the new tree.

### Phases

- Phase 1 — Foundation (parallel skeleton)
- Phase 2 — Persistence
- Phase 3 — Tools
- Phase 4 — Resources + Prompts
- Phase 5 — Server composition
- Phase 6 — Domain + audio port
- Phase 7 — Cutover ← this release

### Upgrade path

MCP clients using legacy tool names: migrate to new names per the table above. Shim layer at `scripts/compat_shims.py` bridges both names until v1.1.0.

### Thanks

Plan: `docs/superpowers/plans/2026-04-17-phase-7-cutover.md`.
EOF

gh release create v1.0.0 \
  --title "v1.0.0 — The Blueprint" \
  --notes-file /tmp/phase-7-release-notes.md
```

Expected: release URL printed.

- [ ] **Step 6: Bump version in `pyproject.toml` on `dev` for post-release work**

```bash
git checkout dev
git pull --ff-only
# Open pyproject.toml → version = "1.1.0.dev0"  (or whatever next)
git add pyproject.toml
git commit -m "chore: bump version to 1.1.0.dev0 post-v1.0.0 release"
git push origin dev
```

---

## Task 23: Post-flight — verify BFS/L5 stable 24 hours, record metrics

**Files:** none (observability).

**Rollback:** N/A — purely observational.

- [ ] **Step 1: 24h tail of VM logs**

```bash
ssh root@155.212.128.27 "
  tail -n 500 /var/log/dj-bfs.log | grep -E 'OK|FAIL' | tail -n 50
  tail -n 500 /var/log/dj-l5.log  | grep -E 'OK|FAIL' | tail -n 50
"
```

Count OK vs FAIL; FAIL rate should match historical baseline (≤ 5%).

- [ ] **Step 2: Sentry / error rate check**

```bash
# If Sentry is enabled:
gh api "repos/${OWNER}/${REPO}/issues?labels=sentry"
# Or directly via Sentry MCP:
# mcp__9222c2b5-.__search_issues query="error.type:ImportError OR AttributeError"
```

Expected: no new issue classes introduced by cutover. If a spike appears → investigate specific handler.

- [ ] **Step 3: Verify disk space on VM hasn't exploded**

```bash
ssh root@155.212.128.27 "df -h /opt/dj-music-plugin /var/lib/dj-cache"
```

Expected: same as pre-cutover.

- [ ] **Step 4: Verify Panel works**

```bash
curl -sf https://panel.dj-music.vercel.app/api/health | head
```

Expected: `{"status":"ok",...}` 200 OK. Panel pages don't call MCP tools directly — the `actions/*.ts` functions do, via the REST layer. Confirm key action (e.g. `buildSet`, `analyzeTrack`) works:

```bash
# Use Vercel logs MCP or curl the panel / action endpoint manually:
# mcp__96591f5d-.__get_runtime_logs project=<panel-project-id>
```

- [ ] **Step 5: Record cutover metrics in CHANGELOG**

Update `CHANGELOG.md`:

```markdown
## [1.0.0] — 2026-04-17

### Added
- 13 generic tools (entity_*, provider_*, compute_*, sync_playlist, admin_unlock_namespace)
- EntityRegistry + ProviderRegistry
- Handler layer (app/handlers/)
- Schema resources (schema://entities/{entity})

### Changed
- Project tree: app/v2/ → app/ (atomic swap)
- MCP tool surface: 88 → 13
- CLAUDE.md + all docs rewritten
- Provider abstraction: YM now via app/providers/yandex/ adapter

### Removed
- app/engines/, app/infrastructure/, app/clients/, app/services/, app/bootstrap/, app/controllers/, app/schemas/ (all replaced)
- app/ym/ (superseded by app/providers/yandex/)
- 15 DB tables: spotify_*, beatport_*, soundcloud_*, embeddings, transition_candidates, dj_saved_loops, dj_cue_points, dj_beatgrid_change_points, dj_set_constraints, dj_set_feedback, labels, track_labels, app_exports

### Fixed
- N/A — architectural release

### Notes
- Legacy code quarantined at app/v1_legacy/ — deleted in v1.1.0.
- Legacy tool names supported via scripts/compat_shims.py through v1.1.0.
```

- [ ] **Step 6: Commit + push**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add v1.0.0 entry"
git push origin dev
```

---

## Task 24: (Deferred to post-v1.0.0) — Sunset `app/v1_legacy/`

**Note:** THIS TASK IS NOT RUN IN PHASE 7. It's listed here as a successor task, scheduled ~2 weeks after v1.0.0 release (tracked separately as Phase 7.sunset or v1.1.0 issue).

Included here so that the cutover PR carries its own sunset plan, per blueprint §15.8 "Post-cutover (+1 release)".

### Scheduled actions (future task, DO NOT run here)

- [ ] Delete `app/v1_legacy/` directory.
- [ ] Delete `tests/v1_legacy/` directory.
- [ ] Delete `scripts/compat_shims.py` + `tests/scripts/test_compat_shims.py`.
- [ ] Remove `[importlinter:contract:legacy-sunset]` from `.importlinter`.
- [ ] Update `CLAUDE.md` to drop the "legacy quarantine" footnote.
- [ ] Tag `v1.1.0`.

### Criteria to trigger sunset

- 2 weeks elapsed since v1.0.0.
- No rollback has been requested or executed.
- No external consumer reported dependency on legacy names.
- BFS/L5 campaigns stable (>99% OK rate) for ≥ 7 days.

### Sunset PR

- Branch: `sunset/v1.0.0-legacy`.
- PR base: `dev`.
- Squash-merge; tag `v1.1.0` on `main`.

---

## Self-Review — Spec Coverage

Checklist against blueprint §15.8 (Phase 7 deliverables):

| Blueprint deliverable | Task(s) |
|---|---|
| Delete entries per §13.1 (engines, ym, infrastructure, etc.) | Tasks 10–15 |
| Move `app/` → `app/v1_legacy/` (stash for one release) | Task 16 |
| Move `app/v2/` → `app/` | Task 16 |
| Update `pyproject.toml`, `alembic.ini`, `start.sh`, scripts | Task 17 |
| Update panel `.env.local` references | Task 17 (no semantic change) |
| Update `CLAUDE.md` full rewrite | Task 5 |
| Update `docs/architecture.md`, `tool-catalog.md`, `structure.md` | Tasks 6, 7, 8 |
| Update `.claude/rules/*` | Task 9 |
| Campaign compatibility — BFS/L5 scripts migrate OR shim | Tasks 3, 20 |
| Full `make check` green | Tasks 10–17, 21 |
| Smoke test on VM | Tasks 19, 20 |
| Tag `v1.0.0` "The Blueprint" | Task 22 |
| Merge `dev` → `main` via PR (NOT direct push) | Task 22 |
| Post-cutover (+1 release): delete `app/v1_legacy/` | Task 24 (deferred) |

### Testing strategy coverage (blueprint §17.5)

| Campaign smoke step | Task |
|---|---|
| `scripts/vm_import_and_analyze.py --limit 5` | Task 20 Step 5 (VM log tail) |
| `build_set` equivalent via new tools | Task 19 (smoke covers `entity_create` for set_version) |
| `deliver_set` equivalent | Task 19 (smoke covers) |
| `sync_playlist pull` | Task 19 (explicit smoke case) |

### Risk mitigation coverage (blueprint §18.1)

| Risk | Mitigating task |
|---|---|
| BFS/L5 breaks during cutover | Task 3 (shims) + Task 4 (graceful stop) + Task 20 (controlled restart) |
| Migration drops a still-used column | Task 1 Step 5 + Task 18 Step 1 (staging dry-run) |
| Alembic breaks production DB | Task 1 Step 6 (backup) + Task 18 rollback block |
| Panel breaks despite out-of-scope | Task 8 Step 5 (server-action tool-name map) + Task 23 Step 4 (panel verification) |
| Docs drift from new code | Tasks 5–9 (all docs rewritten before swap), verified in Task 17 Step 7 (make check) |
| Hidden import from `app.v2.*` that wasn't updated | Task 15 Step 2 (leak scan) + Task 17 Step 5 (scripts scan) |

### Explicitly out of scope

- Panel refactor (blueprint §18.3, D2).
- Deletion of `app/v1_legacy/` (Task 24, scheduled for v1.1.0).
- Removal of `scripts/compat_shims.py` (same — v1.1.0).
- Alembic schema versioning beyond the migration applied in Task 18.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase-7-cutover.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — orchestrator dispatches a fresh subagent per task. Per-task rollback and verification make this the right fit for Phase 7's destructive nature. Strongly recommend pausing after Task 16 (the atomic swap) for a human-eyeball check before continuing.

**2. Inline Execution** — run via `superpowers:executing-plans`. Acceptable only if you intend to watch every command personally and can intervene inside the 90-minute downtime window.

**Critical human checkpoints (do NOT skip):**

1. **After Task 1 Step 9** — user "GO" required before destructive work.
2. **After Task 16** — inspect tree shape by hand before committing.
3. **After Task 18 Step 4** — confirm DB table count before proceeding.
4. **After Task 20 Step 7** — confirm BFS/L5 stable before merging PR.
5. **After Task 23 Step 4** — 24h soak before cutting the sunset PR.

**Branch protection reminder:** per project `git.md` rules, NEVER push directly to `main`. All promotions use `gh pr merge --squash`. The pre-push hook enforces this — if it errors, do not add `--no-verify`.

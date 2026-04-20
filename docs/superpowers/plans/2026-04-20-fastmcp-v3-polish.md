# FastMCP v3 Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md` (commit `548b572`)

**Goal:** Deduplicate 6 custom middleware against FastMCP v3 built-ins, migrate per-tool timeout from middleware to native `@tool(timeout=N)` across 20 tools (14 dispatch + 6 UI from PR #113), extend `fastmcp.json` with environment+env interpolation, fix CORS for browser MCP clients. Ship as `v1.0.4` patch across 3 sequential PRs directly against `main`.

**Architecture:** No surface-level MCP changes (13 tool dispatchers + 27 resources + 6 prompts unchanged). Internal refactor only: swap our middleware implementations for canonical FastMCP built-ins, move `TransientError` from middleware package to `app/shared/errors.py`, add `timeout=` parameter to all 14 `@tool` decorators, extend existing `fastmcp.json` with `environment` and `deployment.env` sections (interpolation from shell env).

**Tech Stack:** FastMCP v3.2.4, Python 3.12, uv, pytest, ruff, mypy, import-linter, starlette (CORS middleware), pydantic-settings.

**Scope discipline:**
- In scope: 10 changes across 3 PRs (§2 of spec).
- Non-goals: `@tool(task=True)` + Docket + Redis (separate `fastmcp-tasks-migration` spec); REST `/mcp` mount (coupled to Docket); docstring parameter descriptions; `ctx.transport` branching; EntityRegistry → Provider subclass refactor.

---

## File Structure

### Deleted in PR1 (6 files in `app/server/middleware/` + 5 tests)

- `app/server/middleware/otel_tracing.py` — replaced by FastMCP v3 native OTEL tracing
- `app/server/middleware/timing.py` — replaced by `fastmcp.server.middleware.timing.DetailedTimingMiddleware`
- `app/server/middleware/response_caching.py` — replaced by `fastmcp.server.middleware.caching.ResponseCachingMiddleware`
- `app/server/middleware/response_limit.py` — replaced by `fastmcp.server.middleware.response_limiting.ResponseLimitingMiddleware`
- `app/server/middleware/structured_logging.py` — replaced by `fastmcp.server.middleware.logging.StructuredLoggingMiddleware`
- `app/server/middleware/error_handling.py` — renamed to `domain_error.py` (content moves, not deletes)
- `tests/server/middleware/test_otel_tracing.py`, `test_timing.py`, `test_response_caching.py`, `test_response_limit.py`, `test_structured_logging.py`, `test_retry.py`

### Created in PR1

- `app/server/middleware/domain_error.py` — renamed from `error_handling.py`, class `ErrorHandlingMiddleware` → `DomainErrorMiddleware`
- `tests/server/middleware/test_domain_error.py` — renamed from `test_error_handling.py`

### Modified in PR1

- `app/shared/errors.py` — add `TransientError`
- `app/server/middleware/retry.py` — reduced to backward-compat shim re-exporting `TransientError` (kept for `v1.0.4`, removed in `v1.0.5`)
- `app/server/middleware/__init__.py` — full rewrite: imports of 5 built-ins + `build_middleware_list(settings)` function + `_READ_ONLY_TOOLS`
- `app/server/app.py` — `register_middleware(mcp)` calls `build_middleware_list(get_settings())`
- `tests/server/test_ordering.py` — count `16 → 15` + renamed classes in expected list
- `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` — §11 middleware table update
- `docs/architecture.md` — middleware count update

### Deleted in PR2 (1 file + 1 test)

- `app/server/middleware/tool_timeout.py` — replaced by native `@tool(timeout=N)` parameter
- `tests/server/middleware/test_tool_timeout.py`

### Modified in PR2

- `app/server/middleware/__init__.py` — remove `ToolCallTimeoutMiddleware` import from ordering
- `app/config/mcp.py` — drop `default_tool_timeout_s` field (unused after migration)
- `tests/server/test_ordering.py` — count `15 → 14` + remove class from expected list
- 14 files in `app/tools/**/*.py` — add `timeout=N` kwarg per §4.2 spec table

### Modified in PR3

- `fastmcp.json` — add `environment.{type,python,project}` and `deployment.env` with `${VAR}` interpolation
- `app/rest/app.py` — tighten CORS: explicit `allow_methods`, `allow_headers`, add `expose_headers`
- `.claude-plugin/plugin.json` — if env interpolation verification fails, add `source .env 2>/dev/null ||` before `exec`

### Modified in final release task

- `pyproject.toml` — version bump `1.0.3 → 1.0.4`
- `CHANGELOG.md` — add `[1.0.4]` section

---

## Pre-work: Sign-off Checklist (Task 0)

### Task 0: Verify spec §9 pre-PR1 sign-off checklist

**Files:**
- Read-only verification — no file changes.

- [ ] **Step 1: Verify `TransientError` importers are limited to middleware package + tests**

Run:
```bash
rg "from app.server.middleware.retry import" app/ tests/ scripts/ 2>&1
```
Expected:
```text
tests/server/middleware/test_retry.py:8:from app.server.middleware.retry import RetryMiddleware, TransientError
```

(Only one hit — the test file. No production code imports from the retry module. Handlers that raise `TransientError` today do so through domain-level abstractions, not by importing from middleware.)

**If additional hits appear**, document them — they will need import-path updates in Task 2.

- [ ] **Step 2: Enumerate `register_middleware` call sites**

Run:
```bash
rg "register_middleware" app/ tests/ 2>&1 | grep -v "\.pyc"
```
Expected hits:
```text
app/server/app.py:57:def register_middleware(mcp: FastMCP) -> None:
app/server/app.py:84:    register_middleware(mcp)
app/server/app.py:131:        register_middleware(mcp)
```

(Three hits — one definition, two call sites. Both call sites inside `app/server/app.py`, so signature changes are contained.)

- [ ] **Step 3: Confirm no production tool sets per-tool timeout today**

Run:
```bash
rg "tool\.meta\[.timeout_s.\]|meta=\{.*timeout_s" app/ tests/ scripts/ 2>&1
```
Expected:
```bash
tests/server/middleware/test_tool_timeout.py:18:    tool.meta = {"timeout_s": timeout} if timeout is not None else {}
```

(Only one hit — the test for the middleware we are deleting. No production tool uses the convention. Migration is safe.)

- [ ] **Step 4: Smoke-test `fastmcp run fastmcp.json` in a clean shell**

Run:
```bash
env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/local/bin bash -c \
  'cd $(git rev-parse --show-toplevel) && uv run fastmcp run fastmcp.json --no-banner 2>&1 | head -20'
```
Expected: server starts, emits FastMCP banner suppressed, logs `INFO dj-music-v2 MCP server built`, then hangs on STDIN (kill with Ctrl-C after confirming log line).

**If it fails to start**, check whether env vars from `.env` are needed — PR3 interpolation task will address this. For pre-work, we just want to know whether the current `fastmcp.json` works without `.env` vars.

- [ ] **Step 5: Commit sign-off summary as a note (no code change)**

This task has no git commit — it's pre-work recon. Record findings in the PR1 description when it opens.

---

## PR1: `refactor/middleware-dedupe`

### Task 1: Create PR1 branch from dev

**Files:** (none modified)

- [ ] **Step 1: Fetch latest main**

Run:
```bash
git fetch origin main
```

- [ ] **Step 2: Create branch**

Run:
```bash
git checkout -b refactor/middleware-dedupe origin/main
```

Expected: `Switched to a new branch 'refactor/middleware-dedupe'`

- [ ] **Step 3: Cherry-pick spec + plan amendments onto PR1 branch**

Spec (commit `46ee404` in the amendment-applied order, or use `git log claude/gracious-pascal-b5ec8d --oneline -5` to locate the current hashes) and plan commits must land in the first PR merge so they are available in `main` for later PR reviewers.

Run:
```bash
# Locate spec + plan commits from the worktree feature branch
SPEC=$(git rev-list --all --grep="docs: add FastMCP v3 polish design spec" -n 1)
PLAN=$(git rev-list --all --grep="docs: add FastMCP v3 polish implementation plan" -n 1)
AMEND=$(git rev-list --all --grep="docs: amend spec/plan" -n 1 2>/dev/null || true)

# Cherry-pick in the correct order (spec first, then plan, then amend if it exists)
git cherry-pick $SPEC $PLAN
if [ -n "$AMEND" ]; then git cherry-pick $AMEND; fi
```

Expected: two or three new commits on top of `origin/main`, tree clean.

- [ ] **Step 4: Verify working tree is clean**

Run:
```bash
git status
```
Expected: `nothing to commit, working tree clean`

### Task 2: Move `TransientError` to `app/shared/errors.py`

**Files:**
- Modify: `app/shared/errors.py` — append new class
- Test: `tests/shared/test_errors.py` — add test for new class

- [ ] **Step 1: Write failing test for the new location**

Create `tests/shared/test_errors.py` (or append if the file exists):

```python
"""Tests for app/shared/errors.py custom exception hierarchy."""

from __future__ import annotations

import pytest

from app.shared.errors import TransientError

def test_transient_error_is_exception_subclass() -> None:
    """TransientError must be raisable as a Python exception."""
    with pytest.raises(TransientError, match="network hiccup"):
        raise TransientError("network hiccup")

def test_transient_error_importable_from_shared() -> None:
    """Canonical import path is app.shared.errors."""
    from app.shared.errors import TransientError as _TE  # noqa: F401
```

Run:
```bash
uv run pytest tests/shared/test_errors.py -v 2>&1 | tail -20
```
Expected: failing import error — `ImportError: cannot import name 'TransientError' from 'app.shared.errors'`.

- [ ] **Step 2: Add `TransientError` to `app/shared/errors.py`**

Read the existing file to locate the insertion point (top of the file, alongside other exceptions). Add:

```python
class TransientError(Exception):
    """Marker for errors safe to retry.

    Raise from providers / DB / network layers when a call failed due to a
    transient condition (timeout, rate-limit, connection reset). The
    ``RetryMiddleware`` retries these with exponential backoff.
    """
```

Preserve existing docstrings and other exception classes (`NotFoundError`, `ValidationError`, `ConflictError`, `NotAllowedError`, `DJMusicError`).

- [ ] **Step 3: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/shared/test_errors.py -v 2>&1 | tail -20
```
Expected: `2 passed`.

- [ ] **Step 4: Commit**

Run:
```bash
git add app/shared/errors.py tests/shared/test_errors.py
```

Create commit message via Write tool (not HEREDOC — per `.claude/rules/git.md`):

Write `/tmp/dj-commit-msg.txt` with:
```bash
refactor(errors): move TransientError to app.shared.errors

Prepares PR1 middleware dedupe: RetryMiddleware will live in
fastmcp.server.middleware.error_handling (built-in), so the marker
exception has no reason to live in app/server/middleware/retry.py.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 3: Reduce `app/server/middleware/retry.py` to a re-export shim

**Files:**
- Modify: `app/server/middleware/retry.py` — shrink to backward-compat shim
- Test: `tests/shared/test_errors.py` — add back-compat import test

- [ ] **Step 1: Write failing test for backward-compat import path**

Append to `tests/shared/test_errors.py`:

```python
def test_transient_error_legacy_import_still_works() -> None:
    """Back-compat shim at app.server.middleware.retry must keep working
    until v1.0.4. Remove after one release cycle."""
    from app.server.middleware.retry import TransientError as _TE
    assert _TE is TransientError  # same class, not a fork
```

Run:
```bash
uv run pytest tests/shared/test_errors.py::test_transient_error_legacy_import_still_works -v 2>&1 | tail -10
```
Expected: fails because `app/server/middleware/retry.py` still defines its own `RetryMiddleware` and a local `TransientError` (not identical-by-identity with the new one in `app.shared.errors`).

Actually — re-read what happens. Current `retry.py` defines `class TransientError(Exception)` locally. `is` comparison will fail because Python class identity requires the **same** class object. So test SHOULD fail.

- [ ] **Step 2: Rewrite `app/server/middleware/retry.py` as a shim**

Replace the full file contents with:

```python
"""Back-compat shim — scheduled for removal in v1.0.4.

Historically this file defined ``RetryMiddleware`` and ``TransientError``.
As of v1.0.4:

- ``RetryMiddleware`` is imported from ``fastmcp.server.middleware.error_handling``.
- ``TransientError`` lives in ``app.shared.errors``.

This shim re-exports ``TransientError`` to keep third-party imports working
for one release cycle. Delete this file in v1.0.5.
"""

from __future__ import annotations

from app.shared.errors import TransientError

__all__ = ["TransientError"]
```

- [ ] **Step 3: Run back-compat test to verify it passes**

Run:
```bash
uv run pytest tests/shared/test_errors.py -v 2>&1 | tail -10
```
Expected: `3 passed`.

- [ ] **Step 4: Commit**

Run:
```bash
git add app/server/middleware/retry.py tests/shared/test_errors.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): reduce retry.py to TransientError re-export shim

Built-in fastmcp RetryMiddleware will replace our custom one in the
upcoming middleware dedupe. Keep legacy import path working for one
release cycle; file scheduled for deletion in v1.0.4.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 4: Delete `OTELTracingMiddleware`

**Files:**
- Delete: `app/server/middleware/otel_tracing.py`
- Delete: `tests/server/middleware/test_otel_tracing.py`

**Rationale:** FastMCP v3.0 ships native OTEL instrumentation with MCP semantic conventions (`tools/call {name}`, `gen_ai.tool.name`, `fastmcp.component.type`). Our middleware creates parallel spans named `mcp.tool.{name}`, duplicating data in traces.

- [ ] **Step 1: Confirm test file exists**

Run:
```bash
ls tests/server/middleware/test_otel_tracing.py 2>&1
```
Expected: file path echoed.

- [ ] **Step 2: Delete both files**

Run:
```bash
git rm app/server/middleware/otel_tracing.py tests/server/middleware/test_otel_tracing.py
```
Expected: two `rm` lines in output.

- [ ] **Step 3: Verify nothing else imports the deleted class**

Run:
```bash
rg "OTELTracingMiddleware" app/ tests/ 2>&1
```
Expected hits only in `app/server/middleware/__init__.py` (import + `ALL_MIDDLEWARE` entry). These are repaired in Task 12.

- [ ] **Step 4: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): drop OTELTracingMiddleware

FastMCP v3 ships native OpenTelemetry instrumentation with MCP semantic
conventions (tools/call {name}, gen_ai.tool.name, fastmcp.component.*).
Our custom middleware created parallel mcp.tool.{name} spans, duplicating
data in Jaeger/Grafana.

Downstream dashboard migration from mcp.tool.X to tools/call X is a
separate, out-of-band operation.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 5: Delete `DetailedTimingMiddleware` (custom) — built-in will replace

**Files:**
- Delete: `app/server/middleware/timing.py`
- Delete: `tests/server/middleware/test_timing.py`

**Rationale:** FastMCP ships `fastmcp.server.middleware.timing.DetailedTimingMiddleware` with the same class name and same per-operation tracking semantics.

- [ ] **Step 1: Delete both files**

Run:
```bash
git rm app/server/middleware/timing.py tests/server/middleware/test_timing.py
```

- [ ] **Step 2: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): drop custom DetailedTimingMiddleware

Replaced in __init__.py by fastmcp.server.middleware.timing
.DetailedTimingMiddleware (same class name, same behaviour, tested in
the FastMCP core test suite).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 6: Delete custom `RetryMiddleware` (test) — built-in will replace

**Files:**
- Delete: `tests/server/middleware/test_retry.py`

**Rationale:** The built-in `fastmcp.server.middleware.error_handling.RetryMiddleware` is tested in FastMCP core. The legacy file `app/server/middleware/retry.py` is already reduced to a shim (Task 3) — not deleted because it preserves `TransientError` re-export. Only the test file is deleted here.

- [ ] **Step 1: Delete test file**

Run:
```bash
git rm tests/server/middleware/test_retry.py
```

- [ ] **Step 2: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): drop custom RetryMiddleware tests

Built-in fastmcp.server.middleware.error_handling.RetryMiddleware
replaces our custom implementation; it is tested in the FastMCP core
suite. retry.py remains as a shim re-exporting TransientError.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 7: Delete `ResponseCachingMiddleware` (custom)

**Files:**
- Delete: `app/server/middleware/response_caching.py`
- Delete: `tests/server/middleware/test_response_caching.py`

**Rationale:** Built-in `fastmcp.server.middleware.caching.ResponseCachingMiddleware` accepts `CallToolSettings(ttl=..., included_tools=[...])` for per-operation control. Our custom kept the `readOnlyHint` discriminator inline; the built-in offloads that to explicit config (see Task 12).

- [ ] **Step 1: Delete both files**

Run:
```bash
git rm app/server/middleware/response_caching.py tests/server/middleware/test_response_caching.py
```

- [ ] **Step 2: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): drop custom ResponseCachingMiddleware

Replaced by fastmcp.server.middleware.caching.ResponseCachingMiddleware
with explicit CallToolSettings(included_tools=<read-only list>) wired
up in __init__.py. The built-in supports pluggable storage (RedisStore,
FileTreeStore) — future enhancement.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 8: Delete `ResponseLimitingMiddleware` (custom)

**Files:**
- Delete: `app/server/middleware/response_limit.py`
- Delete: `tests/server/middleware/test_response_limit.py`

**Rationale:** Built-in `fastmcp.server.middleware.response_limiting.ResponseLimitingMiddleware(max_size, truncation_suffix, tools=[...])` is a drop-in replacement.

- [ ] **Step 1: Delete both files**

Run:
```bash
git rm app/server/middleware/response_limit.py tests/server/middleware/test_response_limit.py
```

- [ ] **Step 2: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): drop custom ResponseLimitingMiddleware

Replaced by fastmcp.server.middleware.response_limiting
.ResponseLimitingMiddleware (same behaviour: cap response size, truncate
text responses, raise ToolError for structured ones).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 9: Delete `StructuredLoggingMiddleware` (custom)

**Files:**
- Delete: `app/server/middleware/structured_logging.py`
- Delete: `tests/server/middleware/test_structured_logging.py`

**Rationale:** Built-in `fastmcp.server.middleware.logging.StructuredLoggingMiddleware(include_payloads, max_payload_length, logger)` replaces ours.

- [ ] **Step 1: Delete both files**

Run:
```bash
git rm app/server/middleware/structured_logging.py tests/server/middleware/test_structured_logging.py
```

- [ ] **Step 2: Commit**

Write `/tmp/dj-commit-msg.txt`:
```text
refactor(middleware): drop custom StructuredLoggingMiddleware

Replaced by fastmcp.server.middleware.logging
.StructuredLoggingMiddleware(include_payloads=False,
max_payload_length=500). Matches our current log shape (enter/exit
records, session_id + request_id keys).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 10: Rename `error_handling.py` → `domain_error.py` (file + class)

**Files:**
- Rename: `app/server/middleware/error_handling.py` → `app/server/middleware/domain_error.py`
- Rename class: `ErrorHandlingMiddleware` → `DomainErrorMiddleware`

**Rationale:** FastMCP ships a built-in `fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware` too. Our class maps domain-level exceptions (`NotFoundError`, `ValidationError`, `ConflictError`, `NotAllowedError`, `DJMusicError`) to `ToolError` — clear behaviour, but the name collision invites confusion. Renaming to `DomainErrorMiddleware` conveys what it actually does.

- [ ] **Step 1: Git-move the file**

Run:
```bash
git mv app/server/middleware/error_handling.py app/server/middleware/domain_error.py
```

- [ ] **Step 2: Read the renamed file**

Run:
```bash
sed -n '1,80p' app/server/middleware/domain_error.py
```

- [ ] **Step 3: Rewrite docstring and class name**

Using Edit tool on `app/server/middleware/domain_error.py`:

Replace the module docstring (first triple-quoted block at top of file):

```python
"""Outermost middleware: map domain exceptions to MCP ``ToolError``.

Translates ``NotFoundError``, ``ValidationError``, ``ConflictError``,
``NotAllowedError``, and generic ``DJMusicError`` raised by repositories,
handlers, and domain logic into ``ToolError`` envelopes with stable
human-readable messages.

Unknown exceptions are wrapped with a generic message in production
(``mask_details=True``) or surfaced verbatim in dev.

Distinct from ``fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware``
(which focuses on exception logging and tracebacks — not domain mapping).
Rename from ``ErrorHandlingMiddleware`` landed in v1.0.4 to avoid the
name collision with the built-in.
"""
```

Replace the class definition line `class ErrorHandlingMiddleware(Middleware):` with `class DomainErrorMiddleware(Middleware):`.

- [ ] **Step 4: Verify no other references exist inside the file**

Run:
```bash
rg "ErrorHandlingMiddleware" app/server/middleware/domain_error.py
```
Expected: only the comment referencing the built-in in the docstring (if any).

- [ ] **Step 5: Commit**

Run:
```bash
git add app/server/middleware/domain_error.py
```

Write `/tmp/dj-commit-msg.txt`:
```python
refactor(middleware): rename ErrorHandling -> DomainError

FastMCP ships its own ErrorHandlingMiddleware. Our middleware maps
domain exceptions (NotFoundError/ValidationError/ConflictError/
NotAllowedError/DJMusicError) to ToolError — the new name describes
that intent unambiguously.

File renamed from error_handling.py to domain_error.py. Class renamed
from ErrorHandlingMiddleware to DomainErrorMiddleware. Behaviour
unchanged. Imports in __init__.py updated in a follow-up task.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 11: Rename test file and update imports + class references

**Files:**
- Rename: `tests/server/middleware/test_error_handling.py` → `tests/server/middleware/test_domain_error.py`
- Modify: test internals — update imports and class references

- [ ] **Step 1: Git-move the test file**

Run:
```bash
git mv tests/server/middleware/test_error_handling.py tests/server/middleware/test_domain_error.py
```

- [ ] **Step 2: Update imports inside the renamed test**

Find every occurrence of `ErrorHandlingMiddleware` and `error_handling` inside the file:

```bash
rg -n "ErrorHandlingMiddleware|error_handling" tests/server/middleware/test_domain_error.py
```

Using Edit tool, for each hit replace `ErrorHandlingMiddleware` with `DomainErrorMiddleware` and `error_handling` (module path) with `domain_error`. Preserve the rest of the test verbatim.

Example before:
```python
from app.server.middleware.error_handling import ErrorHandlingMiddleware
...
mw = ErrorHandlingMiddleware(mask_details=True)
```

Example after:
```python
from app.server.middleware.domain_error import DomainErrorMiddleware
...
mw = DomainErrorMiddleware(mask_details=True)
```

- [ ] **Step 3: Run renamed test to verify it passes**

Run:
```bash
uv run pytest tests/server/middleware/test_domain_error.py -v 2>&1 | tail -20
```
Expected: all existing test methods pass (behaviour unchanged).

- [ ] **Step 4: Commit**

Run:
```bash
git add tests/server/middleware/test_domain_error.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
test(middleware): rename test_error_handling -> test_domain_error

Mirror the module rename from Task 10. Test bodies updated only in
imports and class references; assertions unchanged.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 12: Rewrite `app/server/middleware/__init__.py`

**Files:**
- Modify: `app/server/middleware/__init__.py` — full rewrite: built-in imports + custom imports + `_READ_ONLY_TOOLS` + `build_middleware_list(settings)` + legacy `ALL_MIDDLEWARE` tuple for test compatibility

**Goal:** One module that both (a) exposes a `build_middleware_list(settings)` factory for the composition root and (b) keeps `ALL_MIDDLEWARE` tuple of classes for the existing ordering test in `tests/server/test_ordering.py`.

- [ ] **Step 1: Replace the file contents**

Write the following to `app/server/middleware/__init__.py`:

```python
"""Middleware pipeline — 15 classes after PR1 (14 after PR2 drops ToolCallTimeout).

Order is outermost→innermost; the first added wraps all others at call time.
Do not reorder without updating blueprint §11 and ``tests/server/test_ordering.py``.

Five middleware classes below are imported from ``fastmcp.server.middleware.*``:
``DetailedTimingMiddleware``, ``RetryMiddleware``, ``ResponseLimitingMiddleware``,
``ResponseCachingMiddleware``, ``StructuredLoggingMiddleware``. FastMCP v3 ships
these with the same semantics our hand-rolled versions had; the core test suite
covers their behaviour.

``DomainErrorMiddleware`` (formerly ``ErrorHandlingMiddleware``) is ours — it
maps domain exceptions to ``ToolError`` and is distinct from FastMCP's built-in
``ErrorHandlingMiddleware`` (which focuses on exception logging/tracebacks).

``OTELTracingMiddleware`` was removed: FastMCP v3 ships native OTEL instrumentation
with MCP semantic conventions. ``ToolCallTimeoutMiddleware`` will be removed in
PR2 and per-tool timeouts set via ``@tool(timeout=N)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListPromptsSettings,
    ListResourcesSettings,
    ListToolsSettings,
    ReadResourceSettings,
    ResponseCachingMiddleware,
)
from fastmcp.server.middleware.error_handling import RetryMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware

from app.server.middleware.audit_log import AuditLogMiddleware
from app.server.middleware.cost_tracking import CostTrackingMiddleware
from app.server.middleware.db_session import DbSessionMiddleware
from app.server.middleware.deprecation_warning import DeprecationWarningMiddleware
from app.server.middleware.domain_error import DomainErrorMiddleware
from app.server.middleware.progress_throttle import ProgressThrottleMiddleware
from app.server.middleware.provider_rate_limit import ProviderRateLimitMiddleware
from app.server.middleware.sampling_budget import SamplingBudgetMiddleware
from app.server.middleware.sentry_context import SentryContextMiddleware
from app.server.middleware.tool_timeout import ToolCallTimeoutMiddleware
from app.shared.errors import TransientError

if TYPE_CHECKING:
    from fastmcp.server.middleware import Middleware

    from app.config import Settings

# Tools whose outputs can be safely cached by name + args. Must match
# ``readOnlyHint=True`` annotations on the actual ``@tool`` declarations in
# ``app/tools/``. Passed to the built-in ``ResponseCachingMiddleware`` as
# ``CallToolSettings.included_tools`` so mutating tools are never cached.
_READ_ONLY_TOOLS: tuple[str, ...] = (
    "entity_list",
    "entity_get",
    "entity_aggregate",
    "provider_read",
    "provider_search",
    "transition_score_pool",
    # UI tools from PR #113 — all readOnlyHint=True, render Prefab dashboards.
    "ui_library_audit",
    "ui_library_dashboard",
    "ui_camelot_wheel",
    "ui_score_pool_matrix",
    "ui_set_view",
    "ui_transition_score",
)

def build_middleware_list(settings: "Settings") -> list["Middleware"]:
    """Construct the 15-middleware pipeline in canonical order (outer→inner)."""
    return [
        # 1 outermost — domain-error → ToolError translation
        DomainErrorMiddleware(mask_details=not settings.mcp.debug),
        # 2 — sentry breadcrumb context
        SentryContextMiddleware(),
        # (OTELTracingMiddleware removed — FastMCP v3 native tracing)
        # 3 — per-tool/resource/prompt timing (built-in)
        DetailedTimingMiddleware(),
        # 4 — audit-log of mutations
        AuditLogMiddleware(),
        # 5 — retry transient errors (built-in)
        RetryMiddleware(max_retries=2, retry_exceptions=(TransientError,)),
        # 6 — cap response size (built-in)
        ResponseLimitingMiddleware(max_size=settings.mcp.response_max_bytes),
        # 7 — cache read-only tool calls (built-in, explicit opt-in per tool)
        ResponseCachingMiddleware(
            call_tool_settings=CallToolSettings(
                ttl=settings.mcp.response_cache_ttl,
                included_tools=list(_READ_ONLY_TOOLS),
            ),
            list_tools_settings=ListToolsSettings(enabled=False),
            list_resources_settings=ListResourcesSettings(enabled=False),
            list_prompts_settings=ListPromptsSettings(enabled=False),
            read_resource_settings=ReadResourceSettings(enabled=False),
        ),
        # 8 — warn on deprecated tool version calls
        DeprecationWarningMiddleware(),
        # 9 — provider/LLM cost accounting
        CostTrackingMiddleware(),
        # 10 — LLM sampling budget per session
        SamplingBudgetMiddleware(),
        # 11 — throttle progress events to 1/sec
        ProgressThrottleMiddleware(),
        # 12 — per-tool timeout (removed in PR2 — @tool(timeout=N))
        ToolCallTimeoutMiddleware(),
        # 13 — Yandex Music rate limit
        ProviderRateLimitMiddleware(),
        # 14 — open UoW, commit/rollback
        DbSessionMiddleware(),
        # 15 innermost — structured log at tool boundary (built-in)
        StructuredLoggingMiddleware(include_payloads=False, max_payload_length=500),
    ]

# Legacy tuple — the classes in order, for the ordering test in
# ``tests/server/test_ordering.py``. Instances are built via
# ``build_middleware_list(settings)``; this tuple carries only types.
ALL_MIDDLEWARE: tuple[type, ...] = (
    DomainErrorMiddleware,
    SentryContextMiddleware,
    DetailedTimingMiddleware,
    AuditLogMiddleware,
    RetryMiddleware,
    ResponseLimitingMiddleware,
    ResponseCachingMiddleware,
    DeprecationWarningMiddleware,
    CostTrackingMiddleware,
    SamplingBudgetMiddleware,
    ProgressThrottleMiddleware,
    ToolCallTimeoutMiddleware,
    ProviderRateLimitMiddleware,
    DbSessionMiddleware,
    StructuredLoggingMiddleware,
)

__all__ = ["ALL_MIDDLEWARE", "_READ_ONLY_TOOLS", "build_middleware_list"]
```

- [ ] **Step 2: Quick sanity — count classes in `ALL_MIDDLEWARE`**

Run:
```bash
uv run python -c "from app.server.middleware import ALL_MIDDLEWARE; print(len(ALL_MIDDLEWARE))"
```
Expected: `15`.

- [ ] **Step 3: Run ordering test — will FAIL because count was 16, now 15**

Run:
```bash
uv run pytest tests/server/test_ordering.py -v 2>&1 | tail -15
```
Expected: two failures (`test_order_is_exactly_sixteen`, `test_order_matches_spec`). Task 14 fixes them.

- [ ] **Step 4: Commit**

Run:
```bash
git add app/server/middleware/__init__.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): rewrite __init__ with builtins + factory

Adds `build_middleware_list(settings)` that constructs the 15-middleware
pipeline. Imports DetailedTiming/Retry/ResponseLimiting/ResponseCaching/
StructuredLogging from fastmcp.server.middleware.* instead of local
modules (local modules removed in earlier tasks). Keeps `ALL_MIDDLEWARE`
tuple of classes for the ordering test.

Retains ToolCallTimeoutMiddleware; removed in PR2 once timeout= lands
on each @tool decorator.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 13: Update `app/server/app.py` to use `build_middleware_list`

**Files:**
- Modify: `app/server/app.py:57-60` — `register_middleware` body

**Goal:** `register_middleware(mcp)` now builds the list via `build_middleware_list(get_settings())` instead of iterating classes in `ALL_MIDDLEWARE` and instantiating each with no args. Signature unchanged (still `(mcp)`), so call sites at lines 84 and 131 stay.

- [ ] **Step 1: Read lines 1-70 of app.py to locate the edit site**

Run:
```bash
sed -n '1,70p' app/server/app.py
```

- [ ] **Step 2: Replace imports and `register_middleware` body**

Using Edit tool, change:

```python
from app.server.middleware import ALL_MIDDLEWARE
```

to:

```python
from app.config import get_settings
from app.server.middleware import build_middleware_list
```

And replace the function body:

```python
def register_middleware(mcp: FastMCP) -> None:
    """Register all 16 middleware in blueprint §11 order."""
    for cls in ALL_MIDDLEWARE:
        mcp.add_middleware(cls())
```

with:

```python
def register_middleware(mcp: FastMCP) -> None:
    """Register all 15 middleware in blueprint §11 order (14 after PR2)."""
    for mw in build_middleware_list(get_settings()):
        mcp.add_middleware(mw)
```

Also update the module docstring at line 10 (`4. ``register_middleware(mcp)`` — 16 middleware in blueprint §11 order.`) to read `15 middleware (14 after PR2)`.

- [ ] **Step 3: Sanity-check server builds**

Run:
```bash
uv run python -c "from app.server.app import build_mcp_server; mcp = build_mcp_server(); print('middleware count:', sum(1 for _ in mcp._middleware))"
```
Expected: `middleware count: 15`.

If you get `AttributeError: 'FastMCP' object has no attribute '_middleware'`, try a different accessor — e.g. `len(mcp._mcp_middleware)` or inspect via `dir(mcp)`. FastMCP's internal attribute name has not been exercised here previously; if it changed between versions, the build succeeds silently and we fall back to the ordering test in Task 14 as the count check.

- [ ] **Step 4: Commit**

Run:
```bash
git add app/server/app.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(server): use build_middleware_list instead of ALL_MIDDLEWARE

register_middleware() now delegates construction to
build_middleware_list(get_settings()). Instances get their settings
dependencies at build time (debug, response_max_bytes, response_cache_ttl)
rather than each middleware re-reading settings in its own __init__.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 14: Update `tests/server/test_ordering.py` to assert count=15 + new class names

**Files:**
- Modify: `tests/server/test_ordering.py`

- [ ] **Step 1: Read current test**

Run:
```bash
cat tests/server/test_ordering.py
```

- [ ] **Step 2: Rewrite the file**

Replace contents with:

```python
"""Middleware order matches blueprint §11. Do not reorder without updating spec."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE

def test_order_length_is_fifteen_after_pr1() -> None:
    """PR1 dropped OTELTracingMiddleware. PR2 will drop ToolCallTimeoutMiddleware."""
    assert len(ALL_MIDDLEWARE) == 15

def test_order_matches_spec() -> None:
    expected = [
        "DomainErrorMiddleware",
        "SentryContextMiddleware",
        # OTEL removed in PR1
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        "ToolCallTimeoutMiddleware",  # will drop in PR2
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    actual = [c.__name__ for c in ALL_MIDDLEWARE]
    assert actual == expected
```

- [ ] **Step 3: Run the test**

Run:
```bash
uv run pytest tests/server/test_ordering.py -v 2>&1 | tail -15
```
Expected: `2 passed`.

- [ ] **Step 4: Commit**

Run:
```bash
git add tests/server/test_ordering.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
test(ordering): assert len=15 and new class names post-PR1

OTELTracingMiddleware dropped, ErrorHandlingMiddleware renamed to
DomainErrorMiddleware. Five built-in classes keep the same names
(DetailedTiming/Retry/ResponseLimiting/ResponseCaching/StructuredLogging)
but come from fastmcp.server.middleware.*.

Next commit in PR2 will drop ToolCallTimeoutMiddleware -> len=14.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 15: Update blueprint docs for middleware count

**Files:**
- Modify: `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §11 table
- Modify: `docs/architecture.md` if it references 16 middleware

- [ ] **Step 1: Find existing §11 references**

Run:
```bash
rg "16 middleware|16 classes|sixteen middleware" docs/ 2>&1 | head -20
```

- [ ] **Step 2: Update blueprint §11**

Using Edit tool, in `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md`:
- Find the row for `OTELTracingMiddleware` in the §11 table (has `**new**` marker). Remove the row.
- Find the row for `ErrorHandlingMiddleware`. Update left column to `DomainErrorMiddleware`, keep the right column.
- Near §11 heading or intro text: if there's a phrase like "16 middleware" or "sixteen middleware", change to `15 middleware (14 after PR2 drops ToolCallTimeoutMiddleware in favour of @tool(timeout=N))`.

- [ ] **Step 3: Update `docs/architecture.md`**

Run:
```bash
rg "16 middleware|sixteen middleware" docs/architecture.md 2>&1
```

If matches exist, edit to `15 middleware`.

- [ ] **Step 4: Commit**

Run:
```bash
git add docs/
```

Write `/tmp/dj-commit-msg.txt`:
```bash
docs(blueprint): middleware count 16 -> 15 post-PR1

OTELTracingMiddleware removed (FastMCP v3 native OTEL). Renamed
ErrorHandlingMiddleware -> DomainErrorMiddleware to avoid name collision
with FastMCP's built-in ErrorHandlingMiddleware.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 16: Final PR1 verification + push + open PR

**Files:** (none modified)

- [ ] **Step 1: Full quality gate**

Run:
```bash
make check 2>&1 | tail -40
```
Expected: all green — `ruff check` pass, `ruff format --check` pass, `mypy app/` pass (no new errors introduced), `lint-imports` pass, `pytest -q` pass.

If mypy fails on `app/server/middleware/__init__.py` due to `TYPE_CHECKING` imports, run again and document. If `lint-imports` fails on a new cross-layer import, investigate the contract; do not widen without justification.

- [ ] **Step 2: Smoke-test server build in-process**

Run:
```bash
uv run python -c "from app.server.app import build_mcp_server; mcp = build_mcp_server(); print('OK — server built')"
```
Expected: `OK — server built` + no tracebacks.

- [ ] **Step 3: OTEL span check**

Run (one terminal):
```bash
opentelemetry-instrument --traces_exporter console --service_name dj-music-test \
  uv run python -c "
import asyncio
from fastmcp import Client
from app.server.app import build_mcp_server
mcp = build_mcp_server()
async def main():
    async with Client(mcp) as client:
        await client.list_tools()
asyncio.run(main())
" 2>&1 | grep -E "tools/call|mcp\.tool\." | head -10
```
Expected: span names beginning with `tools/call ...` (native). **No** spans named `mcp.tool.*`.

If `opentelemetry-instrument` is not installed, skip this step — it's a nice-to-have sanity check, not a correctness gate. Install is `pip install opentelemetry-distro opentelemetry-exporter-otlp && opentelemetry-bootstrap -a install`.

- [ ] **Step 4: Grep for dead references**

Run:
```bash
rg "OTELTracingMiddleware|ErrorHandlingMiddleware|app\.server\.middleware\.(otel_tracing|timing|response_caching|response_limit|structured_logging|error_handling)" app/ tests/ 2>&1
```
Expected: **no hits** in `app/` or `tests/`. If any remain, repair before pushing.

- [ ] **Step 5: Push branch**

Run:
```bash
git push -u origin refactor/middleware-dedupe
```

- [ ] **Step 6: Open PR**

Write `/tmp/dj-pr-body.md`:
```markdown
## Summary

Dedupe 6 custom middleware against FastMCP v3 built-ins, drop native-OTEL duplicate.

## Changes

- **Deleted** `OTELTracingMiddleware` — FastMCP v3 ships native OTEL tracing with MCP semantic conventions (`tools/call {name}`, `gen_ai.tool.name`). Our custom created parallel `mcp.tool.{name}` spans.
- **Replaced** 5 custom middleware with FastMCP built-ins (same class names, wrapped behaviour tested in FastMCP core):
  - `DetailedTimingMiddleware` → `fastmcp.server.middleware.timing.DetailedTimingMiddleware`
  - `RetryMiddleware` → `fastmcp.server.middleware.error_handling.RetryMiddleware` (with `retry_exceptions=(TransientError,)`)
  - `ResponseLimitingMiddleware` → `fastmcp.server.middleware.response_limiting.ResponseLimitingMiddleware`
  - `ResponseCachingMiddleware` → `fastmcp.server.middleware.caching.ResponseCachingMiddleware` (with explicit `CallToolSettings(included_tools=_READ_ONLY_TOOLS)`)
  - `StructuredLoggingMiddleware` → `fastmcp.server.middleware.logging.StructuredLoggingMiddleware`
- **Renamed** `ErrorHandlingMiddleware` → `DomainErrorMiddleware` (avoid collision with FastMCP's built-in `ErrorHandlingMiddleware`).
- **Moved** `TransientError` from `app/server/middleware/retry.py` to `app/shared/errors.py`; retry.py kept as a back-compat shim (deletable in v1.0.4).
- Middleware count: **16 → 15** (PR2 will drop `ToolCallTimeoutMiddleware` to reach 14).

Spec: `docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md`.

## Test plan

- [ ] `make check` green
- [ ] `uv run python -c "from app.server.app import build_mcp_server; build_mcp_server()"` succeeds
- [ ] OTEL sanity: native `tools/call X` spans present, no parallel `mcp.tool.X`
- [ ] `rg "OTELTracingMiddleware|ErrorHandlingMiddleware" app/ tests/` → no hits

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Run:
```bash
gh pr create --base main --title "refactor: dedupe middleware against FastMCP v3 built-ins" --body-file /tmp/dj-pr-body.md
rm /tmp/dj-pr-body.md
```

- [ ] **Step 7: Record PR URL**

Record the URL emitted by `gh pr create` — it will be referenced in PR2 and PR3 descriptions.

- [ ] **Step 8: Request human review**

PAUSE HERE. Wait for maintainer review and merge of PR1 before starting PR2. Any review findings are fixed in this branch via additional commits; do not cascade into PR2 branch.

---

## PR2: `refactor/tool-timeout-migration`

### Task 17: Create PR2 branch from updated main

**Files:** (none modified)

- [ ] **Step 1: Ensure PR1 is merged**

Run:
```bash
gh pr view refactor/middleware-dedupe --json state --jq .state
```
Expected: `"MERGED"`. If `"OPEN"`, wait.

- [ ] **Step 2: Sync main and branch**

Run:
```bash
git fetch origin main
git checkout -b refactor/tool-timeout-migration origin/main
```

### Task 18: Delete `tool_timeout.py` middleware + test

**Files:**
- Delete: `app/server/middleware/tool_timeout.py`
- Delete: `tests/server/middleware/test_tool_timeout.py`

- [ ] **Step 1: Delete both files**

Run:
```bash
git rm app/server/middleware/tool_timeout.py tests/server/middleware/test_tool_timeout.py
```

- [ ] **Step 2: Verify remaining references are only in `__init__.py`**

Run:
```bash
rg "ToolCallTimeoutMiddleware" app/ tests/ 2>&1
```
Expected hits only in `app/server/middleware/__init__.py` (import + `ALL_MIDDLEWARE` + `build_middleware_list`) and `tests/server/test_ordering.py`. Fixed in Tasks 19 and 22.

- [ ] **Step 3: Commit**

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(middleware): delete ToolCallTimeoutMiddleware module

FastMCP v3 supports per-tool timeouts natively via @tool(timeout=N).
Our middleware read tool.meta['timeout_s'], but no production tool
set that field — all fell through to the 300s default. Per-tool
decorator values land in the next commit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 19: Remove `ToolCallTimeoutMiddleware` from `app/server/middleware/__init__.py`

**Files:**
- Modify: `app/server/middleware/__init__.py` — drop import, drop from `build_middleware_list`, drop from `ALL_MIDDLEWARE` tuple

- [ ] **Step 1: Delete the import line**

Using Edit tool, remove:

```python
from app.server.middleware.tool_timeout import ToolCallTimeoutMiddleware
```

- [ ] **Step 2: Delete entry 12 from `build_middleware_list`**

Using Edit tool, remove these lines:

```python
        # 12 — per-tool timeout (removed in PR2 — @tool(timeout=N))
        ToolCallTimeoutMiddleware(),
```

Renumber comments below it: 13→12, 14→13, 15→14.

- [ ] **Step 3: Delete entry from `ALL_MIDDLEWARE` tuple**

Using Edit tool, remove the line `ToolCallTimeoutMiddleware,` from the tuple.

- [ ] **Step 4: Quick count check**

Run:
```bash
uv run python -c "from app.server.middleware import ALL_MIDDLEWARE; print(len(ALL_MIDDLEWARE))"
```
Expected: `14`.

- [ ] **Step 5: Commit**

Run:
```bash
git add app/server/middleware/__init__.py
```

Write `/tmp/dj-commit-msg.txt`:
```text
refactor(middleware): drop ToolCallTimeoutMiddleware from pipeline

Per-tool timeouts now land on each @tool(timeout=N) decorator (next
commit). Middleware count 15 -> 14.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 20: Add `timeout=N` to all 20 `@tool` decorators

**Files:** Modify 20 files per §4.2 of the spec (14 dispatch tools + 6 UI tools from PR #113).

**Per-tool timeout table (restated from spec §4.2):**

| File | Tool name | `timeout=` |
|---|---|---|
| `app/tools/entity/list.py` | `entity_list` | `30.0` |
| `app/tools/entity/get.py` | `entity_get` | `30.0` |
| `app/tools/entity/aggregate.py` | `entity_aggregate` | `30.0` |
| `app/tools/provider/read.py` | `provider_read` | `30.0` |
| `app/tools/provider/search.py` | `provider_search` | `30.0` |
| `app/tools/admin/unlock_namespace.py` | `unlock_namespace` | `30.0` |
| `app/tools/admin/tool_invoke.py` | `tool_invoke` | `30.0` |
| `app/tools/ui/library_audit.py` | `ui_library_audit` | `30.0` |
| `app/tools/ui/library_dashboard.py` | `ui_library_dashboard` | `30.0` |
| `app/tools/ui/camelot_wheel.py` | `ui_camelot_wheel` | `30.0` |
| `app/tools/ui/set_view.py` | `ui_set_view` | `30.0` |
| `app/tools/ui/transition_score.py` | `ui_transition_score` | `30.0` |
| `app/tools/entity/create.py` | `entity_create` | `120.0` |
| `app/tools/entity/update.py` | `entity_update` | `120.0` |
| `app/tools/entity/delete.py` | `entity_delete` | `120.0` |
| `app/tools/provider/write.py` | `provider_write` | `120.0` |
| `app/tools/sync/playlist_sync.py` | `playlist_sync` | `180.0` |
| `app/tools/compute/score_pool.py` | `transition_score_pool` | `300.0` |
| `app/tools/compute/sequence_optimize.py` | `sequence_optimize` | `300.0` |
| `app/tools/ui/score_pool_matrix.py` | `ui_score_pool_matrix` | `300.0` |

- [ ] **Step 1: Edit the 12 fast-read tools (timeout=30.0)**

For each of these files, locate the `@tool(...)` call and add `timeout=30.0` immediately after `description=...,` closing. Example for `app/tools/entity/list.py`:

Before:
```python
@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, and "
        "field projection. Use schema://entities/{entity} to discover available "
        "filters/presets."
    ),
)
```

After:
```python
@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, and "
        "field projection. Use schema://entities/{entity} to discover available "
        "filters/presets."
    ),
    timeout=30.0,
)
```

Apply to:
- `app/tools/entity/list.py`
- `app/tools/entity/get.py`
- `app/tools/entity/aggregate.py`
- `app/tools/provider/read.py`
- `app/tools/provider/search.py`
- `app/tools/admin/unlock_namespace.py`
- `app/tools/admin/tool_invoke.py`
- `app/tools/ui/library_audit.py`
- `app/tools/ui/library_dashboard.py`
- `app/tools/ui/camelot_wheel.py`
- `app/tools/ui/set_view.py`
- `app/tools/ui/transition_score.py`

- [ ] **Step 2: Edit the 4 write tools (timeout=120.0)**

Same pattern, value `120.0`:
- `app/tools/entity/create.py`
- `app/tools/entity/update.py`
- `app/tools/entity/delete.py`
- `app/tools/provider/write.py`

- [ ] **Step 3: Edit the 1 sync tool (timeout=180.0)**

- `app/tools/sync/playlist_sync.py` → `timeout=180.0`

- [ ] **Step 4: Edit the 3 compute tools (timeout=300.0)**

- `app/tools/compute/score_pool.py` → `timeout=300.0`
- `app/tools/compute/sequence_optimize.py` → `timeout=300.0`
- `app/tools/ui/score_pool_matrix.py` → `timeout=300.0`

- [ ] **Step 5: Verify all 20 files have a `timeout=` kwarg**

Run:
```bash
rg "timeout=" app/tools/ 2>&1
```
Expected: 20 lines, one per tool file. (Exclude any `_fallback.py` helper — it has no `@tool`.)

- [ ] **Step 6: Run tool metadata tests**

Run:
```bash
uv run pytest tests/tools/ -v 2>&1 | tail -30
```
Expected: existing tool metadata tests continue to pass. The `timeout=` kwarg is a FastMCP-supported parameter — it should not break existing tool registration or metadata assertions.

- [ ] **Step 7: Commit**

Run:
```bash
git add app/tools/
```

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(tools): add timeout= to all 14 @tool decorators

Per-tool timeouts now native FastMCP v3 parameter. Values per spec §4.2:

- Fast reads (30s): entity_list, entity_get, entity_aggregate,
  provider_read, provider_search, unlock_namespace, tool_invoke.
- Writes (120s): entity_create, entity_update, entity_delete,
  provider_write.
- Sync (180s): playlist_sync.
- Compute (300s): transition_score_pool, sequence_optimize.

Replaces tool.meta['timeout_s'] convention (never used in production)
+ ToolCallTimeoutMiddleware default fallback (300s for everything).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 21: Drop `default_tool_timeout_s` from config

**Files:**
- Modify: `app/config/mcp.py` — remove unused field

- [ ] **Step 1: Verify field is unused elsewhere**

Run:
```bash
rg "default_tool_timeout_s" app/ tests/ scripts/ 2>&1
```
Expected: only the definition line in `app/config/mcp.py`. If any usage remains in tests, migrate them to `tool_timeout_default_s` (which exists in the same file) first.

- [ ] **Step 2: Remove the field**

Using Edit tool, delete from `app/config/mcp.py`:

```python
    default_tool_timeout_s: float = Field(default=300.0, ge=1.0, le=3600.0)
```

- [ ] **Step 3: Run config tests**

Run:
```bash
uv run pytest tests/config/ -v 2>&1 | tail -15
```
Expected: pass.

- [ ] **Step 4: Commit**

Run:
```bash
git add app/config/mcp.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
refactor(config): drop unused MCPSettings.default_tool_timeout_s

Field was only read by ToolCallTimeoutMiddleware (deleted in previous
commits). Per-tool timeouts now live on @tool(timeout=N). The parallel
field tool_timeout_default_s (same default, different name) remains for
now — used elsewhere or reserved for future.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 22: Update `tests/server/test_ordering.py` to count=14

**Files:**
- Modify: `tests/server/test_ordering.py` — update asserted count + expected list

- [ ] **Step 1: Rewrite the file**

Replace contents with:

```python
"""Middleware order matches blueprint §11. Do not reorder without updating spec."""

from __future__ import annotations

from app.server.middleware import ALL_MIDDLEWARE

def test_order_length_is_fourteen_post_pr2() -> None:
    """PR1 dropped OTEL, PR2 dropped ToolCallTimeout."""
    assert len(ALL_MIDDLEWARE) == 14

def test_order_matches_spec() -> None:
    expected = [
        "DomainErrorMiddleware",
        "SentryContextMiddleware",
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    actual = [c.__name__ for c in ALL_MIDDLEWARE]
    assert actual == expected
```

- [ ] **Step 2: Run the test**

Run:
```bash
uv run pytest tests/server/test_ordering.py -v 2>&1 | tail -10
```
Expected: `2 passed`.

- [ ] **Step 3: Commit**

Run:
```bash
git add tests/server/test_ordering.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
test(ordering): assert len=14 post-PR2

ToolCallTimeoutMiddleware removed in favour of @tool(timeout=N). Final
middleware count for v1.0.4 is 14.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 23: PR2 verification + push + open PR

**Files:** (none modified)

- [ ] **Step 1: Full quality gate**

Run:
```bash
make check 2>&1 | tail -40
```
Expected: all green.

- [ ] **Step 2: Final timeout grep**

Run:
```bash
rg "timeout_s|default_tool_timeout|ToolCallTimeoutMiddleware|tool_timeout" app/ tests/ 2>&1
```
Expected result: only `app/providers/yandex/client.py` hits (HTTP client timeout — unrelated, keep). Everything else must be gone.

- [ ] **Step 3: Timeout visible in tool schema check**

Run:
```bash
uv run fastmcp inspect fastmcp.json --format fastmcp 2>&1 | head -80
```
Expected: each tool's JSON includes `timeout` field with one of the values from the §4.2 table. If the output format differs, use `uv run python -c "from app.server.app import build_mcp_server; import asyncio; mcp = build_mcp_server(); tools = asyncio.run(mcp.list_tools()); print([(t.name, getattr(t, 'timeout', None)) for t in tools])"`.

- [ ] **Step 4: Push branch**

Run:
```bash
git push -u origin refactor/tool-timeout-migration
```

- [ ] **Step 5: Open PR**

Write `/tmp/dj-pr-body.md`:
```markdown
## Summary

Migrate per-tool timeouts from custom middleware to native `@tool(timeout=N)` parameter.

## Changes

- **Deleted** `app/server/middleware/tool_timeout.py` and its test. Middleware count 15 → 14.
- **Added** `timeout=N` to all 20 `@tool(...)` decorators per spec §4.2 (14 dispatch + 6 UI from PR #113):
  - Fast reads (30s): `entity_list`, `entity_get`, `entity_aggregate`, `provider_read`, `provider_search`, `unlock_namespace`, `tool_invoke`, `ui_library_audit`, `ui_library_dashboard`, `ui_camelot_wheel`, `ui_set_view`, `ui_transition_score`.
  - Writes (120s): `entity_create`, `entity_update`, `entity_delete`, `provider_write`.
  - Sync (180s): `playlist_sync`.
  - Compute (300s): `transition_score_pool`, `sequence_optimize`, `ui_score_pool_matrix`.
- **Removed** `MCPSettings.default_tool_timeout_s` (only read by the deleted middleware).

## Behavioural note

Timeout violations now surface as native MCP error code `-32000` (`"Tool 'X' exceeded timeout of Ns"`) instead of `ToolError("tool 'X' timed out after Ns")`. No MCP client parses the text; structurally both are `CallToolResult(isError=True)`.

Spec: `docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md` §4.2.

## Test plan

- [ ] `make check` green
- [ ] `rg "timeout_s|ToolCallTimeoutMiddleware" app/ tests/` shows only `app/providers/yandex/client.py`
- [ ] `fastmcp inspect fastmcp.json --format fastmcp` — each tool reports its configured timeout

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Run:
```bash
gh pr create --base main --title "refactor: migrate tool timeouts to @tool(timeout=N)" --body-file /tmp/dj-pr-body.md
rm /tmp/dj-pr-body.md
```

- [ ] **Step 6: Wait for merge**

PAUSE HERE until PR2 is merged.

---

## PR3: `feat/fastmcp-json-and-cors`

### Task 24: Create PR3 branch from updated main

**Files:** (none modified)

- [ ] **Step 1: Ensure PR2 is merged**

Run:
```bash
gh pr view refactor/tool-timeout-migration --json state --jq .state
```
Expected: `"MERGED"`.

- [ ] **Step 2: Sync**

Run:
```bash
git fetch origin main
git checkout -b feat/fastmcp-json-and-cors origin/main
```

### Task 25: Extend `fastmcp.json` with `environment` and `deployment.env`

**Files:**
- Modify: `fastmcp.json`

- [ ] **Step 1: Replace file contents**

Write:

```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {
    "type": "filesystem",
    "path": "server.py",
    "entrypoint": "mcp"
  },
  "environment": {
    "type": "uv",
    "python": ">=3.12",
    "project": "."
  },
  "deployment": {
    "transport": "stdio",
    "log_level": "INFO",
    "env": {
      "DJ_DB_URL": "${DJ_DB_URL}",
      "DJ_YM_TOKEN": "${DJ_YM_TOKEN}",
      "DJ_YM_USER_ID": "${DJ_YM_USER_ID}",
      "DJ_YM_LIBRARY_PATH": "${DJ_YM_LIBRARY_PATH}",
      "DJ_SENTRY_DSN": "${DJ_SENTRY_DSN}",
      "DJ_MCP_CODE_MODE": "${DJ_MCP_CODE_MODE:-0}"
    }
  }
}
```

- [ ] **Step 2: JSON validity check**

Run:
```bash
uv run python -c "import json; json.load(open('fastmcp.json')); print('valid JSON')"
```
Expected: `valid JSON`.

- [ ] **Step 3: Commit**

Run:
```bash
git add fastmcp.json
```

Write `/tmp/dj-commit-msg.txt`:
```bash
feat(config): extend fastmcp.json with environment + env interpolation

environment.{type=uv,python>=3.12,project=.} lets `fastmcp run` and
`fastmcp dev inspector` manage the uv env declaratively.

deployment.env with ${VAR} interpolation surfaces DJ_* settings in a
single declarative spot. Secrets continue to live in .env (gitignored);
fastmcp run reads them from shell environment before launching.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 26: Verify env interpolation end-to-end

**Files:**
- (Possibly) Modify: `.claude-plugin/plugin.json` — add `source .env` before `exec` if needed

- [ ] **Step 1: Clean-shell smoke test**

Run:
```bash
env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/local/bin:$HOME/.local/bin bash -c \
  'cd $(git rev-parse --show-toplevel) && set -a && source .env 2>/dev/null && set +a && uv run fastmcp run fastmcp.json --no-banner 2>&1 | head -30' &
BG=$!
sleep 5
kill $BG 2>/dev/null
wait $BG 2>/dev/null
echo "--- end output ---"
```

Expected output: contains `INFO dj-music-v2 MCP server built` and **does not** contain `ValidationError` or `KeyError: 'DJ_DB_URL'`.

- [ ] **Step 2: Determine whether `plugin.json` needs a `source .env` change**

Inspect current `.claude-plugin/plugin.json`:

```bash
cat .claude-plugin/plugin.json
```

Current command:
```text
"bash -c \"cd \"${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}\" && exec uv run fastmcp run fastmcp.json --no-banner\""
```

If the Step 1 smoke test failed (interpolation returned empty strings), add `.env` sourcing. Using Edit tool, replace the command value for the `mcp` server with:

```text
"bash -c \"cd \\\"${DJ_PLUGIN_DEV_PATH:-${CLAUDE_PLUGIN_ROOT}}\\\" && set -a && source .env 2>/dev/null && set +a && exec uv run fastmcp run fastmcp.json --no-banner\""
```

(Note the `set -a && source .env 2>/dev/null && set +a &&` prefix that turns on auto-export, sources `.env`, turns it off, then `exec`s the server.)

If Step 1 passed without sourcing, **skip** this edit — `plugin.json` doesn't need to change.

- [ ] **Step 3: If `plugin.json` changed, commit**

Run:
```bash
git diff --stat .claude-plugin/plugin.json
```

If there are changes:

```bash
git add .claude-plugin/plugin.json
```

Write `/tmp/dj-commit-msg.txt`:
```text
fix(plugin): source .env before exec so fastmcp.json can interpolate

bash -c spawns a new shell that does not inherit .env values. Sourcing
.env with set -a / set +a auto-exports DJ_* vars into the environment
so fastmcp.json's ${VAR} interpolation finds them.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

If no changes, skip the commit — move to Task 27.

### Task 27: Fix CORS in `app/rest/app.py`

**Files:**
- Modify: `app/rest/app.py:18-24` — tighten CORS middleware

- [ ] **Step 1: Read current file**

Run:
```bash
cat app/rest/app.py
```

- [ ] **Step 2: Replace the `CORSMiddleware` block**

Using Edit tool, change:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

to:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "https://*.vercel.app"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )
```

- [ ] **Step 3: Run REST tests**

Run:
```bash
uv run pytest tests/rest/ -v 2>&1 | tail -20
```
Expected: existing REST tests pass (CORS is static config; tests rarely assert on it).

- [ ] **Step 4: Commit**

Run:
```bash
git add app/rest/app.py
```

Write `/tmp/dj-commit-msg.txt`:
```bash
feat(rest): CORS headers for browser MCP clients

Browser-resident MCP clients (MCP Inspector, any custom web client) send
`mcp-protocol-version` and `mcp-session-id` headers. With
allow_credentials=True + explicit allow_origins (not "*"), CORS preflight
requires explicit allow_headers rather than wildcard. Session tracking
requires expose_headers=["mcp-session-id"] so browser JS can read the
session ID from responses.

Also narrows allow_methods from ["*"] to explicit list (security
hygiene).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

### Task 28: CORS preflight verification

**Files:** (none modified)

- [ ] **Step 1: Start REST API**

Run in one terminal:
```bash
uv run --extra http uvicorn app.rest.app:api --host 0.0.0.0 --port 8000
```
Leave running.

- [ ] **Step 2: Preflight request**

In another terminal:

```bash
curl -i -X OPTIONS http://localhost:8000/api/tools/entity_list/call \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: mcp-session-id, mcp-protocol-version, authorization, content-type" \
  2>&1 | head -20
```

Expected response includes:
```text
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:3000
access-control-allow-credentials: true
access-control-allow-methods: GET, POST, DELETE, OPTIONS
access-control-allow-headers: mcp-protocol-version, mcp-session-id, Authorization, Content-Type
access-control-expose-headers: mcp-session-id
```

- [ ] **Step 3: Stop REST API**

Ctrl-C the `uvicorn` process in the first terminal.

- [ ] **Step 4: No commit needed — verification only**

### Task 29: PR3 verification + push + open PR

**Files:** (none modified)

- [ ] **Step 1: Full quality gate**

Run:
```bash
make check 2>&1 | tail -40
```
Expected: all green.

- [ ] **Step 2: Push branch**

Run:
```bash
git push -u origin feat/fastmcp-json-and-cors
```

- [ ] **Step 3: Open PR**

Write `/tmp/dj-pr-body.md`:
```markdown
## Summary

Extend `fastmcp.json` with declarative environment + env interpolation, fix CORS for browser MCP clients.

## Changes

- **`fastmcp.json`**: added `environment.{type=uv, python=">=3.12", project="."}` and `deployment.env` with `${VAR}` interpolation for DJ_* secrets. `fastmcp run` and `fastmcp dev inspector` now manage the uv env declaratively.
- **`.claude-plugin/plugin.json`** (if needed per verification): prepend `set -a && source .env && set +a &&` before `exec` so interpolation finds env vars.
- **`app/rest/app.py`**: tighten CORS middleware:
  - `allow_methods`: `["*"]` → `["GET", "POST", "DELETE", "OPTIONS"]`
  - `allow_headers`: `["*"]` → `["mcp-protocol-version", "mcp-session-id", "Authorization", "Content-Type"]`
  - `expose_headers`: added `["mcp-session-id"]` (required by browser JS to read session ID from response)

## Rationale

With `allow_credentials=True` + non-wildcard `allow_origins`, browser CORS preflights reject `allow_headers: "*"`. Browser MCP clients (MCP Inspector, custom web clients) need `mcp-session-id` exposed for session tracking.

Spec: `docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md` §4.3–§4.4.

## Test plan

- [ ] `make check` green
- [ ] Clean-shell `fastmcp run fastmcp.json` starts without `ValidationError`
- [ ] `curl -i -X OPTIONS http://localhost:8000/api/tools/entity_list/call -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: mcp-session-id, mcp-protocol-version, authorization, content-type'` returns expected access-control-allow-headers + expose-headers

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Run:
```bash
gh pr create --base main --title "feat: extend fastmcp.json + fix CORS for browser MCP clients" --body-file /tmp/dj-pr-body.md
rm /tmp/dj-pr-body.md
```

- [ ] **Step 4: Wait for merge**

PAUSE HERE until PR3 is merged.

---

## Release Task: `v1.0.4` tag + changelog

### Task 30: Bump version + changelog + tag on main

**Files:**
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`
- Create (optional): `docs/release-notes/v1.0.4.md`

No `dev → main` release PR is needed — this repo merges PRs directly to `main`. Task 30 runs on a short-lived release branch off `main`, merged into `main`, then tagged.

- [ ] **Step 1: Sync main locally**

Run:
```bash
git checkout main
git pull origin main
```

- [ ] **Step 2: Create release branch**

Run:
```bash
git checkout -b release/v1.0.4
```

- [ ] **Step 3: Bump version in `pyproject.toml`**

Using Edit tool, change:
```toml
version = "1.0.3"
```
to:
```toml
version = "1.0.4"
```

- [ ] **Step 4: Update CHANGELOG.md**

Prepend to the top of `CHANGELOG.md` (under any existing `## [Unreleased]` block or right below the main heading):

```markdown
## [1.0.4] — 2026-04-20

### Changed
- Replaced 5 custom middleware with canonical FastMCP v3 built-ins: `DetailedTimingMiddleware`, `RetryMiddleware`, `ResponseLimitingMiddleware`, `ResponseCachingMiddleware`, `StructuredLoggingMiddleware`. Behaviour equivalent, covered by FastMCP core tests.
- Renamed `ErrorHandlingMiddleware` → `DomainErrorMiddleware` to avoid name collision with FastMCP's built-in `ErrorHandlingMiddleware`. File renamed from `app/server/middleware/error_handling.py` to `app/server/middleware/domain_error.py`.
- Moved `TransientError` from `app/server/middleware/retry.py` to `app/shared/errors.py`. Legacy import path kept as a re-export shim until v1.0.5.
- Per-tool timeouts now via native `@tool(timeout=N)` parameter on 20 `@tool` decorators (14 dispatch + 6 UI from PR #113), replacing `ToolCallTimeoutMiddleware` reading `tool.meta["timeout_s"]`. Values per category (30s reads/UI, 120s writes, 180s sync, 300s compute/UI-compute).

### Added
- `fastmcp.json` `environment` section (uv / python ≥ 3.12 / project root) for declarative env management.
- `fastmcp.json` `deployment.env` with `${VAR}` interpolation for DJ_* secrets.
- CORS headers for browser MCP clients: `mcp-protocol-version`, `mcp-session-id` in `allow_headers`; `mcp-session-id` in `expose_headers`; explicit `allow_methods`.

### Removed
- `OTELTracingMiddleware` — FastMCP v3 ships native OpenTelemetry instrumentation with MCP semantic conventions.
- `ToolCallTimeoutMiddleware` — replaced by native `@tool(timeout=N)` parameter.
- `MCPSettings.default_tool_timeout_s` — unused after timeout migration.

### Breaking (internal to codebase only — MCP surface unchanged)
- Import: `from app.server.middleware.error_handling import ErrorHandlingMiddleware` → `from app.server.middleware.domain_error import DomainErrorMiddleware`.
- Import: `from app.server.middleware.retry import TransientError` → `from app.shared.errors import TransientError` (legacy path works until v1.0.5).
- Timeout error messages: `ToolError("tool 'X' timed out after Ns")` → native MCP error code `-32000` `"Tool 'X' exceeded timeout of Ns"`. No MCP client parses the text — structurally equivalent.
```

- [ ] **Step 5: Commit release changes**

Run:
```bash
git add pyproject.toml CHANGELOG.md
```

Write `/tmp/dj-commit-msg.txt`:
```bash
release: v1.0.4

FastMCP v3 polish — middleware dedupe, @tool(timeout=N) migration
across 20 tools (14 dispatch + 6 UI from PR #113), fastmcp.json
environment + env interpolation, CORS for browser MCP clients.

Spec: docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md
Plan: docs/superpowers/plans/2026-04-20-fastmcp-v3-polish.md

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Run:
```bash
git commit -F /tmp/dj-commit-msg.txt && rm /tmp/dj-commit-msg.txt
```

- [ ] **Step 6: Push branch and open release PR**

Run:
```bash
git push -u origin release/v1.0.4
```

Write `/tmp/dj-pr-body.md`:
```markdown
## Summary

Release `v1.0.4` — FastMCP v3 canonical polish. Version bump + CHANGELOG only; code changes already landed via PR1/PR2/PR3.

## Changelog

See `CHANGELOG.md` → `[1.0.4]` section.

## Test plan

- [ ] `make check` green on main
- [ ] `v1.0.4` tag created post-merge
- [ ] GitHub release published

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Run:
```bash
gh pr create --base main --title "Release: v1.0.4" --body-file /tmp/dj-pr-body.md
rm /tmp/dj-pr-body.md
```

- [ ] **Step 7: After merge, tag + GitHub release**

Once the release PR is squash-merged to main:

```bash
git checkout main
git pull origin main
git tag -a v1.0.4 -m "v1.0.4 — FastMCP v3 polish"
git push origin v1.0.4
```

Then:
```bash
gh release create v1.0.4 \
  --title "v1.0.4 — FastMCP v3 polish" \
  --notes "See CHANGELOG.md for details. Spec: docs/superpowers/specs/2026-04-20-fastmcp-v3-polish-design.md"
```

(Repo has no long-lived `dev` branch — nothing to merge back.)

---

## Appendix: command cheat-sheet

```bash
# Full quality gate
make check

# Middleware class count
uv run python -c "from app.server.middleware import ALL_MIDDLEWARE; print(len(ALL_MIDDLEWARE))"

# Server smoke
uv run python -c "from app.server.app import build_mcp_server; build_mcp_server()"

# Tool timeout introspection
uv run python -c "
from app.server.app import build_mcp_server
import asyncio
mcp = build_mcp_server()
tools = asyncio.run(mcp.list_tools())
for t in tools:
    print(t.name, getattr(t, 'timeout', None))
"

# Clean-shell fastmcp run test
env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/local/bin:$HOME/.local/bin bash -c \
  'cd $(git rev-parse --show-toplevel) && set -a && source .env 2>/dev/null && set +a && uv run fastmcp run fastmcp.json --no-banner'

# CORS preflight
curl -i -X OPTIONS http://localhost:8000/api/tools/entity_list/call \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: mcp-session-id, mcp-protocol-version"

# Final grep for dead timeout references (PR2)
rg "timeout_s|default_tool_timeout|ToolCallTimeoutMiddleware|tool_timeout" app/ tests/
# Expected: only app/providers/yandex/client.py (HTTP client timeout — unrelated)

# Final grep for dead middleware references (PR1)
rg "OTELTracingMiddleware|ErrorHandlingMiddleware|app\.server\.middleware\.(otel_tracing|timing|response_caching|response_limit|structured_logging|error_handling)" app/ tests/
# Expected: no hits
```

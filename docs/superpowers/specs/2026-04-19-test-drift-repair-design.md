# Test Drift Repair — Design

**Date:** 2026-04-19
**Scope:** Fix 19 of 22 pre-existing failing tests on `fix/drift-ym-download-bugs`; keep v1 architecture intact; changes limited to `tests/` tree.
**Out of scope:** Group A (`tests/models/test_transition.py` + `misc_repos::test_transition_pair`) — blocked by user's in-progress WIP in `app/models/transition*.py`.

---

## 1. Baseline

Full `pytest --override-ini 'addopts='` on `fix/drift-ym-download-bugs` HEAD (`7a13b19`):

- **22 failed**, 609 passed, 47 xfailed, 16 xpassed

Failures classified into 5 live groups + 1 blocked group:

| # | Group | Count | Root cause |
|---|---|---|---|
| A | `models/test_transition.py`, `misc_repos::test_transition_pair` | 4 | Chuzhoj WIP (`M app/models/transition*.py`) — fields `overall_score`, `bpm_distance`, `reaction` removed from ORM; tests not yet updated. **Blocked** — user asked not to touch. |
| B | `middleware/test_cost_tracking.py` (3) + `test_sampling_budget.py` (4) | 7 | `await fctx.set_state(...)` against `MagicMock()` returns a `MagicMock`, not a coroutine — `TypeError: object MagicMock can't be used in 'await' expression`. |
| C | `server/test_di.py` | 7 | Tests call accessors as sync (`assert get_uow(ctx) is uow`) but all DI accessors are `async def`. Plus 5 accessors now read from `lifespan_context` (my previous commit `7a13b19`), while tests still mock `state`. |
| D | `tools/entity/test_{delete,get,update}.py` (3) + `tools/provider/test_{read,search,write}.py` (4) | 7 | `tests/tools/conftest.py` patches `di._read_slot` only; `get_provider_registry` et al. go through `_read_lifespan` — mock never applied, DI resolution fails with `Failed to resolve dependency 'uow'/'registry'`. |
| E | `entity/test_get.py::test_get_not_found_raises`, `test_update.py::test_update_not_found_raises` | 2 (⊂ D) | `pytest.raises(..., match="not found")` catches the DI failure from group D instead of the expected `NotFoundError`. Fixes itself once D is repaired. |
| F | `config/test_settings_facade.py::test_settings_construction_without_env` | 1 | Loads ambient `.env`, so `database_url` becomes Supabase Postgres instead of the SQLite default the assertion expects. |

**Target:** 19 of 22 failures green after this change; A stays red (blocked).

---

## 2. Non-goals

- Do NOT modify anything under `app/`.
- Do NOT touch tests in group A.
- Do NOT introduce unrelated refactors or new test helpers beyond what the 19 fixes need.
- Do NOT touch `xfail` markers — they mark known pending implementation work unrelated to this drift.

---

## 3. Shared test helpers

Two small helpers, each placed in the narrowest `conftest.py` that needs it. No new top-level `tests/_fakes.py` module — keep the blast radius small.

### 3.1 `tests/server/middleware/conftest.py` — `make_async_ctx`

```python
def make_async_ctx(*, tool_name: str = "t", state: dict | None = None) -> MiddlewareContext:
    """MiddlewareContext with real-ish async state slots.

    Middleware under test does ``await fctx.set_state(...)`` — a plain
    MagicMock returns another MagicMock there, not a coroutine, which
    crashes with ``TypeError: object MagicMock can't be used in
    'await' expression``. This helper installs real async thunks that
    mutate an ordinary dict, so assertions like
    ``ctx.fastmcp_context.state["cost"]["llm_tokens"] += 1500`` still
    behave correctly.
    """
    state = state if state is not None else {}

    async def _set(key: str, value: Any, *, serializable: bool = True) -> None:
        state[key] = value

    async def _delete(key: str) -> None:
        state.pop(key, None)

    fctx = MagicMock()
    fctx.state = state
    fctx.set_state = _set
    fctx.delete_state = _delete
    msg = MagicMock()
    msg.name = tool_name
    return MiddlewareContext(message=msg, fastmcp_context=fctx)
```

**Consumers:** `test_cost_tracking.py`, `test_sampling_budget.py`, `test_db_session.py` (migrated from its inline copy).

### 3.2 `tests/server/conftest.py` — `make_di_ctx`

```python
def make_di_ctx(
    *, state: dict | None = None, lifespan: dict | None = None
) -> SimpleNamespace:
    """Context mock for app.server.di accessors.

    ``get_uow`` reads ``fastmcp_context.state``; the five lifespan-
    yielded accessors (``get_provider_registry``, analyzer/pipeline/
    session_store/transition_scorer/optimizer) read
    ``fastmcp_context.request_context.lifespan_context``. Callers
    populate whichever slot the accessor under test consults.
    """
    fctx = SimpleNamespace(state=dict(state or {}))
    if lifespan is not None:
        fctx.request_context = SimpleNamespace(lifespan_context=dict(lifespan))
    return SimpleNamespace(fastmcp_context=fctx)
```

**Consumers:** `test_di.py` only.

---

## 4. Per-group fixes

### 4.1 Group B — middleware async ctx (7 tests)

- Move helper into `tests/server/middleware/conftest.py` (new fixture module-level function, not a `pytest.fixture` — it's a plain factory).
- `test_cost_tracking.py`: replace local `_ctx(name)` with `make_async_ctx(tool_name=name, state={})`. No other assertions change.
- `test_sampling_budget.py`: same treatment.
- `test_db_session.py`: drop its inline `_ctx_with_factory` in favour of `make_async_ctx`, augment with `lifespan_context={"db_session_factory": factory}`.

### 4.2 Group C — rewrite `test_di.py` as async (7 tests)

Current file is a mix of dead patterns: sync calls, `state`-only mock, no `pytest.mark.asyncio`. Rewrite all 7 tests with:

- `@pytest.mark.asyncio` on every function.
- Use `make_di_ctx(state=...)` for the two `get_uow` tests.
- Use `make_di_ctx(lifespan=...)` for the five lifespan-backed accessors.
- Replace `get_*(ctx)` with `await get_*(ctx)`.
- `raises_when_missing` variants pass `lifespan={}` (or `state={}`) — accessor must then raise `RuntimeError` with the expected message.

Example after:

```python
@pytest.mark.asyncio
async def test_get_uow_returns_state_slot() -> None:
    uow = MagicMock(spec=UnitOfWork)
    ctx = make_di_ctx(state={"uow": uow})
    assert await get_uow(ctx) is uow

@pytest.mark.asyncio
async def test_get_provider_registry_returns_lifespan_slot() -> None:
    reg = MagicMock(spec=ProviderRegistry)
    ctx = make_di_ctx(lifespan={"provider_registry": reg})
    assert await get_provider_registry(ctx) is reg
```

Test names renamed from `_returns_state_slot` → `_returns_lifespan_slot` where the slot actually lives in lifespan context; names are documentation, leaving them stale would mislead future readers.

### 4.3 Group D — patch both resolvers (7 tests, no test changes)

Modify `tests/tools/conftest.py:86-96`. Replace:

```python
def _fake_read_slot(ctx, key, what): ...
monkeypatch.setattr(di, "_read_slot", _fake_read_slot)
```

with:

```python
def _fake_resolver(ctx, key, what):
    if key in _slots:
        return _slots[key]
    raise RuntimeError(f"{what} not initialized (test)")

monkeypatch.setattr(di, "_read_slot", _fake_resolver)
monkeypatch.setattr(di, "_read_lifespan", _fake_resolver)
```

`get_uow` (via `_read_slot`) and `get_provider_registry` (via `_read_lifespan`) now both hit the same test-side dict. Tests under `tests/tools/entity/` and `tests/tools/provider/` are unchanged — they simply start passing. Group E (`not_found` regex tests) is a strict subset of D and self-resolves.

### 4.4 Group F — isolate `.env` (1 test)

In `tests/config/test_settings_facade.py::test_settings_construction_without_env`:

```python
def test_settings_construction_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ):
        if k.startswith("DJ_"):
            monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None)
    assert s.database.database_url.startswith("sqlite")
    assert s.transition.weight_bpm == 0.20
```

`_env_file=None` is the pydantic-settings escape hatch that disables `.env` file loading for a single instance. Combined with the env var scrub, we exercise the true defaults path. Other tests in the file stay untouched — they explicitly rely on ambient env.

---

## 5. Execution order & commits

Single commit on `fix/drift-ym-download-bugs`, title:

> `fix(tests): repair mock drift blocking 19 pre-existing tests`

Body lists all 4 groups. No separate commit per group — they share the same "test drift" theme and the two helpers are trivial.

**Order of edits:**

1. `tests/server/middleware/conftest.py` — add `make_async_ctx`
2. `tests/server/middleware/test_cost_tracking.py`, `test_sampling_budget.py`, `test_db_session.py` — migrate to helper
3. `tests/server/conftest.py` — add `make_di_ctx`
4. `tests/server/test_di.py` — full rewrite (7 tests)
5. `tests/tools/conftest.py` — patch both resolvers
6. `tests/config/test_settings_facade.py` — one-test patch

---

## 6. Verification plan

1. After each group edit, run its narrow suite:
   - B: `uv run pytest tests/server/middleware/test_cost_tracking.py tests/server/middleware/test_sampling_budget.py tests/server/middleware/test_db_session.py --override-ini 'addopts='`
   - C: `uv run pytest tests/server/test_di.py --override-ini 'addopts='`
   - D: `uv run pytest tests/tools/entity tests/tools/provider --override-ini 'addopts='`
   - F: `uv run pytest tests/config/test_settings_facade.py --override-ini 'addopts='`
2. Final: full `uv run pytest --override-ini 'addopts='`.
3. **Success criterion:** `22 failed → ≤3 failed`. Remaining failures must all be group A (`tests/models/test_transition.py::*`, `tests/repositories/test_misc_repos.py::test_transition_pair`). Any other remaining failure is a regression, investigate before commit.
4. `uv run ruff check app/ tests/` — clean.
5. `uv run lint-imports` — no new contract violations.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| `Settings(_env_file=None)` not accepted by the installed pydantic-settings version | Fallback: `monkeypatch.chdir(tmp_path)` so no `.env` is in the resolution path. |
| `make_async_ctx` conflicts with local `_ctx` in migrated test files | Remove the local `_ctx`, import helper instead. Confirmed: all three files define their own `_ctx` — no cross-file conflict. |
| Replacing `di._read_lifespan` monkeypatch breaks a test that legitimately relied on real lifespan resolution | Confirmed by grep: no other test under `tests/tools/` reaches into lifespan directly. |
| `get_uow` accessor path uses `fctx.get_state` before falling back to `fctx.state` — `SimpleNamespace` has neither `get_state` nor the attribute until we assign | `_read_slot` handles the `AttributeError` via `try/except Exception: value = None` and then falls back to `state`. Verified in code. |

---

## 8. What we deliberately don't do

- No unified `tests/_fakes.py` module. Two tiny helpers close to their users is cheaper to read and debug than a centralized kit.
- No rewrite of `di.py` back to sync. That would revert part of commit `7a13b19` (my earlier fix that unblocked `transition_score_pool` and all `local://*` resources).
- No attempt to land group A's fix. The user has uncommitted work in those files and owns the model redesign.

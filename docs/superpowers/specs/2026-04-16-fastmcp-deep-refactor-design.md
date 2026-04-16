# FastMCP Deep Refactor — Design Spec

**Date:** 2026-04-16
**Scope:** DI cleanup, tool transforms, per-session visibility, middleware upgrade, prompts, resources, elicitation, structured output
**Approach:** B — Deep Refactor (modernize MCP stack under FastMCP 3+ patterns)
**Breaking:** Yes — dev environment, tests will be updated

---

## 1. DI Cleanup — Unified Context Injection

### Problem
Three inconsistent Context injection patterns coexist:
1. `ctx: Context | None = None` — leaks into JSON Schema as optional param
2. `ctx: Context = CurrentContext()` — correct DI, used only in `session_draft.py`
3. `Depends(get_context)` — re-exported in `__init__.py`, rarely used

DI parameters with `Field(description="Injected ...")` leak into tool schemas:
```python
svc: Annotated[SetService, Field(description="Injected set service")] = Depends(get_set_service)
```

### Solution
1. **All DI params**: plain `Depends()`, no `Field()` / `Annotated` wrappers
2. **Context**: unify on `CurrentContext()` from `fastmcp.dependencies`
3. **ToolContext**: remains as null-safe facade, initialized via `CurrentContext()`
4. **REST gateway**: `ToolContext._has_session()` already handles `request_context is None`

### Before/After
```python
# Before (3 variants):
async def my_tool(
    ctx: Context | None = None,
    svc: Annotated[SetService, Field(description="Injected")] = Depends(get_set_service),
): ...

# After (one pattern):
async def my_tool(
    svc: SetService = Depends(get_set_service),
    ctx: Context = CurrentContext(),
): ...
```

### Scope
~20 tool files, mechanical find-and-replace. Remove `get_context` re-export from dependencies `__init__.py`.

### Files
- `app/controllers/tools/**/*.py` — all tool files
- `app/controllers/resources/session_draft.py` — already uses `CurrentContext()`
- `app/controllers/dependencies/__init__.py` — remove `get_context` export

---

## 2. Tool Transforms — LLM-Friendly Interface

### Problem
`build_pre_constructor_transforms()` returns `[]`. Tool descriptions and arguments are raw from code. Complex tools have confusing signatures for LLMs.

### Solution
Create `ToolTransform` config in `transforms.py` for 10-15 complex tools.

#### Hide internal params
```python
ArgTransform(hide=True, default=10)  # top_n, batch_size, etc.
```

#### Rewrite descriptions centrally
```python
ToolTransform({
    "score_transitions": ToolTransformConfig(
        description="Score how well tracks blend together. 'set' for full audit, 'pair' for two tracks, 'track_candidates' for best neighbors.",
        args={
            "top_n": ArgTransform(hide=True, default=10),
        },
    ),
    "manage_set": ToolTransformConfig(
        args={
            "data": ArgTransform(
                description="Action payload. create: {name, template_name?}. update: {id, name?}. delete: {id}."
            ),
        },
    ),
})
```

#### Target tools
`manage_set`, `manage_playlist`, `manage_tracks`, `score_transitions`, `deliver_set`, `sync_playlist`, `analyze_batch`, `import_tracks`, `download_tracks`, `expand_playlist_ym`, `ym_playlists`, `ym_likes`, `track_feedback`, `transition_history`.

### Files
- `app/bootstrap/transforms.py` — expand `build_pre_constructor_transforms()`

---

## 3. Per-Session Visibility

### Problem
`unlock_tools` uses `ctx.fastmcp.enable(tags=...)` — global mutation. Multiple concurrent clients share visibility state.

### Solution
Switch to per-session visibility via `ctx.enable_components(tags=...)` / `ctx.disable_components(tags=...)`.

### Changes
1. `unlock_tools` action handlers: `ctx.fastmcp.*` → `ctx.*`
2. `apply_visibility_policy` in `bootstrap/visibility.py` — stays as global startup default
3. Status check: adapt from inspecting `server.transforms` Visibility objects to session-level query

### Prerequisite
Verify `ctx.enable_components` exists in fastmcp>=3.2.4. Bump version if needed.

### Files
- `app/controllers/tools/admin.py`
- `app/bootstrap/visibility.py` (verify, may not need changes)

---

## 4. Middleware Upgrade

### New middleware

| Middleware | Purpose | Position |
|-----------|---------|----------|
| `ResponseLimitMiddleware` | Cap tool response size (50K chars) to protect LLM context | After timing, before rate limit |
| `CachingMiddleware` | Cache static resource reads (ttl=300s) | After response limit, before YM rate limit |

### Extended timeouts
Add to `ToolCallTimeoutMiddleware`:
- `deliver_set: 300.0`
- `analyze_batch: 600.0`
- `separate_stems: 300.0`
- `analyze_track: 120.0`

### Final middleware order
1. `ToolCallTimeoutMiddleware` (extended)
2. `StructuredLoggingMiddleware`
3. `DetailedTimingMiddleware`
4. `ResponseLimitMiddleware` ← NEW
5. `CachingMiddleware` ← NEW
6. `YMRateLimitMiddleware`
7. `ErrorHandlingMiddleware`
8. `RetryMiddleware`

### Prerequisite
Verify availability of `ResponseLimitMiddleware` and `CachingMiddleware` in fastmcp>=3.2.4.

### Files
- `app/bootstrap/middleware.py`

---

## 5. Prompts — Improvement and Expansion

### 5a. Server instructions
Expand from one-liner to structured multi-line instructions in `server_builder.py`:
- Core workflow description
- How to start (dj_expert_session prompt)
- Resource discovery hints
- Category system explanation

### 5b. PromptResult on existing prompts
All 7 prompts: return `PromptResult(messages=[...], description="...")` instead of bare `list[Message]`.

### 5c. New prompt: `quick_mix_check`
Lightweight prompt for checking track compatibility:
- Params: `track_a: str`, `track_b: str`
- Steps: resolve tracks → explain_transition → summarize
- File: `app/controllers/prompts/workflows/quick_mix_check.py`

### 5d. New prompt: `taste_analysis`
Extract from `dj_expert_session` into standalone:
- Params: `limit: int = 500`
- Steps: get likes → get dislikes → pull features → compare → report
- File: `app/controllers/prompts/workflows/taste_analysis.py`

### Files
- `app/bootstrap/server_builder.py` — instructions
- `app/controllers/prompts/workflows/*.py` — all 7 existing + 2 new

---

## 6. Resources — Dict Returns + New Resources

### 6a. Return dict instead of json.dumps
All status/template resources: change return type from `str` (with manual `json.dumps`) to `dict[str, Any]`. FastMCP auto-serializes.

Exception: knowledge resources (`knowledge://vocabulary`, etc.) stay as `str` with `mime_type="application/json"` — large blobs, no benefit from structured parsing.

### 6b. New resource: `transition://{from_id}/{to_id}/score`
Cached transition score between two tracks. Read-only, delegating to `TransitionScorer`.

### 6c. New resource: `session://tool-history`
Last 20 tool calls in current session. Populated via `StructuredLoggingMiddleware.on_call_tool` writing to `ctx.set_state`.

### Files
- `app/controllers/resources/status.py` — dict returns
- `app/controllers/resources/templates.py` — dict returns
- `app/controllers/resources/snapshot.py` — dict returns
- `app/controllers/resources/transition_score.py` ← NEW
- `app/controllers/resources/session_history.py` ← NEW
- `app/controllers/middleware.py` — tool-history state tracking

---

## 7. Elicitation Cleanup + Structured Output

### 7a. Fix double break bug
`app/controllers/elicitation.py` line 145: remove duplicate `break`.

### 7b. Unify elicitation through ToolContext
Add `confirm()`, `choice()` methods to `ToolContext`, delegating to `safe_confirm`/`safe_choice`. Single entry point for all tool elicitation.

### 7c. Structured output — Pydantic return types
Create response models in `app/schemas/` for 5-7 key tools:
- `SetVersionResult` — for `commit_set_version`
- `TransitionScoreResult` — for `score_transitions`
- `SetArcPreview` — for `preview_set_arc`
- `LibraryStatsResult` — for `get_library_stats`
- `AuditResult` — for `audit_playlist`
- `SearchResult` — for `search_library`

FastMCP auto-generates `output_schema` from return type, improving LLM parsing.

### Files
- `app/controllers/elicitation.py` — bug fix
- `app/controllers/tools/_shared/context.py` — add confirm/choice
- `app/schemas/tool_responses.py` ← NEW
- `app/controllers/tools/sets.py`, `curation.py`, `search.py` — typed returns

---

## Implementation Order

Phases ordered by dependency and risk:

| Phase | Section | Risk | Reason |
|-------|---------|------|--------|
| 1 | §7a Bug fix | None | Independent, zero risk |
| 2 | §1 DI cleanup | Low | Mechanical, well-tested pattern |
| 3 | §3 Per-session visibility | Low | 1 file, isolated |
| 4 | §2 Tool transforms | Low | Additive, no existing code changes |
| 5 | §4 Middleware upgrade | Medium | Needs version verification |
| 6 | §6 Resources | Medium | Return type changes, test updates |
| 7 | §5 Prompts | Low | Additive mostly |
| 8 | §7b-c Elicitation + structured output | Medium | New schemas, tool signature changes |

### Verification
After each phase: `make check` (lint + typecheck + arch + test).

### FastMCP version
Current: `>=3.2.4`. May need bump for per-session visibility, ResponseLimitMiddleware, CachingMiddleware. Verify before phases 3-5.

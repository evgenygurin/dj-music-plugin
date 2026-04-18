# Phase 4 Complete — Resources + Prompts

Phase 4 of the DJ Music Plugin v2 blueprint refactor is complete across
chunks A, B, C, and D. This phase introduces the full resource surface
and the 6 workflow prompts of the v2 architecture.

## Deliverables

### Resources (27 URIs total)

- 8 static URIs — schema, session, reference blobs
- 19 parametric templates — track / playlist / set / transition /
  transition_history / session views

13 resource modules under ``app/v2/resources/`` plus 4 reference blobs
under ``app/v2/resources/reference/``.

### Prompts (6 workflows)

- ``dj_expert_session``        — knowledge priming
- ``build_set_workflow``       — 8-step set-building recipe
- ``deliver_set_workflow``     — export + optional YM sync
- ``expand_playlist_workflow`` — provider discovery + import
- ``full_pipeline``            — expand -> build -> deliver chain
- ``quick_mix_check``          — pair compatibility shortcut

### Import-linter contracts (18 total, 2 new)

- ``v2-resources-no-tools`` — resources must not import tools, handlers,
  provider adapters
- ``v2-prompts-pure`` — prompts are pure text builders; no repos, tools,
  providers, DB, sqlalchemy, httpx

## Test counts (Phase 4 surface)

```text
tests/v2/resources/:  combined with tests/v2/prompts/
tests/v2/prompts/  :  38 passed, 52 xfailed
```

The 52 xfails are reservations for Phase 5 server wiring
(``app/v2/server/app.py:build_mcp_app_for_tests``). All xfails use
``strict=False`` so they flip automatically to passing once Phase 5
lands the FileSystemProvider-backed FastMCP app.

## Verification

- ``uv run pytest tests/v2/resources/ tests/v2/prompts/ -q`` — green
  (38 passed, 52 xfailed).
- ``uv run ruff check app/v2/resources/ app/v2/prompts/
  tests/v2/resources/ tests/v2/prompts/`` — clean.
- ``uv run lint-imports`` — 18 kept, 0 broken.

## Phase 5 hand-off

1. Create ``app/v2/server/app.py`` with ``build_mcp_app_for_tests`` that
   composes ``FastMCP(name=...)`` + FileSystemProvider rooted at
   ``app/v2/resources/`` and ``app/v2/prompts/``. The docstring of
   ``app/v2/prompts/__init__.py`` lists the 6 prompt modules the FSP
   must pick up.
2. Wire DI (``get_uow``, ``get_session_store``,
   ``get_provider_registry``) via middleware + lifespan — the Phase 4
   conftests monkey-patch these in tests today.
3. Register any test-only helper tool (e.g. a session-id echo) needed
   by ``tests/v2/resources/test_session_resources.py``.
4. Flip the ``@pytest.mark.xfail(strict=False)`` markers off as tests
   start passing — or leave them (non-strict) so they self-heal.

# Phase 7 — Task 18 Migration Status

## Status: NO-OP (deferred)

The Phase 2 plan called for applying an Alembic migration
(`p2_drop_dead_tables`) that drops tables removed by the v2 architecture.

In the Phase 7 cutover worktree, however, the v2 tree has no Alembic
`migrations/` directory — the legacy `app/db/migrations/` was deleted in
Chunk C alongside the rest of the legacy package, and Phase 2's migration
was never authored inside `app/v2/db/`.

`alembic.ini` still points at `app/db/migrations`, which is now empty.

## What to do post-merge

1. After merging `worktree-phase-7-cutover` into `dev`, author a fresh
   Alembic baseline against the v1 (post-swap) schema:
   ```bash
   uv run alembic init app/db/migrations  # scaffold env.py
   uv run alembic revision --autogenerate -m "v1_0_0_baseline"
   uv run alembic upgrade head
   ```
2. Run against real Supabase (not the local SQLite DB) to capture the
   dropped-table diff.
3. Commit the baseline + any diff migrations separately.

## Why not in this worktree

- No Alembic scaffolding exists in v2.
- Supabase connection not available from the worktree `.env`.
- Would require authoring both `env.py` and a dropped-tables migration
  from scratch — outside Phase 7 Chunk D scope (which is the mechanical
  swap, not schema work).

Tracked as follow-up to Phase 7 — see `docs/superpowers/plans/2026-04-17-phase-7-cutover.md` Task 18 (line 1869).

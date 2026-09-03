# Cell 11 — Providers and Database

## Mission
Own persistence and external-provider integration.

## Read
- `app/models/**`, `app/repositories/**`, `app/db/**`, `app/providers/**`
- migrations, persistence/provider schemas and tests

## Scope
- SQLAlchemy mappings and aggregate persistence.
- Repository and Unit of Work transaction behavior.
- Database sessions, migrations and seeds.
- Supabase/Postgres integration and external provider adapters.

## Write ownership
- `app/models/**`, `app/repositories/**`, `app/db/**`, `app/providers/**`
- migrations only with explicit parent coordination.

## Constraints
- Preserve transaction boundaries and UoW semantics.
- Separate read-only inspection from mutation paths.
- Never add credentials or real environment values.
- GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with schema/provider changes, migration safety, tests, and risks.
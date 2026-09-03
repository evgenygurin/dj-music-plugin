# Cell 05 — Providers and Database

## Mission
Own persistence and external-provider integration: SQLAlchemy models/repositories/session infrastructure, migrations, and provider adapters.

## Read
- `AGENTS.md` and relevant `rules/`
- `app/models/**`
- `app/repositories/**`
- `app/db/**`
- `app/providers/**`
- provider/persistence schemas and tests
- Alembic migrations and database documentation

## Scope
- SQLAlchemy 2.0 aggregate roots and mappings.
- Repository and Unit of Work persistence behavior.
- DB sessions, migrations, seeds, and DB-facing infrastructure.
- Yandex Music and other external provider adapters.
- Provider-specific authentication/configuration contracts.

## Write ownership
- `app/models/**`
- `app/repositories/**`
- `app/db/**`
- `app/providers/**`
- migrations only when explicitly delegated by parent

## Do not touch
Pure domain algorithms, audio implementation, MCP composition, root secrets/config, or another cell's files.

## Constraints
- Preserve Unit of Work semantics and transaction boundaries.
- Keep read-only Supabase inspection separate from mutation paths.
- Never commit credentials or real environment values.
- Run GitNexus impact before symbol edits.

## Deliverable
`REPORT.md` with schema/provider changes, migration safety, transaction implications, external API risks, tests, and cross-cell dependencies.

# Cell 17 — BeatGrid Persistence

Own only `app/models/**`, `app/repositories/**`, `app/db/**` and related persistence tests/migrations. Do not edit domain or audio implementation.

Persist the new beatgrid/tempo analysis using existing SQLAlchemy/Postgres/Supabase conventions. Prefer metadata plus an external/object-storage reference for large arrays if that is already the repository pattern; do not put huge beat arrays into ordinary relational columns without evidence. Preserve migration compatibility and existing records.

Read cells 15 and 16 reports first. Add focused repository/model/migration tests. Do not require a live Supabase service or secrets. Finish with `.mece/cells/17-persistence/REPORT.md`.

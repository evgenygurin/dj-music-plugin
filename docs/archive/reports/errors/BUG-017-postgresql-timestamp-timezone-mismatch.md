# BUG-017: PostgreSQL timestamp timezone mismatch

**Status**: Fixed
**Severity**: Critical (blocks all writes to PostgreSQL)
**Found**: 2026-04-06
**Fixed**: 2026-04-06

## Symptom

`import_tracks` fails with:
```bash
asyncpg.exceptions.DataError: invalid input for query argument $4:
datetime.datetime(2026, 4, 6, 13, 40, 8, ..., tzinfo=datetime.timezone.utc)
(can't subtract offset-naive and offset-aware datetimes)
```

## Root Cause

All 70 timestamp columns across 35 tables were defined as `TIMESTAMP WITHOUT TIME ZONE` (SQLAlchemy default `DateTime()`), but `utc_now()` returns timezone-aware datetime (`datetime.now(UTC)`).

SQLite ignores this mismatch. PostgreSQL (via asyncpg) rejects it.

## Fix

1. Updated `TimestampMixin` in `app/models/base.py`: `DateTime()` → `DateTime(timezone=True)`
2. Updated `fetched_at` in `app/models/ingestion.py`: added `DateTime(timezone=True)`
3. Updated `added_at` in `app/models/playlist.py`: added `DateTime(timezone=True)`
4. Created Alembic migration `bdc73180c4b9` to ALTER all 70 columns to `TIMESTAMP WITH TIME ZONE`

## Related

Also found: `.mcp.json` used `${CLAUDE_PLUGIN_ROOT}` which is only available inside Claude Code plugins, not regular MCP servers. Replaced with absolute path.

"""Audit iter 50 (T-48): asyncpg ``ForeignKeyViolationError`` (and
unique-key collisions) leaked the raw SQL trace to MCP clients::

    entity_create(playlist, {"name":"x", "parent_id": 99999})
    -> (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) ...
       FOREIGN KEY constraint "dj_playlists_parent_id_fkey" ...
       Key (parent_id)=(99999) is not present in table "dj_playlists"
       [SQL: INSERT INTO dj_playlists ...]

The full SQL + parameter dump shouldn't reach end users — and the
caller can't tell from the wall of text what they did wrong.
``BaseRepository.create`` / ``update`` / ``delete`` now catch
``IntegrityError`` and convert via
``_integrity_error_to_validation``:

- FK violation -> "foreign key violation on Playlist.parent_id:
  value '99999' does not exist in dj_playlists"
- Unique collision -> "unique constraint violation on Track"
- Anything else -> "integrity violation on X"

SQLite's IntegrityError messages don't match the exact Postgres
phrase ("Key (col)=(val) is not present in table") so we rely on
the asyncpg pattern for FK detail extraction; the SQLite path
falls into the generic "integrity violation" bucket. Same shape,
typed error.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def repos(
    engine: AsyncEngine, session: AsyncSession
) -> tuple[PlaylistRepository, SetRepository]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return PlaylistRepository(session), SetRepository(session)


@pytest.mark.asyncio
async def test_repo_create_wraps_integrity_error(
    repos: tuple[PlaylistRepository, SetRepository],
) -> None:
    """The wrapping happens at the repository layer regardless of
    backend. We can't rely on SQLite to actually enforce FKs (off
    by default), so verify the wrapping by patching ``flush`` to
    raise a synthetic ``IntegrityError`` and catching the conversion.
    """
    from unittest.mock import patch

    from sqlalchemy.exc import IntegrityError

    pl_repo, _ = repos

    class _FakeOrig:
        def __str__(self) -> str:
            return (
                'insert or update on table "dj_playlists" violates foreign key '
                'constraint "dj_playlists_parent_id_fkey"\n'
                'DETAIL:  Key (parent_id)=(99999) is not present in table "dj_playlists".'
            )

    fake_exc = IntegrityError("INSERT", {}, _FakeOrig())
    with (
        patch.object(pl_repo.session, "flush", side_effect=fake_exc),
        pytest.raises(ValidationError, match=r"foreign key"),
    ):
        await pl_repo.create(name="x", parent_id=99999)


@pytest.mark.asyncio
async def test_pure_function_maps_fk_detail_string() -> None:
    """The pure mapper extracts column / value / parent table from
    the asyncpg-style detail string."""
    from sqlalchemy.exc import IntegrityError

    from app.repositories.base import _integrity_error_to_validation

    # Forge an IntegrityError carrying the asyncpg detail format.
    class _FakeOrig:
        def __str__(self) -> str:
            return (
                'insert or update on table "dj_playlists" violates foreign key '
                'constraint "dj_playlists_parent_id_fkey"\n'
                'DETAIL:  Key (parent_id)=(99999) is not present in table "dj_playlists".'
            )

    err = IntegrityError("INSERT", {}, _FakeOrig())
    out = _integrity_error_to_validation(err, "DjPlaylist")
    assert "foreign key" in str(out).lower()
    assert "DjPlaylist.parent_id" in str(out)
    assert out.details is not None
    assert out.details["column"] == "parent_id"
    assert out.details["value"] == "99999"
    assert out.details["parent_table"] == "dj_playlists"


@pytest.mark.asyncio
async def test_pure_function_maps_undefined_column() -> None:
    """Audit iter 52 (T-50): ``UndefinedColumnError`` from a stale
    Supabase schema (Alembic migration not applied) used to leak the
    SQL trace. Now mapped to "schema mismatch" with column + table."""
    from sqlalchemy.exc import ProgrammingError

    from app.repositories.base import _programming_error_to_validation

    class _FakeOrig:
        def __str__(self) -> str:
            return 'column "kind" of relation "track_feedback" does not exist'

    err = ProgrammingError("INSERT", {}, _FakeOrig())
    out = _programming_error_to_validation(err, "TrackFeedback")
    assert "schema mismatch" in str(out).lower()
    assert "'kind'" in str(out)
    assert out.details is not None
    assert out.details["column"] == "kind"
    assert out.details["table"] == "track_feedback"


@pytest.mark.asyncio
async def test_pure_function_maps_undefined_table() -> None:
    """Missing table → schema mismatch with table name."""
    from sqlalchemy.exc import ProgrammingError

    from app.repositories.base import _programming_error_to_validation

    class _FakeOrig:
        def __str__(self) -> str:
            return 'relation "transitions" does not exist'

    err = ProgrammingError("SELECT", {}, _FakeOrig())
    out = _programming_error_to_validation(err, "Transition")
    assert "schema mismatch" in str(out).lower()
    assert "'transitions'" in str(out)
    assert out.details is not None
    assert out.details["table"] == "transitions"


@pytest.mark.asyncio
async def test_pure_function_maps_unique_collision() -> None:
    """Unique-constraint collisions get their own bucket."""
    from sqlalchemy.exc import IntegrityError

    from app.repositories.base import _integrity_error_to_validation

    class _FakeOrig:
        def __str__(self) -> str:
            return 'duplicate key value violates unique constraint "tracks_external_id_key"'

    err = IntegrityError("INSERT", {}, _FakeOrig())
    out = _integrity_error_to_validation(err, "Track")
    assert "unique" in str(out).lower()

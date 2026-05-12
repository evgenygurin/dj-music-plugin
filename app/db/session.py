"""Async engine + session factory.

The engine is constructed lazily via ``get_engine()`` so tests can
substitute their own URL without touching process-level state.

SQLite FK enforcement
---------------------
SQLite ships with foreign-key enforcement OFF by default; an orphan
``INSERT INTO child(parent_id) VALUES (9999)`` writes the row silently
even when ``parent_id`` is a ``FOREIGN KEY`` to a non-existent parent.
This diverges from PostgreSQL's behaviour and lets bugs slip through
the tests-on-SQLite / prod-on-PG path.

The canonical SQLAlchemy fix is a ``connect`` event listener that
issues ``PRAGMA foreign_keys=ON`` on every new connection (see
``https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support``).
Hook into the **sync** engine wrapped by ``AsyncEngine`` so it fires
for every aiosqlite connection in the pool, exactly once per connect.
With this in place the DB itself rejects orphan FK refs as
``IntegrityError("FOREIGN KEY constraint failed")``, which the repo
layer (``_integrity_error_to_validation``) converts into a typed
``ValidationError``. The application-level ``validate_fk_constraints``
gate (see ``app/tools/entity/_fk_gate.py``) is layered on top for
informative messages naming the bad id — defense in depth.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """Issue ``PRAGMA foreign_keys=ON`` on every new SQLite connection.

    Listens on the base ``Engine`` class so it covers every SQLAlchemy
    engine in the process (including those built lazily inside tests).
    The dialect filter is duck-typed: aiosqlite's dbapi connection
    exposes ``isolation_level`` like stdlib ``sqlite3.Connection`` and
    ships with no native FK enforcement. For non-SQLite drivers the
    cursor / pragma combination would raise, so we filter cleanly via
    class-name check rather than ``isinstance(..., sqlite3.Connection)``
    (which fails to match aiosqlite's wrapper class).
    """
    cls_name = type(dbapi_connection).__module__.lower()
    if "sqlite" not in cls_name:
        return
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def get_engine() -> AsyncEngine:
    """Return the process-wide engine, constructing it on first call."""
    global _engine
    if _engine is None:
        s = get_settings().database
        kwargs: dict[str, object] = {"echo": s.db_echo}
        if "postgresql" in s.database_url:
            kwargs["pool_pre_ping"] = s.db_pool_pre_ping
            kwargs["pool_size"] = s.db_pool_size
            kwargs["connect_args"] = {"statement_cache_size": s.db_statement_cache_size}
        _engine = create_async_engine(s.database_url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session maker."""
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _factory


async def dispose() -> None:
    """Dispose the engine. Call in lifespan teardown."""
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _factory = None

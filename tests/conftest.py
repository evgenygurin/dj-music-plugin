"""Shared test fixtures for DJ Music Plugin.

All fixtures use async SQLAlchemy with in-memory SQLite.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base


@pytest.fixture
async def async_engine():
    """In-memory async SQLite engine with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(async_engine) -> AsyncSession:  # type: ignore[no-untyped-def]
    """Async session that rolls back after each test."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seeded_db(db):  # type: ignore[no-untyped-def]
    """Session with reference data: 24 Camelot keys."""
    from app.core.constants import CAMELOT_KEYS

    # Lazy import — models may not exist yet during early tasks
    try:
        from app.models.key import Key

        for code, (camelot, name) in CAMELOT_KEYS.items():
            mode = 1 if camelot.endswith("B") else 0
            pitch_class = code % 12
            db.add(
                Key(
                    key_code=code,
                    pitch_class=pitch_class,
                    mode=mode,
                    name=name,
                    camelot=camelot,
                )
            )
        await db.flush()
    except ImportError:
        pass  # Key model not yet created

    yield db

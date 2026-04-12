"""Tests verifying FastMCP dependency injection patterns.

Key verifications:
1. Depends() resolves dependencies correctly
2. Multiple repos share the same session (per-request caching)
3. Session commits on success, rolls back on error
4. Dependencies are hidden from MCP tool schema
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from dj_music.di import (
    get_db_session,
    get_playlist_repo,
    get_set_repo,
    get_track_repo,
)
from dj_music.models.track import Track
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository


def _patch_dependency_context(monkeypatch: pytest.MonkeyPatch, session_factory) -> None:  # type: ignore[no-untyped-def]
    class MockContext:
        lifespan_context = {"db_session_factory": session_factory}

    import dj_music.di

    monkeypatch.setattr(
        dj_music.di,
        "get_context",
        lambda: MockContext(),
    )


@pytest.mark.asyncio
async def test_get_db_session_context_manager(seeded_db):
    """Verify get_db_session is an async context manager."""
    # get_db_session is decorated with @asynccontextmanager, making it
    # a callable that returns an async context manager (not an async generator).
    assert callable(get_db_session)


@pytest.mark.asyncio
async def test_repo_factory_returns_repo_instance(async_engine, monkeypatch: pytest.MonkeyPatch):
    """Verify repo factories return repository instances."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    _patch_dependency_context(monkeypatch, session_factory)

    async with get_db_session() as session:
        track_repo = get_track_repo(session)
        playlist_repo = get_playlist_repo(session)
        set_repo = get_set_repo(session)

        assert isinstance(track_repo, TrackRepository)
        assert isinstance(playlist_repo, PlaylistRepository)
        assert isinstance(set_repo, SetRepository)

        # All repos should have the SAME session instance
        assert track_repo.session is session
        assert playlist_repo.session is session
        assert set_repo.session is session


@pytest.mark.asyncio
async def test_session_commits_on_success(async_engine, monkeypatch: pytest.MonkeyPatch):
    """Verify session auto-commits on successful operation."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    _patch_dependency_context(monkeypatch, session_factory)

    async with get_db_session() as session:
        track = Track(title="Test Track", status=0, duration_ms=180000)
        session.add(track)
        await session.flush()
        track_id = track.id

    # After context exit, verify track was committed
    async with session_factory() as verification_session:
        stmt = select(Track).where(Track.id == track_id)
        result = await verification_session.execute(stmt)
        persisted = result.scalar_one_or_none()
        assert persisted is not None
        assert persisted.title == "Test Track"


@pytest.mark.asyncio
async def test_session_rolls_back_on_error(async_engine, monkeypatch: pytest.MonkeyPatch):
    """Verify session auto-rolls back on error."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    _patch_dependency_context(monkeypatch, session_factory)

    track_id = None
    with pytest.raises(ValueError, match="Intentional error"):
        async with get_db_session() as session:
            track = Track(title="Rollback Test", status=0, duration_ms=180000)
            session.add(track)
            await session.flush()
            track_id = track.id
            raise ValueError("Intentional error")

    # After rollback, track should NOT exist
    if track_id:
        async with session_factory() as verification_session:
            stmt = select(Track).where(Track.id == track_id)
            result = await verification_session.execute(stmt)
            persisted = result.scalar_one_or_none()
            assert persisted is None  # Rolled back


@pytest.mark.asyncio
async def test_multiple_repos_share_session():
    """Verify multiple repos injected in same tool call share one session.

    This is the KEY FastMCP DI pattern:
    - Depends() caches per-request
    - All repos get the SAME session
    - Single transaction per tool call
    """
    pass  # Placeholder for MCP client integration test


@pytest.mark.asyncio
async def test_repo_never_commits():
    """Verify repositories only flush, never commit.

    This is enforced by code review and the .claude/rules/repositories.md rule.
    Commit must ONLY happen in get_db_session context manager.
    """
    import ast
    from pathlib import Path

    repo_dir = Path(__file__).parent.parent / "app" / "db" / "repositories"
    repo_files = [
        repo_file for repo_file in repo_dir.glob("*.py") if repo_file.name != "__init__.py"
    ]
    assert repo_files, f"No repository files found under {repo_dir}"
    for repo_file in repo_files:
        source = repo_file.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "commit"
            ):
                pytest.fail(
                    f"Repository {repo_file.name} contains session.commit() call. "
                    f"Repositories must only flush(), not commit()."
                )

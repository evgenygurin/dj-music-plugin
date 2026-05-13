"""TransitionPersistHandler tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastmcp.server.context import Context
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.handlers.transition_persist import transition_persist_handler
from app.models.base import Base
from app.models.track import Track
from app.repositories.transition import TransitionRepository
from app.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    return MagicMock(spec=Context)


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock()}
    )
    # Restrict to the actual repository surface so the test catches calls to
    # methods that don't exist on the real ``TransitionRepository``.
    u.transitions = MagicMock(spec=["upsert", "get_pair", "create", "update"])
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=10))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.82
    score.bpm = 0.9
    score.harmonics = 0.8
    score.energy = 0.75
    score.bass = 0.85
    score.drums = 0.78
    score.vocals = 0.82
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_scores_and_persists_pair(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)

    assert result["from_track_id"] == 1
    assert result["to_track_id"] == 2
    assert result["overall"] == pytest.approx(0.82)
    uow.transitions.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_scoring_profile_rejected(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """Regression: ``TransitionCreate.scoring_profile`` was advertised on
    the schema but never read by the handler, so a typo (or any
    non-existent profile) silently fell through to the default weights.
    Now the handler verifies the profile exists and raises a clear
    ``ValidationError`` before any scoring work.
    """
    from app.shared.errors import ValidationError

    uow.scoring_profiles = MagicMock()
    uow.scoring_profiles.get_by_name = AsyncMock(return_value=None)
    data = {"from_track_id": 1, "to_track_id": 2, "scoring_profile": "bogus"}
    with pytest.raises(ValidationError, match=r"scoring_profile 'bogus' not found"):
        await transition_persist_handler(ctx, uow, data, scorer)
    uow.scoring_profiles.get_by_name.assert_awaited_once_with("bogus")
    # No score / persist should have happened.
    scorer.score.assert_not_called()
    uow.transitions.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_known_scoring_profile_passes_validation(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """When the profile exists, validation clears and the handler proceeds
    to its normal score+persist path."""
    uow.scoring_profiles = MagicMock()
    uow.scoring_profiles.get_by_name = AsyncMock(return_value=MagicMock(name="manual_test"))
    data = {"from_track_id": 1, "to_track_id": 2, "scoring_profile": "manual_test"}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    assert result["overall"] == pytest.approx(0.82)


@pytest.mark.asyncio
async def test_missing_features_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.track_features.get_scoring_features_batch.return_value = {1: MagicMock()}
    data = {"from_track_id": 1, "to_track_id": 2}
    with pytest.raises(NotFoundError):
        await transition_persist_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_hard_reject_is_persisted_with_zero_overall(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    rejected = MagicMock()
    rejected.overall = 0.0
    rejected.hard_reject = True
    rejected.reject_reason = "bpm_diff>10"
    rejected.bpm = rejected.harmonic = rejected.energy = 0.0
    rejected.spectral = rejected.groove = rejected.timbral = 0.0
    scorer.score.return_value = rejected

    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    assert result["hard_reject"] is True
    assert result["overall"] == 0.0
    uow.transitions.upsert.assert_awaited_once()


# ── Real-DB regression for BUG: TransitionRepository.upsert must exist. ──


@pytest_asyncio.fixture
async def real_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def real_session(real_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    async with factory() as s:
        # Seed two real tracks so transition FKs validate.
        s.add(Track(id=1, title="A", sort_title="a", duration_ms=180_000))
        s.add(Track(id=2, title="B", sort_title="b", duration_ms=180_000))
        await s.flush()
        try:
            yield s
        finally:
            await s.rollback()


# ── Phase 1 Task D: section_context wiring through schema → handler → scorer. ──


@pytest.mark.asyncio
async def test_section_context_outro_intro_resolved_to_drum_only(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """``TransitionCreate.section_context={from=OUTRO,to=INTRO}`` must be
    parsed into a ``SectionContext`` and passed to ``scorer.score`` as
    a kwarg. The handler also surfaces ``score.section_pair_class`` in
    the response dict so callers see which overlay applied.
    """
    from app.domain.transition.section_context import SectionContext, SectionPairClass
    from app.shared.constants import SectionType

    # Make the mock scorer echo whatever section_context the handler
    # passed it — so we can both assert the handler resolved the DTO
    # correctly AND let the response surface ``section_pair_class``.
    def _score(a, b, *, section_context=None, intent=None):
        score = MagicMock()
        score.overall = 0.82
        score.bpm = 0.9
        score.harmonics = 0.8
        score.energy = 0.75
        score.bass = 0.85
        score.drums = 0.78
        score.vocals = 0.82
        score.hard_reject = False
        score.reject_reason = None
        score.section_pair_class = (
            section_context.section_pair_class.value if section_context is not None else None
        )
        return score

    scorer.score.side_effect = _score

    data = {
        "from_track_id": 1,
        "to_track_id": 2,
        "section_context": {"from_section": "OUTRO", "to_section": "INTRO"},
    }
    result = await transition_persist_handler(ctx, uow, data, scorer)

    # Verify the scorer was called with a real SectionContext, not a dict
    call = scorer.score.call_args
    section_context = call.kwargs["section_context"]
    assert isinstance(section_context, SectionContext)
    assert section_context.from_section == SectionType.OUTRO
    assert section_context.to_section == SectionType.INTRO
    assert section_context.section_pair_class == SectionPairClass.DRUM_ONLY

    # Verify the response surfaces section_pair_class
    assert result["section_pair_class"] == "drum_only"


@pytest.mark.asyncio
async def test_section_context_accepts_integer_section_values(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """Integer SectionType values (7=OUTRO, 0=INTRO) are also accepted."""
    from app.domain.transition.section_context import SectionContext
    from app.shared.constants import SectionType

    captured: dict[str, object] = {}

    def _score(a, b, *, section_context=None, intent=None):
        captured["section_context"] = section_context
        score = MagicMock()
        score.overall = 0.82
        score.bpm = 0.9
        score.harmonics = 0.8
        score.energy = 0.75
        score.bass = 0.85
        score.drums = 0.78
        score.vocals = 0.82
        score.hard_reject = False
        score.reject_reason = None
        score.section_pair_class = (
            section_context.section_pair_class.value if section_context is not None else None
        )
        return score

    scorer.score.side_effect = _score

    data = {
        "from_track_id": 1,
        "to_track_id": 2,
        "section_context": {"from_section": 7, "to_section": 0},  # OUTRO → INTRO
    }
    result = await transition_persist_handler(ctx, uow, data, scorer)

    section_context = captured["section_context"]
    assert isinstance(section_context, SectionContext)
    assert section_context.from_section == SectionType.OUTRO
    assert section_context.to_section == SectionType.INTRO
    assert result["section_pair_class"] == "drum_only"


@pytest.mark.asyncio
async def test_section_context_omitted_yields_none(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """Omitting ``section_context`` → handler passes ``None`` to the
    scorer and the response surfaces ``section_pair_class=None``.
    Backwards-compat path for the common case where the caller has
    no section data.
    """

    def _score(a, b, *, section_context=None, intent=None):
        score = MagicMock()
        score.overall = 0.82
        score.bpm = 0.9
        score.harmonics = 0.8
        score.energy = 0.75
        score.bass = 0.85
        score.drums = 0.78
        score.vocals = 0.82
        score.hard_reject = False
        score.reject_reason = None
        score.section_pair_class = None
        return score

    scorer.score.side_effect = _score

    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)

    # Scorer received section_context=None
    call = scorer.score.call_args
    assert call.kwargs["section_context"] is None
    assert result["section_pair_class"] is None


@pytest.mark.asyncio
async def test_section_context_unknown_string_falls_back_to_none(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """An unknown section alias on both sides → ``_resolve_section_context``
    returns ``None`` (no SectionContext built) and the scorer sees
    ``section_context=None``. Defensive against typos in caller payloads.
    """

    def _score(a, b, *, section_context=None, intent=None):
        score = MagicMock()
        score.overall = 0.82
        score.bpm = 0.9
        score.harmonics = 0.8
        score.energy = 0.75
        score.bass = 0.85
        score.drums = 0.78
        score.vocals = 0.82
        score.hard_reject = False
        score.reject_reason = None
        score.section_pair_class = None
        return score

    scorer.score.side_effect = _score

    data = {
        "from_track_id": 1,
        "to_track_id": 2,
        "section_context": {"from_section": "BOGUS", "to_section": "ALSO_BOGUS"},
    }
    result = await transition_persist_handler(ctx, uow, data, scorer)

    call = scorer.score.call_args
    assert call.kwargs["section_context"] is None
    assert result["section_pair_class"] is None


# ── Real-DB regression for BUG: TransitionRepository.upsert must exist. ──


@pytest.mark.asyncio
async def test_transition_repository_upsert_creates_then_updates(
    real_session: AsyncSession,
) -> None:
    """Regression: ``TransitionRepository.upsert`` must exist and behave as
    upsert — first call creates, second call with the same (from, to) pair
    updates in place rather than raising AttributeError.
    """
    repo = TransitionRepository(real_session)

    row1 = await repo.upsert(
        from_track_id=1,
        to_track_id=2,
        bpm_score=0.9,
        harmonics_score=0.8,
        energy_score=0.7,
        bass_score=0.85,
        drums_score=0.75,
        vocals_score=0.8,
        overall_quality=0.8,
        hard_reject=False,
        reject_reason=None,
    )
    assert row1.id is not None

    row2 = await repo.upsert(
        from_track_id=1,
        to_track_id=2,
        bpm_score=0.5,
        harmonics_score=0.5,
        energy_score=0.5,
        bass_score=0.5,
        drums_score=0.5,
        vocals_score=0.5,
        overall_quality=0.5,
        hard_reject=False,
        reject_reason=None,
    )
    # Same row should be reused (upsert, not insert).
    assert row2.id == row1.id
    assert row2.overall_quality == pytest.approx(0.5)

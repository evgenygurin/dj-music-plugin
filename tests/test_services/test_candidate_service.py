"""Tests for CandidateService — transition candidate pruning."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.repositories.candidate import CandidateRepository
from app.services.candidate_service import CandidateService

# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
async def svc(db: AsyncSession) -> CandidateService:
    return CandidateService(CandidateRepository(db))


async def _create_track(db: AsyncSession, track_id: int, title: str) -> Track:
    """Create a track with given id."""
    track = Track(id=track_id, title=title, status=0)
    db.add(track)
    await db.flush()
    return track


async def _create_features(
    db: AsyncSession,
    track_id: int,
    *,
    bpm: float = 128.0,
    key_code: int = 14,
    integrated_lufs: float = -8.0,
) -> TrackAudioFeaturesComputed:
    """Create audio features for a track."""
    feat = TrackAudioFeaturesComputed(
        track_id=track_id,
        bpm=bpm,
        key_code=key_code,
        integrated_lufs=integrated_lufs,
        energy_mean=0.6,
    )
    db.add(feat)
    await db.flush()
    return feat


async def _seed_compatible_tracks(db: AsyncSession) -> list[int]:
    """Create 3 tracks that are compatible (similar BPM, key, energy).

    Track 1: 128 BPM, key 14 (8A), -8 LUFS
    Track 2: 130 BPM, key 14 (8A), -9 LUFS
    Track 3: 126 BPM, key 12 (7A), -7 LUFS  (adjacent key, dist=1)
    """
    ids = [1, 2, 3]
    await _create_track(db, 1, "Compatible Track A")
    await _create_track(db, 2, "Compatible Track B")
    await _create_track(db, 3, "Compatible Track C")

    await _create_features(db, 1, bpm=128.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 2, bpm=130.0, key_code=14, integrated_lufs=-9.0)
    await _create_features(db, 3, bpm=126.0, key_code=12, integrated_lufs=-7.0)
    return ids


async def _seed_incompatible_tracks(db: AsyncSession) -> list[int]:
    """Create tracks that are NOT compatible.

    Track 10: 128 BPM, key 14 (8A), -8 LUFS  — reference
    Track 11: 155 BPM, key 14 (8A), -8 LUFS  — BPM too far (27 > 10)
    Track 12: 128 BPM, key  0 (1A), -8 LUFS  — key too far (dist=7)
    Track 13: 128 BPM, key 14 (8A), -1 LUFS  — energy too far (7 > 6)
    """
    ids = [10, 11, 12, 13]
    for i, title in zip(ids, ["Ref", "Far BPM", "Far Key", "Far Energy"], strict=True):
        await _create_track(db, i, f"Incompat {title}")

    await _create_features(db, 10, bpm=128.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 11, bpm=155.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 12, bpm=128.0, key_code=0, integrated_lufs=-8.0)
    await _create_features(db, 13, bpm=128.0, key_code=14, integrated_lufs=-1.0)
    return ids


# ── Test: generate_candidates ───────────────────────────


@pytest.mark.asyncio
async def test_generate_candidates_compatible(db: AsyncSession, svc: CandidateService) -> None:
    """Compatible tracks should produce candidate pairs."""
    ids = await _seed_compatible_tracks(db)

    stats = await svc.generate_candidates(ids)

    assert stats.total_tracks == 3
    assert stats.total_pairs_checked == 3  # C(3,2) = 3
    # 3 compatible pairs x 2 directions = 6 candidates
    assert stats.candidates_created == 6
    assert stats.skipped_missing_features == 0


@pytest.mark.asyncio
async def test_generate_candidates_incompatible(db: AsyncSession, svc: CandidateService) -> None:
    """Incompatible tracks should not produce candidates (except ref↔ref which is itself)."""
    ids = await _seed_incompatible_tracks(db)

    stats = await svc.generate_candidates(ids)

    assert stats.total_tracks == 4
    assert stats.total_pairs_checked == 6  # C(4,2) = 6
    # Track 10 is not compatible with any of 11,12,13 — 0 candidates
    assert stats.candidates_created == 0


@pytest.mark.asyncio
async def test_generate_candidates_all_tracks(db: AsyncSession, svc: CandidateService) -> None:
    """Generate candidates for all tracks when track_ids=None."""
    await _seed_compatible_tracks(db)

    stats = await svc.generate_candidates(track_ids=None)

    assert stats.total_tracks == 3
    assert stats.candidates_created == 6


@pytest.mark.asyncio
async def test_generate_candidates_missing_features(
    db: AsyncSession, svc: CandidateService
) -> None:
    """Tracks without features should be skipped."""
    await _create_track(db, 100, "No Features Track")
    await _create_track(db, 101, "Has Features")
    await _create_features(db, 101, bpm=128.0)

    stats = await svc.generate_candidates([100, 101])

    assert stats.skipped_missing_features == 1
    assert stats.total_tracks == 1
    assert stats.candidates_created == 0  # only 1 track, need at least 2


@pytest.mark.asyncio
async def test_generate_candidates_single_track(db: AsyncSession, svc: CandidateService) -> None:
    """Single track should produce no candidates."""
    await _create_track(db, 200, "Single")
    await _create_features(db, 200, bpm=128.0)

    stats = await svc.generate_candidates([200])

    assert stats.total_tracks == 1
    assert stats.candidates_created == 0


@pytest.mark.asyncio
async def test_regenerate_deletes_old_candidates(db: AsyncSession, svc: CandidateService) -> None:
    """Running generate_candidates twice should replace old candidates."""
    ids = await _seed_compatible_tracks(db)

    stats1 = await svc.generate_candidates(ids)
    assert stats1.candidates_created == 6

    stats2 = await svc.generate_candidates(ids)
    assert stats2.candidates_created == 6

    # Total in DB should be 6, not 12
    count = await svc.count_candidates()
    assert count == 6


# ── Test: get_candidates_for_track ──────────────────────


@pytest.mark.asyncio
async def test_get_candidates_for_track(db: AsyncSession, svc: CandidateService) -> None:
    """Should return candidates for a specific track."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    candidates = await svc.get_candidates_for_track(1)

    assert len(candidates) == 2  # tracks 2 and 3
    assert all(c.from_track_id == 1 for c in candidates)
    to_ids = {c.to_track_id for c in candidates}
    assert to_ids == {2, 3}


@pytest.mark.asyncio
async def test_get_candidates_for_track_ordered(db: AsyncSession, svc: CandidateService) -> None:
    """Candidates should be ordered by BPM distance."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    candidates = await svc.get_candidates_for_track(1)

    # All candidates should have non-None bpm_distance
    distances = [c.bpm_distance for c in candidates]
    assert all(d is not None for d in distances)
    # Should be sorted ascending
    assert distances == sorted(distances)  # type: ignore[type-var]


@pytest.mark.asyncio
async def test_get_candidates_for_track_with_limit(
    db: AsyncSession, svc: CandidateService
) -> None:
    """Limit should restrict results."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    candidates = await svc.get_candidates_for_track(1, limit=1)

    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_get_candidates_for_track_empty(db: AsyncSession, svc: CandidateService) -> None:
    """Track with no candidates should return empty list."""
    candidates = await svc.get_candidates_for_track(9999)
    assert candidates == []


# ── Test: get_candidate_pair ────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_pair_exists(db: AsyncSession, svc: CandidateService) -> None:
    """Should return the candidate pair if it exists."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    pair = await svc.get_candidate_pair(1, 2)

    assert pair is not None
    assert pair.from_track_id == 1
    assert pair.to_track_id == 2
    assert pair.bpm_distance is not None
    assert pair.key_distance is not None
    assert pair.energy_delta is not None


@pytest.mark.asyncio
async def test_get_candidate_pair_not_exists(db: AsyncSession, svc: CandidateService) -> None:
    """Should return None for non-existing pair."""
    pair = await svc.get_candidate_pair(1, 9999)
    assert pair is None


# ── Test: count_candidates ──────────────────────────────


@pytest.mark.asyncio
async def test_count_candidates_total(db: AsyncSession, svc: CandidateService) -> None:
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    count = await svc.count_candidates()
    assert count == 6


@pytest.mark.asyncio
async def test_count_candidates_per_track(db: AsyncSession, svc: CandidateService) -> None:
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    count = await svc.count_candidates(track_id=1)
    assert count == 2


# ── Test: candidate distances are correct ───────────────


@pytest.mark.asyncio
async def test_candidate_bpm_distance(db: AsyncSession, svc: CandidateService) -> None:
    """BPM distance should be computed correctly."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    pair = await svc.get_candidate_pair(1, 2)
    assert pair is not None
    # Track 1: 128 BPM, Track 2: 130 BPM → distance = 2.0
    assert pair.bpm_distance == pytest.approx(2.0, abs=0.1)


@pytest.mark.asyncio
async def test_candidate_key_distance(db: AsyncSession, svc: CandidateService) -> None:
    """Key distance should use Camelot wheel."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    # Track 1 (8A, code=14) → Track 3 (7A, code=12): distance = 1
    pair = await svc.get_candidate_pair(1, 3)
    assert pair is not None
    assert pair.key_distance == 1


@pytest.mark.asyncio
async def test_candidate_energy_delta(db: AsyncSession, svc: CandidateService) -> None:
    """Energy delta should be absolute LUFS difference."""
    ids = await _seed_compatible_tracks(db)
    await svc.generate_candidates(ids)

    # Track 1: -8 LUFS, Track 2: -9 LUFS → delta = 1.0
    pair = await svc.get_candidate_pair(1, 2)
    assert pair is not None
    assert pair.energy_delta == pytest.approx(1.0, abs=0.1)


# ── Test: key distance filter ──────────────────────────


@pytest.mark.asyncio
async def test_key_distance_filter_excludes_far_keys(
    db: AsyncSession, svc: CandidateService
) -> None:
    """Keys with Camelot distance > 2 should be excluded from candidates."""
    await _create_track(db, 50, "Key Near")
    await _create_track(db, 51, "Key Far")

    # key_code=14 (8A) and key_code=8 (5A): distance = 3
    await _create_features(db, 50, bpm=128.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 51, bpm=128.0, key_code=8, integrated_lufs=-8.0)

    stats = await svc.generate_candidates([50, 51])
    assert stats.candidates_created == 0  # distance 3 > max 2


@pytest.mark.asyncio
async def test_key_distance_filter_includes_close_keys(
    db: AsyncSession, svc: CandidateService
) -> None:
    """Keys with Camelot distance ≤ 2 should be included."""
    await _create_track(db, 60, "Key A")
    await _create_track(db, 61, "Key B")

    # key_code=14 (8A) and key_code=10 (6A): distance = 2
    await _create_features(db, 60, bpm=128.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 61, bpm=128.0, key_code=10, integrated_lufs=-8.0)

    stats = await svc.generate_candidates([60, 61])
    assert stats.candidates_created == 2  # both directions


# ── Test: BPM double-time awareness ────────────────────


@pytest.mark.asyncio
async def test_bpm_double_time_candidates(db: AsyncSession, svc: CandidateService) -> None:
    """BPM 128 and 64 should be compatible (double-time)."""
    await _create_track(db, 70, "Normal")
    await _create_track(db, 71, "Half-time")

    await _create_features(db, 70, bpm=128.0, key_code=14, integrated_lufs=-8.0)
    await _create_features(db, 71, bpm=64.0, key_code=14, integrated_lufs=-8.0)

    stats = await svc.generate_candidates([70, 71])
    # 128/2 = 64, distance = 0 → should be included
    assert stats.candidates_created == 2

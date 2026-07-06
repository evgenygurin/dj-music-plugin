import pytest

from app.models.audio_file import DjLibraryItem
from app.models.base import Base
from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.unit_of_work import UnitOfWork


async def _create_tables(session):
    """The shared ``session`` fixture skips ``create_all`` (each test picks
    its own Base); create all tables on the bound in-memory engine."""
    conn = await session.connection()
    await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_get_render_inputs_orders_and_joins(session):
    await _create_tables(session)
    # seed parents first (FK enforcement is on in the full suite — flush the
    # Track + DjSet parents before their FK children so insert order is valid).
    session.add(Track(id=5435, title="Edit Select - Vault 2015"))
    session.add(DjSet(id=1, name="S"))
    session.add(DjSetVersion(id=131, set_id=1, label="v131"))
    await session.flush()
    session.add(
        TrackAudioFeaturesComputed(track_id=5435, bpm=130.0, key_code=13, integrated_lufs=-12.33)
    )
    session.add(
        DjLibraryItem(
            track_id=5435, file_path="/tmp/dj_audio/01 [49353955].mp3", file_hash="h", file_size=1
        )
    )
    session.add(DjSetItem(version_id=131, track_id=5435, sort_index=0, mix_in_point_ms=0))
    await session.flush()

    uow = UnitOfWork(session)
    rows = await uow.set_versions.get_render_inputs(131)
    assert len(rows) == 1
    r = rows[0]
    assert r.track_id == 5435
    assert r.title == "Edit Select - Vault 2015"
    assert r.bpm == 130.0
    assert r.key_code == 13
    assert r.mix_in_ms == 0
    assert r.integrated_lufs == -12.33
    assert r.file_path.endswith("[49353955].mp3")


@pytest.mark.asyncio
async def test_get_render_inputs_missing_audio_raises(session):
    await _create_tables(session)
    session.add(Track(id=9, title="No File"))
    session.add(
        TrackAudioFeaturesComputed(track_id=9, bpm=130.0, key_code=1, integrated_lufs=-11.0)
    )
    session.add(DjSet(id=2, name="S2"))
    session.add(DjSetVersion(id=200, set_id=2, label="v"))
    session.add(DjSetItem(version_id=200, track_id=9, sort_index=0, mix_in_point_ms=0))
    await session.flush()
    uow = UnitOfWork(session)
    with pytest.raises(Exception) as exc:  # ValidationError from app.shared.errors
        await uow.set_versions.get_render_inputs(200)
    assert "audio_file" in str(exc.value)

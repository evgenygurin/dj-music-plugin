from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.stem_features import StemFeatures
from app.repositories.stem_features import StemFeaturesRepository


_STEM_FEATURES_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS stem_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        stem_name VARCHAR(16) NOT NULL,
        pipeline_run_id INTEGER,
        analysis_level INTEGER DEFAULT 6 NOT NULL,
        bpm REAL,
        bpm_confidence REAL,
        bpm_stability REAL,
        variable_tempo INTEGER,
        integrated_lufs REAL,
        short_term_lufs_mean REAL,
        momentary_max REAL,
        rms_dbfs REAL,
        true_peak_db REAL,
        crest_factor_db REAL,
        loudness_range_lu REAL,
        energy_mean REAL,
        energy_max REAL,
        energy_std REAL,
        energy_slope REAL,
        energy_sub REAL,
        energy_low REAL,
        energy_lowmid REAL,
        energy_mid REAL,
        energy_highmid REAL,
        energy_high REAL,
        energy_sub_ratio REAL,
        energy_low_ratio REAL,
        energy_lowmid_ratio REAL,
        energy_mid_ratio REAL,
        energy_highmid_ratio REAL,
        energy_high_ratio REAL,
        spectral_centroid_hz REAL,
        spectral_rolloff_85 REAL,
        spectral_rolloff_95 REAL,
        spectral_flatness REAL,
        spectral_flux_mean REAL,
        spectral_flux_std REAL,
        spectral_slope REAL,
        spectral_contrast REAL,
        key_code INTEGER,
        key_confidence REAL,
        atonality INTEGER,
        hnr_db REAL,
        chroma_entropy REAL,
        mfcc_vector VARCHAR(500),
        hp_ratio REAL,
        onset_rate REAL,
        pulse_clarity REAL,
        kick_prominence REAL,
        danceability REAL,
        dynamic_complexity REAL,
        dissonance_mean REAL,
        tonnetz_vector VARCHAR(500),
        tempogram_ratio_vector VARCHAR(500),
        beat_loudness_band_ratio VARCHAR(500),
        spectral_complexity_mean REAL,
        pitch_salience_mean REAL,
        bpm_histogram_first_peak_weight REAL,
        bpm_histogram_second_peak_bpm REAL,
        bpm_histogram_second_peak_weight REAL,
        phrase_boundaries_ms VARCHAR(2000),
        dominant_phrase_bars SMALLINT,
        first_downbeat_ms REAL,
        chords_strength REAL,
        chords_changes_rate REAL,
        hpcp_entropy REAL,
        hpcp_crest REAL,
        inharmonicity REAL,
        meter VARCHAR(16),
        click_detected INTEGER,
        saturation_detected INTEGER,
        drum_bands TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        UNIQUE(track_id, stem_name)
    )
    """
)


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> StemFeaturesRepository:
    async with engine.begin() as conn:
        await conn.execute(_STEM_FEATURES_DDL)
    return StemFeaturesRepository(session)


@pytest.mark.asyncio
async def test_get_by_id(repo: StemFeaturesRepository, session: AsyncSession):
    row = StemFeatures(track_id=1, stem_name="drums", bpm=135.0)
    session.add(row)
    await session.flush()

    fetched = await repo.get(row.id)
    assert fetched is not None
    assert fetched.stem_name == "drums"


@pytest.mark.asyncio
async def test_get_missing_returns_none(repo: StemFeaturesRepository):
    assert await repo.get(99999) is None


@pytest.mark.asyncio
async def test_filter(repo: StemFeaturesRepository, session: AsyncSession):
    r1 = StemFeatures(track_id=1, stem_name="drums")
    r2 = StemFeatures(track_id=1, stem_name="bass")
    r3 = StemFeatures(track_id=2, stem_name="drums")
    session.add_all([r1, r2, r3])
    await session.flush()

    result = await repo.filter(where={"stem_name__eq": "drums"})
    rows = result.items
    assert len(rows) >= 2
    for r in rows:
        assert r.stem_name == "drums"


@pytest.mark.asyncio
async def test_upsert_insert(repo: StemFeaturesRepository):
    row = await repo.upsert(1, "bass", {"bpm": 128.0})
    assert row.id is not None
    assert row.stem_name == "bass"
    assert row.bpm == 128.0
    assert row.track_id == 1


@pytest.mark.asyncio
async def test_upsert_update(repo: StemFeaturesRepository):
    row = await repo.upsert(1, "bass", {"bpm": 128.0})
    updated = await repo.upsert(1, "bass", {"bpm": 130.0})
    assert updated.id == row.id
    assert updated.bpm == 130.0


@pytest.mark.asyncio
async def test_get_all_for_track(repo: StemFeaturesRepository, session: AsyncSession):
    r1 = StemFeatures(track_id=1, stem_name="drums")
    r2 = StemFeatures(track_id=1, stem_name="bass")
    r3 = StemFeatures(track_id=2, stem_name="drums")
    session.add_all([r1, r2, r3])
    await session.flush()

    rows = await repo.get_all_for_track(1)
    assert len(rows) == 2
    names = {r.stem_name for r in rows}
    assert names == {"drums", "bass"}

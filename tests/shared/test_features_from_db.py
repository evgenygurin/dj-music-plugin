"""Audit iter 36 (T-34): ``TrackFeatures.from_db`` dropped two fields
that ``track_audio_features_computed`` rows actually have.

Symptom: ``local://tracks/{id}/features`` returned
``analysis_level: null`` and ``mood_confidence: null`` for every track
— even fully L3-analyzed ones — because ``_track_features_payload``
uses ``getattr(feat, ...)`` on the dataclass and the dataclass simply
didn't declare those fields. Result: callers couldn't tell which P3
fields are populated, and mood confidence was permanently invisible
on the resource.

Fix: declare ``analysis_level: int | None`` and
``mood_confidence: float | None`` on ``TrackFeatures`` and populate
them in ``from_db``.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.shared.features import TrackFeatures


def test_from_db_populates_analysis_level_and_mood_confidence() -> None:
    """Both fields land on the dataclass when the source row has them."""
    row = SimpleNamespace(
        bpm=124.0,
        key_code=8,
        integrated_lufs=-9.0,
        spectral_centroid_hz=2000.0,
        spectral_flatness=0.1,
        energy_mean=0.5,
        onset_rate=2.0,
        kick_prominence=0.3,
        hnr_db=10.0,
        chroma_entropy=0.5,
        mfcc_vector=None,
        analysis_level=3,
        mood="hypnotic",
        mood_confidence=0.8,
    )
    feat = TrackFeatures.from_db(row)
    assert feat.analysis_level == 3
    assert feat.mood_confidence == 0.8
    assert feat.mood == "hypnotic"


def test_from_db_handles_missing_fields_gracefully() -> None:
    """Older rows / minimal stubs still parse — both fields fall to None."""
    row = SimpleNamespace(
        bpm=120.0,
        key_code=None,
        integrated_lufs=None,
        spectral_centroid_hz=None,
        spectral_flatness=None,
        energy_mean=None,
        onset_rate=None,
        kick_prominence=None,
        hnr_db=None,
        chroma_entropy=None,
        mfcc_vector=None,
    )
    feat = TrackFeatures.from_db(row)
    assert feat.analysis_level is None
    assert feat.mood_confidence is None
    assert feat.mood is None

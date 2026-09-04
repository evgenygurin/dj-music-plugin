from app.application.analysis.persistence import snapshot_from_record, snapshot_to_payload
from app.domain.analysis import AnalysisSnapshot, BeatGrid, BeatPosition, TempoHypothesis


def test_snapshot_round_trip_preserves_beatgrid_and_identity() -> None:
    snapshot = AnalysisSnapshot(
        source_hash="source",
        schema_version="1",
        analyzer_versions=(("beat", "2"),),
        engine_version="universal-1",
        model_versions=(("tempo", "3"),),
        dsp_backend="librosa",
        analysis_config_hash="config",
        tempo_hypotheses=(TempoHypothesis(128, 0.9, "audio"),),
        beatgrid=BeatGrid(
            bpm=128,
            beats=(
                BeatPosition(0.0, 0, True),
                BeatPosition(60.0 / 128, 1),
            ),
            phase_s=0.0,
        ),
    )

    payload = snapshot_to_payload(snapshot)
    restored = snapshot_from_record(
        {
            "source_hash": snapshot.source_hash,
            "schema_version": snapshot.schema_version,
            "analyzer_versions": dict(snapshot.analyzer_versions),
            "model_versions": dict(snapshot.model_versions),
            "payload": payload,
        }
    )

    assert restored == snapshot
    assert restored.identity_hash == snapshot.identity_hash


def test_snapshot_from_record_preserves_record_identity_inputs() -> None:
    snapshot = AnalysisSnapshot("source", "1", tempo_hypotheses=(TempoHypothesis(128, 1.0),))
    record = {
        "source_hash": snapshot.source_hash,
        "schema_version": "2",
        "analyzer_versions": {},
        "model_versions": {},
        "payload": snapshot_to_payload(snapshot),
    }

    restored = snapshot_from_record(record)
    assert restored.identity_hash != snapshot.identity_hash

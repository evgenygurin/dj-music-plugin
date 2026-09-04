from dataclasses import FrozenInstanceError

import pytest

from app.domain.analysis.snapshot import AnalysisSnapshot


def test_snapshot_hash_is_deterministic_for_same_identity_inputs() -> None:
    kwargs = dict(source_hash="abc", schema_version="1", analyzer_versions={"tempo": "2"})
    left = AnalysisSnapshot(**kwargs)
    right = AnalysisSnapshot(**kwargs)
    assert left.identity_hash == right.identity_hash


def test_snapshot_hash_changes_when_analysis_identity_changes() -> None:
    base = AnalysisSnapshot(source_hash="abc", schema_version="1")
    changed = AnalysisSnapshot(source_hash="abc", schema_version="2")
    assert base.identity_hash != changed.identity_hash


def test_snapshot_is_immutable_and_rejects_empty_source_hash() -> None:
    snapshot = AnalysisSnapshot(source_hash="abc", schema_version="1")
    with pytest.raises(FrozenInstanceError):
        snapshot.source_hash = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="source_hash"):
        AnalysisSnapshot(source_hash="", schema_version="1")

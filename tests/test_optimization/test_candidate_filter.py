from app.entities.audio.features import TrackFeatures
from app.optimization.candidate_filter import build_adjacency


def _feat(bpm: float | None, key_code: int | None, lufs: float | None) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)


def test_bpm_hard_reject():
    features = {1: _feat(120.0, 0, -10.0), 2: _feat(135.0, 0, -10.0)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]
    assert 1 not in graph[2]


def test_camelot_hard_reject():
    # key_code=0 (1A), key_code=10 (6A) — distance=5 >= threshold
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(130.0, 10, -10.0)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]


def test_lufs_hard_reject():
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(130.0, 0, -17.5)}
    graph = build_adjacency(features)
    assert 2 not in graph[1]


def test_valid_pair_passes():
    features = {1: _feat(130.0, 0, -10.0), 2: _feat(132.0, 1, -11.0)}
    graph = build_adjacency(features)
    assert 2 in graph[1]
    assert 1 in graph[2]


def test_none_features_fallback():
    features = {1: _feat(None, None, None), 2: _feat(130.0, 0, -10.0)}
    graph = build_adjacency(features)
    assert 2 in graph[1]
    assert 1 in graph[2]


def test_self_not_in_adjacency():
    features = {1: _feat(130.0, 0, -10.0)}
    graph = build_adjacency(features)
    assert 1 not in graph[1]


def test_returns_all_ids_as_keys():
    features = {1: _feat(120.0, 0, -10.0), 2: _feat(140.0, 10, -20.0)}
    graph = build_adjacency(features)
    assert 1 in graph
    assert 2 in graph

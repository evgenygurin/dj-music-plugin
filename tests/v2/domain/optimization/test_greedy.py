"""GreedyChainBuilder regression."""

from __future__ import annotations

from app.v2.domain.optimization import GreedyChainBuilder
from app.v2.domain.transition.features import TrackFeatures
from app.v2.domain.transition.scorer import TransitionScorer


def _feats(bpms: tuple[float, ...]) -> list[TrackFeatures]:
    return [
        TrackFeatures(
            bpm=b,
            key_code=5,
            integrated_lufs=-8.0,
            energy_mean=0.3,
            spectral_centroid_hz=3000.0,
            onset_rate=5.0,
            kick_prominence=0.5,
            hnr_db=10.0,
            chroma_entropy=0.6,
        )
        for b in bpms
    ]


def test_greedy_returns_permutation() -> None:
    feats = _feats((124.0, 126.0, 128.0))
    ids = [1, 2, 3]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids)
    assert sorted(res.track_order) == sorted(ids)


def test_greedy_respects_pinned() -> None:
    feats = _feats((124.0, 126.0, 128.0, 130.0))
    ids = [1, 2, 3, 4]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids, pinned={4})
    assert 4 in res.track_order


def test_greedy_excludes_tracks() -> None:
    feats = _feats((124.0, 126.0, 128.0))
    ids = [1, 2, 3]
    res = GreedyChainBuilder(scorer=TransitionScorer()).optimize(feats, ids, excluded={2})
    assert 2 not in res.track_order

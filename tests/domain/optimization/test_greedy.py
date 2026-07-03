"""GreedyChainBuilder regression."""

from __future__ import annotations

from app.domain.optimization import GreedyChainBuilder
from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionPairClass
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures


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


def test_greedy_scores_candidates_with_pair_context() -> None:
    from unittest.mock import MagicMock

    scorer = MagicMock()
    scorer.score.return_value = MagicMock(overall=0.8, hard_reject=False)
    feats = [
        TrackFeatures(
            bpm=126.0,
            integrated_lufs=-12.0,
            mix_out_section_type=int(SectionType.OUTRO),
        ),
        TrackFeatures(
            bpm=128.0,
            integrated_lufs=-10.5,
            mix_in_section_type=int(SectionType.INTRO),
        ),
    ]

    GreedyChainBuilder(scorer=scorer).optimize(feats, [1, 2])

    assert scorer.score.call_count >= 1
    for call in scorer.score.call_args_list:
        assert call.kwargs["intent"] is not None
        assert call.kwargs["section_context"].section_pair_class == SectionPairClass.DRUM_ONLY


def test_greedy_reports_progress() -> None:
    scorer = TransitionScorer()
    feats = [
        TrackFeatures(bpm=126.0, integrated_lufs=-12.0),
        TrackFeatures(bpm=127.0, integrated_lufs=-11.5),
        TrackFeatures(bpm=128.0, integrated_lufs=-11.0),
    ]
    events: list[tuple[int, float]] = []

    GreedyChainBuilder(scorer=scorer).optimize(
        feats,
        [1, 2, 3],
        on_progress=lambda progress, score: events.append((progress, score)),
    )

    assert events
    assert events[-1][0] == 100

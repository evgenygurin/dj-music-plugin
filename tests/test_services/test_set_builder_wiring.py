"""Tests for template/mood wiring in SetBuilderService._optimize_order()."""

from __future__ import annotations

from app.optimization.result import OptimizationResult
from app.services.set.builder import SetBuilderService
from app.services.transition import TrackFeatures


def _feature(*, bpm: float, mood: str | None) -> TrackFeatures:
    return TrackFeatures(
        bpm=bpm,
        key_code=14,
        integrated_lufs=-8.0,
        spectral_centroid_hz=2500.0,
        energy_mean=0.5,
        onset_rate=4.0,
        kick_prominence=0.5,
        mood=mood,
    )


def test_optimize_order_passes_template_and_moods_to_ga(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeGA:
        def __init__(self, scorer) -> None:
            pass

        def optimize(
            self,
            tracks,
            track_ids,
            pinned=None,
            excluded=None,
            template=None,
            moods=None,
            on_progress=None,
        ) -> OptimizationResult:
            captured["template"] = template
            captured["moods"] = moods
            return OptimizationResult(
                track_order=list(track_ids), quality_score=0.77, algorithm="ga"
            )

    monkeypatch.setattr("app.services.optimizer.GeneticAlgorithm", _FakeGA)

    track_ids = [1, 2, 3]
    track_features = [
        _feature(bpm=132.0, mood="driving"),
        _feature(bpm=134.0, mood="peak_time"),
        _feature(bpm=136.0, mood="industrial"),
    ]

    order, quality, algo = SetBuilderService._optimize_order(
        track_ids,
        track_features,
        "ga",
        template_name="peak_hour_60",
    )

    assert order == track_ids
    assert quality == 0.77
    assert algo == "ga"

    template = captured.get("template")
    assert template is not None
    assert template.name == "peak_hour_60"

    moods = captured.get("moods")
    assert isinstance(moods, dict)
    assert moods == {1: "driving", 2: "peak_time", 3: "industrial"}


def test_optimize_order_gracefully_ignores_unknown_template(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeGreedy:
        def __init__(self, scorer) -> None:
            pass

        def optimize(
            self,
            tracks,
            track_ids,
            pinned=None,
            excluded=None,
            template=None,
            moods=None,
            on_progress=None,
        ) -> OptimizationResult:
            captured["template"] = template
            captured["moods"] = moods
            return OptimizationResult(
                track_order=list(reversed(track_ids)),
                quality_score=0.42,
                algorithm="greedy",
            )

    monkeypatch.setattr("app.services.optimizer.GreedyChainBuilder", _FakeGreedy)

    track_ids = [11, 12, 13]
    track_features = [
        _feature(bpm=128.0, mood="minimal"),
        _feature(bpm=129.0, mood=None),
        _feature(bpm=130.0, mood="progressive"),
    ]

    order, quality, algo = SetBuilderService._optimize_order(
        track_ids,
        track_features,
        "greedy",
        template_name="unknown_template",
    )

    assert order == [13, 12, 11]
    assert quality == 0.42
    assert algo == "greedy"
    assert captured.get("template") is None
    assert captured.get("moods") == {11: "minimal", 12: None, 13: "progressive"}

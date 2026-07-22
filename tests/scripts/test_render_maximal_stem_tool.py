from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import render_maximal_stem_tool as script


def _write_track(root: Path, idx: int, bpm: int, genre: str, title: str) -> None:
    for stem in script.STEM_ORDER:
        (root / f"{idx:04d} [{bpm}bpm] [{genre}] {title}-{stem}.m4a").write_bytes(b"stem")


def test_parse_catalog_groups_complete_tracks(tmp_path: Path) -> None:
    _write_track(tmp_path, 1, 132, "hypnotic", "Thoope")
    _write_track(tmp_path, 2, 134, "industrial", "Pressure")
    (tmp_path / "not-a-stem.txt").write_text("ignore")

    tracks = script.parse_catalog(tmp_path)

    assert [track.index for track in tracks] == [1, 2]
    assert tracks[0].title == "Thoope"
    assert tracks[0].bpm == 132.0
    assert tracks[0].genre == "hypnotic"
    assert set(tracks[0].stems) == set(script.STEM_ORDER)
    assert all(isinstance(path, Path) for path in tracks[0].stems.values())


def test_parse_catalog_omits_incomplete_tracks(tmp_path: Path) -> None:
    _write_track(tmp_path, 1, 132, "hypnotic", "Complete")
    (tmp_path / "0002 [132bpm] [hypnotic] Missing-bass.m4a").write_bytes(b"stem")

    tracks = script.parse_catalog(tmp_path)

    assert [track.title for track in tracks] == ["Complete"]


def test_parse_catalog_missing_directory_raises_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="stems directory does not exist"):
        script.parse_catalog(missing)


def test_parse_catalog_no_matching_files_raises_clear_error(tmp_path: Path) -> None:
    (tmp_path / "track.wav").write_bytes(b"audio")

    with pytest.raises(RuntimeError, match="no prepared stem files matched"):
        script.parse_catalog(tmp_path)


def test_scan_features_uses_valid_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_track(tmp_path, 1, 132, "hypnotic", "Cached")
    tracks = script.parse_catalog(tmp_path)
    cache_path = tmp_path / "features-cache.json"
    first_path = tracks[0].stems["drums"]
    stat = first_path.stat()
    cached = {
        script.feature_key(first_path): {
            "track_index": 1,
            "stem": "drums",
            "path": str(first_path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "rms_db": -12.0,
            "low_ratio": 0.2,
            "mid_ratio": 0.5,
            "high_ratio": 0.3,
            "centroid_hz": 1400.0,
            "onset_rate": 3.0,
            "chroma_peak": 4,
        }
    }
    cache_path.write_text(json.dumps(cached), encoding="utf-8")

    calls: list[tuple[int, str]] = []

    def fake_extract(track: script.StemTrack, stem: str) -> script.StemFeature:
        calls.append((track.index, stem))
        return script.StemFeature(
            track_index=track.index,
            stem=stem,
            path=str(track.stems[stem]),
            mtime_ns=track.stems[stem].stat().st_mtime_ns,
            size=track.stems[stem].stat().st_size,
            rms_db=-20.0,
            low_ratio=0.1,
            mid_ratio=0.6,
            high_ratio=0.3,
            centroid_hz=900.0,
            onset_rate=1.0,
            chroma_peak=None,
        )

    monkeypatch.setattr(script, "extract_stem_feature", fake_extract)
    features = script.scan_features(tracks, cache_path)

    assert features[script.feature_key(first_path)].rms_db == -12.0
    assert (1, "drums") not in calls
    assert len(features) == 5


def test_scan_features_skips_failed_track_when_enough_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_track(tmp_path, 1, 132, "hypnotic", "Good")
    _write_track(tmp_path, 2, 132, "hypnotic", "Broken")
    tracks = script.parse_catalog(tmp_path)

    def fake_extract(track: script.StemTrack, stem: str) -> script.StemFeature:
        if track.index == 2 and stem == "drums":
            raise RuntimeError("decode failed")
        path = track.stems[stem]
        return script.StemFeature(
            track_index=track.index,
            stem=stem,
            path=str(path),
            mtime_ns=path.stat().st_mtime_ns,
            size=path.stat().st_size,
            rms_db=-18.0,
            low_ratio=0.2,
            mid_ratio=0.5,
            high_ratio=0.3,
            centroid_hz=1200.0,
            onset_rate=2.0,
            chroma_peak=0,
        )

    monkeypatch.setattr(script, "extract_stem_feature", fake_extract)
    features = script.scan_features(tracks, tmp_path / "features-cache.json")

    assert {feature.track_index for feature in features.values()} == {1}


def _feature(track_index: int, stem: str, *, low: float = 0.2, high: float = 0.3) -> script.StemFeature:
    return script.StemFeature(
        track_index=track_index,
        stem=stem,
        path=f"/tmp/{track_index}-{stem}.m4a",
        mtime_ns=1,
        size=1,
        rms_db=-18.0,
        low_ratio=low,
        mid_ratio=0.5,
        high_ratio=high,
        centroid_hz=1200.0,
        onset_rate=3.0 if stem == "drums" else 1.0,
        chroma_peak=4 if stem in {"harmonic", "instrumental", "acappella"} else None,
    )


def _track(idx: int, bpm: float, genre: str) -> script.StemTrack:
    return script.StemTrack(
        index=idx,
        title=f"Track {idx}",
        bpm=bpm,
        genre=genre,
        stems={stem: Path(f"/tmp/{idx}-{stem}.m4a") for stem in script.STEM_ORDER},
    )


def _features_for(track: script.StemTrack) -> dict[str, script.StemFeature]:
    return {str(track.stems[stem].resolve()): _feature(track.index, stem) for stem in script.STEM_ORDER}


def test_choose_target_bpm_prefers_132_to_134_window() -> None:
    tracks = [_track(1, 128, "hypnotic"), _track(2, 132, "driving"), _track(3, 136, "industrial")]

    assert 132.0 <= script.choose_target_bpm(tracks) <= 134.0


def test_section_scoring_prefers_hypnotic_early_and_peak_late() -> None:
    early = script.SECTION_ARC[0]
    peak = script.SECTION_ARC[-2]
    hypnotic = _track(1, 132, "hypnotic")
    industrial = _track(2, 134, "industrial")
    features = _features_for(hypnotic) | _features_for(industrial)

    assert script.score_track_for_section(hypnotic, features, early, 133.0, 0) > script.score_track_for_section(
        industrial, features, early, 133.0, 0
    )
    assert script.score_track_for_section(industrial, features, peak, 133.0, 0) > script.score_track_for_section(
        hypnotic, features, peak, 133.0, 0
    )


def test_section_scoring_penalizes_reuse_and_extreme_bpm() -> None:
    section = script.SECTION_ARC[1]
    close = _track(1, 132, "driving")
    far = _track(2, 156, "driving")
    features = _features_for(close) | _features_for(far)

    fresh = script.score_track_for_section(close, features, section, 133.0, 0)
    reused = script.score_track_for_section(close, features, section, 133.0, 5)
    stretched = script.score_track_for_section(far, features, section, 133.0, 0)

    assert fresh > reused
    assert fresh > stretched


def _many_tracks(count: int = 48) -> tuple[list[script.StemTrack], dict[str, script.StemFeature]]:
    genres = ["hypnotic", "dub_techno", "progressive", "driving", "industrial", "peak_time", "acid", "detroit"]
    tracks = [_track(i + 1, 128 + (i % 9), genres[i % len(genres)]) for i in range(count)]
    features: dict[str, script.StemFeature] = {}
    for track in tracks:
        features.update(_features_for(track))
    return tracks, features


def test_arrangement_pressure_windows_keep_10_to_12_layers() -> None:
    tracks, features = _many_tracks()
    config = script.PlannerConfig(target_bpm=133.0, duration_bars=64, rotation_bars=4, max_layers=12, seed=7)

    plan = script.plan_arrangement(tracks, features, config)

    pressure_times = [plan.duration_s * 0.45, plan.duration_s * 0.55, plan.duration_s * 0.70]
    for time_s in pressure_times:
        active = script.active_events_at(plan, time_s)
        assert 10 <= len(active) <= 12


def test_arrangement_never_has_two_full_bass_leaders() -> None:
    tracks, features = _many_tracks()
    config = script.PlannerConfig(target_bpm=133.0, duration_bars=64, rotation_bars=4, max_layers=12, seed=7)

    plan = script.plan_arrangement(tracks, features, config)

    for step in range(0, int(plan.duration_s), 4):
        active = script.active_events_at(plan, float(step))
        leaders = [event for event in active if event.role == "bass_leader"]
        assert len(leaders) <= 1


def test_arrangement_rotates_layers_every_4_bars() -> None:
    tracks, features = _many_tracks()
    config = script.PlannerConfig(target_bpm=133.0, duration_bars=48, rotation_bars=4, max_layers=12, seed=3)

    plan = script.plan_arrangement(tracks, features, config)

    bar_s = script.bar_seconds(config.target_bpm)
    for window in range(1, config.duration_bars // config.rotation_bars):
        prev = {
            (e.track_index, e.stem, e.role)
            for e in script.active_events_at(plan, (window - 1) * config.rotation_bars * bar_s + 0.1)
        }
        cur = {
            (e.track_index, e.stem, e.role)
            for e in script.active_events_at(plan, window * config.rotation_bars * bar_s + 0.1)
        }
        assert prev != cur


def test_arrangement_uses_broad_source_set() -> None:
    tracks, features = _many_tracks(72)
    config = script.PlannerConfig(target_bpm=133.0, duration_bars=96, rotation_bars=4, max_layers=12, seed=11)

    plan = script.plan_arrangement(tracks, features, config)

    used_tracks = {event.track_index for event in plan.events}

    assert len(used_tracks) >= 36

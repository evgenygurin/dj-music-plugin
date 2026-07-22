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

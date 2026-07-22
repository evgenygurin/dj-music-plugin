from __future__ import annotations

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

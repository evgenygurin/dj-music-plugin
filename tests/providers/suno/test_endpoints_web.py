"""Tests for the Suno web endpoint registry."""

from __future__ import annotations

import pytest

from app.providers.suno import endpoints_web as w
from app.shared.errors import ValidationError


def test_web_operations_cover_creation_surface() -> None:
    ops = w.suno_web_operations()
    assert {"create", "extend", "concat"} <= set(ops["generation"])
    assert set(ops["edit"]) == {"crop", "fade", "reverse"}
    assert set(ops["stem"]) == {"create", "sample_pack"}
    assert set(ops["playlist"]) == {"create", "add_tracks", "remove_tracks"}


def test_web_entities_include_creation_families() -> None:
    ents = w.suno_web_entities()
    for e in ("generation", "clip", "stem", "wav", "edit", "remaster", "persona", "playlist"):
        assert e in ents


def test_clip_read_kinds_map_to_real_paths() -> None:
    assert w.CLIP_READ_KINDS["downbeats"].path == "/api/gen/{id}/downbeats"
    assert w.CLIP_READ_KINDS["waveform"].path == "/api/gen/{id}/waveform-aggregates"
    assert w.CLIP_READ_KINDS["stems"].path == "/api/clip/{id}/stems"


def test_build_web_body_merges_const_and_validates_required() -> None:
    ep = w.WEB_WRITE[("edit", "crop")]
    body = w.build_web_body({"crop_start_s": 1.0, "crop_end_s": 5.0}, ep)
    assert body["is_crop_remove"] is False
    assert body["ui_surface"] == "song_actions"
    assert body["crop_start_s"] == 1.0
    with pytest.raises(ValidationError, match="crop_start_s"):
        w.build_web_body({"crop_end_s": 5.0}, ep)


def test_build_web_body_keeps_arrays() -> None:
    ep = w.WEB_WRITE[("playlist", "add_tracks")]
    body = w.build_web_body({"clip_ids": ("a", "b")}, ep)
    assert body["clip_ids"] == ["a", "b"]

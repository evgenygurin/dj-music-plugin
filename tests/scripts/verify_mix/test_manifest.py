from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_mix.manifest import (
    Layer,
    ManifestError,
    load_manifest,
    parse_manifest,
)

GOOD: dict[str, Any] = {
    "output": "mix.mp3",
    "backbone": {"source": "backbone.wav", "bpm": 124.53, "bed": True},
    "layers": [
        {
            "source": "vocals.wav",
            "role": "vocal",
            "src_trim": [15.7, 64.0],
            "tempo_ratio": 1.00024,
            "place_at": 10.0,
            "gain": 1.05,
        }
    ],
}


def test_parse_good_manifest() -> None:
    manifest = parse_manifest(GOOD, base_dir=Path("/work"))

    assert manifest.output == Path("mix.mp3")
    assert manifest.backbone.bpm == pytest.approx(124.53)
    assert manifest.backbone.bed is True
    layer = manifest.layers[0]
    assert layer.role == "vocal"
    assert layer.src_trim == (15.7, 64.0)
    assert layer.src_duration == pytest.approx(48.3)
    assert layer.out_duration == pytest.approx(48.3 / 1.00024)
    assert layer.out_end == pytest.approx(10.0 + 48.3 / 1.00024)


def test_paths_resolve_relative_to_manifest_dir() -> None:
    manifest = parse_manifest(GOOD, base_dir=Path("/work"))

    assert manifest.output_path == Path("/work/mix.mp3")
    assert manifest.backbone_path == Path("/work/backbone.wav")
    assert manifest.layer_path(manifest.layers[0]) == Path("/work/vocals.wav")


def test_absolute_paths_kept() -> None:
    data = dict(GOOD, output="/abs/mix.mp3")
    manifest = parse_manifest(data, base_dir=Path("/work"))

    assert manifest.output_path == Path("/abs/mix.mp3")


def test_layer_defaults() -> None:
    data = {
        "output": "m.mp3",
        "backbone": {"source": "b.wav", "bpm": 130},
        "layers": [{"source": "l.wav", "role": "bed", "src_trim": [0, 10]}],
    }
    layer = parse_manifest(data).layers[0]

    assert layer.tempo_ratio == 1.0
    assert layer.place_at == 0.0
    assert layer.gain == 1.0


@pytest.mark.parametrize(
    "mutate",
    [
        {"role": "drums"},  # unknown role
        {"src_trim": [10.0, 5.0]},  # reversed trim
        {"src_trim": [-1.0, 5.0]},  # negative start
        {"src_trim": [5.0]},  # wrong arity
        {"tempo_ratio": 3.0},  # outside sanity bounds
        {"place_at": -2.0},  # negative placement
        {"gain": 0.0},  # non-positive gain
    ],
)
def test_bad_layer_rejected(mutate: dict[str, object]) -> None:
    data = json.loads(json.dumps(GOOD))
    data["layers"][0].update(mutate)

    with pytest.raises(ManifestError):
        parse_manifest(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("output"),
        lambda d: d.pop("backbone"),
        lambda d: d["backbone"].pop("bpm"),
        lambda d: d["backbone"].update({"bpm": 500}),
        lambda d: d["layers"][0].pop("source"),
    ],
)
def test_bad_manifest_rejected(mutate: Callable[[dict[str, Any]], object]) -> None:
    data = json.loads(json.dumps(GOOD))
    mutate(data)

    with pytest.raises(ManifestError):
        parse_manifest(data)


def test_load_manifest_from_file(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(GOOD), encoding="utf-8")

    manifest = load_manifest(path)

    assert manifest.base_dir == tmp_path.resolve()
    assert manifest.backbone_path == tmp_path.resolve() / "backbone.wav"


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "nope.json")


def test_load_manifest_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ManifestError, match="not valid JSON"):
        load_manifest(path)


def test_layer_time_mapping_with_stretch() -> None:
    layer = Layer(
        source=Path("l.wav"),
        role="bed",
        src_trim=(0.0, 60.0),
        tempo_ratio=1.2,
        place_at=30.0,
    )

    # 60 s of source squeezed to 50 s on the timeline
    assert layer.out_duration == pytest.approx(50.0)
    assert layer.out_end == pytest.approx(80.0)

"""Build-plan manifest — dataclasses + JSON load/validate.

The manifest is the single source of truth for an assembled mix: the
ffmpeg graph is generated *from* it, and the verifier reads the *same*
manifest, so what is verified is exactly what was rendered.

Schema (see docs/superpowers/specs/2026-07-07-mix-verify-design.md):

    {
      "output": "mix.mp3",
      "backbone": { "source": "backbone.wav", "bpm": 124.53, "bed": true },
      "layers": [
        { "source": "vocals.wav", "role": "vocal",
          "src_trim": [15.7, 64.0], "tempo_ratio": 1.00024,
          "place_at": 0.0, "gain": 1.05 }
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_ROLES: frozenset[str] = frozenset({"vocal", "bed"})

# Sanity bounds — outside these the manifest is a typo, not a mix.
_BPM_MIN, _BPM_MAX = 20.0, 300.0
_TEMPO_RATIO_MIN, _TEMPO_RATIO_MAX = 0.5, 2.0


class ManifestError(ValueError):
    """Manifest failed structural validation."""


@dataclass(frozen=True, slots=True)
class Layer:
    """One placed layer of the mix."""

    source: Path
    role: str
    src_trim: tuple[float, float]
    tempo_ratio: float = 1.0
    place_at: float = 0.0
    gain: float = 1.0

    @property
    def src_duration(self) -> float:
        """Duration of the trimmed source region, in source time."""
        return self.src_trim[1] - self.src_trim[0]

    @property
    def out_duration(self) -> float:
        """Duration on the output timeline (after tempo stretch)."""
        return self.src_duration / self.tempo_ratio

    @property
    def out_end(self) -> float:
        """End position on the output timeline."""
        return self.place_at + self.out_duration


@dataclass(frozen=True, slots=True)
class Backbone:
    """The continuous base track the layers are placed over."""

    source: Path
    bpm: float
    bed: bool = True
    gain: float = 1.0


@dataclass(frozen=True, slots=True)
class Manifest:
    """Full build plan for one assembled mix."""

    output: Path
    backbone: Backbone
    layers: tuple[Layer, ...] = field(default_factory=tuple)
    base_dir: Path = field(default_factory=Path.cwd)

    def resolve(self, path: Path) -> Path:
        """Resolve a manifest-relative path against the manifest's dir."""
        return path if path.is_absolute() else self.base_dir / path

    @property
    def output_path(self) -> Path:
        return self.resolve(self.output)

    @property
    def backbone_path(self) -> Path:
        return self.resolve(self.backbone.source)

    def layer_path(self, layer: Layer) -> Path:
        return self.resolve(layer.source)


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise ManifestError(f"{where}: missing required key '{key}'")
    return data[key]


def _parse_layer(data: dict[str, Any], index: int) -> Layer:
    where = f"layers[{index}]"
    role = str(_require(data, "role", where))
    if role not in VALID_ROLES:
        raise ManifestError(f"{where}: role '{role}' not in {sorted(VALID_ROLES)}")

    raw_trim = _require(data, "src_trim", where)
    if not isinstance(raw_trim, list | tuple) or len(raw_trim) != 2:
        raise ManifestError(f"{where}: src_trim must be [start_s, end_s]")
    trim = (float(raw_trim[0]), float(raw_trim[1]))
    if trim[0] < 0 or trim[1] <= trim[0]:
        raise ManifestError(f"{where}: src_trim {trim} must satisfy 0 <= start < end")

    tempo_ratio = float(data.get("tempo_ratio", 1.0))
    if not _TEMPO_RATIO_MIN <= tempo_ratio <= _TEMPO_RATIO_MAX:
        raise ManifestError(
            f"{where}: tempo_ratio {tempo_ratio} outside [{_TEMPO_RATIO_MIN}, {_TEMPO_RATIO_MAX}]"
        )

    place_at = float(data.get("place_at", 0.0))
    if place_at < 0:
        raise ManifestError(f"{where}: place_at {place_at} must be >= 0")

    gain = float(data.get("gain", 1.0))
    if gain <= 0:
        raise ManifestError(f"{where}: gain {gain} must be > 0")

    return Layer(
        source=Path(str(_require(data, "source", where))),
        role=role,
        src_trim=trim,
        tempo_ratio=tempo_ratio,
        place_at=place_at,
        gain=gain,
    )


def _parse_backbone(data: dict[str, Any]) -> Backbone:
    where = "backbone"
    bpm = float(_require(data, "bpm", where))
    if not _BPM_MIN <= bpm <= _BPM_MAX:
        raise ManifestError(f"{where}: bpm {bpm} outside [{_BPM_MIN}, {_BPM_MAX}]")
    gain = float(data.get("gain", 1.0))
    if gain <= 0:
        raise ManifestError(f"{where}: gain {gain} must be > 0")
    return Backbone(
        source=Path(str(_require(data, "source", where))),
        bpm=bpm,
        bed=bool(data.get("bed", True)),
        gain=gain,
    )


def parse_manifest(data: dict[str, Any], base_dir: Path | None = None) -> Manifest:
    """Build a validated :class:`Manifest` from a parsed JSON dict."""
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a JSON object")
    output = Path(str(_require(data, "output", "manifest")))
    backbone = _parse_backbone(_require(data, "backbone", "manifest"))
    raw_layers = data.get("layers", [])
    if not isinstance(raw_layers, list):
        raise ManifestError("manifest: 'layers' must be a list")
    layers = tuple(_parse_layer(item, i) for i, item in enumerate(raw_layers))
    return Manifest(
        output=output,
        backbone=backbone,
        layers=layers,
        base_dir=base_dir or Path.cwd(),
    )


def load_manifest(path: Path | str) -> Manifest:
    """Load and validate a build manifest from a JSON file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(f"manifest not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {path}: {exc}") from exc
    return parse_manifest(data, base_dir=path.parent.resolve())

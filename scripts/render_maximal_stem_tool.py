from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
OUT_DIR = Path("generated-sets/maximal-stem-tool-2026-07-22")
STEM_ORDER: tuple[str, ...] = ("acappella", "bass", "drums", "harmonic", "instrumental")
STEM_PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>[\w-]+)\]\s+"
    r"(?P<title>.+)-(?P<stem>acappella|bass|drums|harmonic|instrumental)\.m4a$"
)


@dataclass(slots=True)
class StemTrack:
    index: int
    title: str
    bpm: float
    genre: str
    stems: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StemFeature:
    track_index: int
    stem: str
    path: str
    mtime_ns: int
    size: int
    rms_db: float
    low_ratio: float
    mid_ratio: float
    high_ratio: float
    centroid_hz: float
    onset_rate: float
    chroma_peak: int | None


def feature_key(path: Path) -> str:
    return str(path.resolve())


def _feature_from_cache(key: str, payload: dict[str, Any], path: Path) -> StemFeature | None:
    stat = path.stat()
    if payload.get("path") != str(path):
        return None
    if payload.get("mtime_ns") != stat.st_mtime_ns or payload.get("size") != stat.st_size:
        return None
    return StemFeature(**payload)


def _load_feature_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _write_feature_cache(cache_path: Path, features: dict[str, StemFeature]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({key: asdict(feature) for key, feature in features.items()}, indent=2),
        encoding="utf-8",
    )


def extract_stem_feature(track: StemTrack, stem: str) -> StemFeature:
    import librosa
    import numpy as np

    path = track.stems[stem]
    stat = path.stat()
    y, sr = librosa.load(str(path), sr=22050, mono=True, duration=30.0)
    if y.size == 0:
        raise RuntimeError(f"empty audio: {path}")
    rms_db = float(20.0 * np.log10(np.sqrt(np.mean(y**2)) + 1e-9))
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1 / sr)
    total = float(np.sum(spec) + 1e-12)
    low_ratio = float(np.sum(spec[(freqs >= 20) & (freqs < 160)]) / total)
    mid_ratio = float(np.sum(spec[(freqs >= 160) & (freqs < 2500)]) / total)
    high_ratio = float(np.sum(spec[(freqs >= 2500) & (freqs < 12000)]) / total)
    centroid_hz = float(np.sum(freqs * spec) / total)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_rate = float(np.mean(onset_env))
    chroma_peak: int | None = None
    if stem in {"harmonic", "instrumental", "acappella"}:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_peak = int(np.argmax(np.mean(chroma, axis=1)))
    return StemFeature(
        track_index=track.index,
        stem=stem,
        path=str(path),
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
        rms_db=rms_db,
        low_ratio=low_ratio,
        mid_ratio=mid_ratio,
        high_ratio=high_ratio,
        centroid_hz=centroid_hz,
        onset_rate=onset_rate,
        chroma_peak=chroma_peak,
    )


def scan_features(tracks: Sequence[StemTrack], cache_path: Path) -> dict[str, StemFeature]:
    raw_cache = _load_feature_cache(cache_path)
    features: dict[str, StemFeature] = {}
    failed_tracks: set[int] = set()
    for track in tracks:
        staged: dict[str, StemFeature] = {}
        try:
            for stem in STEM_ORDER:
                path = track.stems[stem]
                key = feature_key(path)
                cached = _feature_from_cache(key, raw_cache.get(key, {}), path)
                staged[key] = cached if cached is not None else extract_stem_feature(track, stem)
        except Exception as exc:
            print(f"WARN skipping track {track.index} {track.title}: {exc}")
            failed_tracks.add(track.index)
            continue
        features.update(staged)
    if not features:
        raise RuntimeError("feature scan produced no usable tracks")
    _write_feature_cache(cache_path, features)
    if failed_tracks:
        print(f"WARN skipped {len(failed_tracks)} tracks during feature scan")
    return features


@dataclass(frozen=True, slots=True)
class SectionSpec:
    name: str
    start: float
    end: float
    density: tuple[int, int]
    preferred_genres: tuple[str, ...]


SECTION_ARC: tuple[SectionSpec, ...] = (
    SectionSpec(
        "intro_hypnotic",
        0.00,
        0.15,
        (5, 8),
        ("hypnotic", "dub_techno", "minimal", "progressive", "detroit"),
    ),
    SectionSpec(
        "build_driving",
        0.15,
        0.38,
        (8, 10),
        ("hypnotic", "driving", "progressive", "acid", "detroit"),
    ),
    SectionSpec(
        "pressure",
        0.38,
        0.76,
        (10, 12),
        ("driving", "industrial", "peak_time", "acid", "detroit"),
    ),
    SectionSpec(
        "peak_release",
        0.76,
        0.91,
        (10, 12),
        ("industrial", "peak_time", "hard_techno", "driving", "acid"),
    ),
    SectionSpec(
        "outro_control",
        0.91,
        1.00,
        (5, 8),
        ("dub_techno", "hypnotic", "detroit", "progressive", "driving"),
    ),
)


def choose_target_bpm(tracks: Sequence[StemTrack]) -> float:
    candidates = [track.bpm for track in tracks if 128.0 <= track.bpm <= 138.0]
    if not candidates:
        return 133.0
    avg = sum(candidates) / len(candidates)
    return max(132.0, min(134.0, round(avg)))


def track_features(features: dict[str, StemFeature], track: StemTrack) -> dict[str, StemFeature]:
    selected: dict[str, StemFeature] = {}
    for stem in STEM_ORDER:
        key = feature_key(track.stems[stem])
        if key in features:
            selected[stem] = features[key]
    return selected


def _genre_score(genre: str, preferred: tuple[str, ...]) -> float:
    if genre not in preferred:
        return -2.5
    return 5.0 - preferred.index(genre) * 0.65


def score_track_for_section(
    track: StemTrack,
    features: dict[str, StemFeature],
    section: SectionSpec,
    target_bpm: float,
    reuse_count: int,
) -> float:
    per_stem = track_features(features, track)
    bpm_penalty = abs(track.bpm - target_bpm) * 0.8
    reuse_penalty = reuse_count * 2.0
    low_penalty = (
        max(0.0, per_stem.get("bass", _feature_fallback(track, "bass")).low_ratio - 0.38)
        * 4.0
    )
    drum_bonus = min(
        2.0,
        per_stem.get("drums", _feature_fallback(track, "drums")).onset_rate * 0.2,
    )
    brightness = per_stem.get("harmonic", _feature_fallback(track, "harmonic")).high_ratio
    brightness_bonus = min(1.0, brightness * 2.0)
    return (
        _genre_score(track.genre, section.preferred_genres)
        + drum_bonus
        + brightness_bonus
        - bpm_penalty
        - reuse_penalty
        - low_penalty
    )


def _feature_fallback(track: StemTrack, stem: str) -> StemFeature:
    return StemFeature(
        track_index=track.index,
        stem=stem,
        path=str(track.stems[stem]),
        mtime_ns=0,
        size=0,
        rms_db=-24.0,
        low_ratio=0.2,
        mid_ratio=0.5,
        high_ratio=0.3,
        centroid_hz=1000.0,
        onset_rate=1.0,
        chroma_peak=None,
    )


def complete_tracks(tracks: Iterable[StemTrack]) -> list[StemTrack]:
    required = set(STEM_ORDER)
    return sorted(
        (track for track in tracks if required.issubset(track.stems)),
        key=lambda track: track.index,
    )


def parse_catalog(stems_dir: Path) -> list[StemTrack]:
    if not stems_dir.exists():
        raise FileNotFoundError(f"stems directory does not exist: {stems_dir}")
    if not stems_dir.is_dir():
        raise NotADirectoryError(f"stems path is not a directory: {stems_dir}")

    by_index: dict[int, StemTrack] = {}
    matched = 0
    for path in sorted(stems_dir.glob("*.m4a")):
        match = STEM_PATTERN.match(path.name)
        if match is None:
            continue
        matched += 1
        idx = int(match.group("index"))
        track = by_index.setdefault(
            idx,
            StemTrack(
                index=idx,
                title=match.group("title"),
                bpm=float(match.group("bpm")),
                genre=match.group("genre"),
            ),
        )
        track.stems[match.group("stem")] = path

    if matched == 0:
        raise RuntimeError(f"no prepared stem files matched in {stems_dir}")

    tracks = complete_tracks(by_index.values())
    if not tracks:
        raise RuntimeError(f"no complete five-stem tracks found in {stems_dir}")
    return tracks

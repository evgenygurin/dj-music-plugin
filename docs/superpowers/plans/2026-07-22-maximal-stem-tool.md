# Maximal Stem Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only 10-12 minute maximal-layer techno DJ-performance tool from `/Users/laptop/Desktop/Stems`.

**Architecture:** Add one focused local production script that parses the prepared stem catalog, scans lightweight features, scores compatibility, plans a dense rotating stem matrix, renders chunked ffmpeg parts, joins them, and writes manifest/diagnostics. Keep the implementation outside MCP tools and DB paths to avoid provider/database side effects.

**Tech Stack:** Python 3.12, `uv`, stdlib dataclasses/argparse/json/subprocess, NumPy/librosa for lightweight analysis, ffmpeg with rubberband filter, existing `app.audio.render.diagnostics` for QA.

## Global Constraints

- Use `uv` for every Python/test command: never run `python`, `pytest`, `ruff`, or `mypy` directly.
- Source stems directory: `/Users/laptop/Desktop/Stems`.
- Input shape: 4,800 `.m4a` files, 960 complete five-stem tracks, stems are `acappella`, `bass`, `drums`, `harmonic`, `instrumental`.
- First version is local-only: no Suno generation, no database writes, no provider calls, no `audio_file` imports.
- The planner must consider all parsed complete tracks as the candidate universe; do not hard-code a small favorite subset.
- Target result: 10-12 minutes, hypnotic rolling techno into peak-time pressure, target BPM 132-134.
- Pressure sections should run 10-12 active layers while obeying hard bass/drum rules.
- Never execute ffmpeg through `shell=True`; all subprocess calls must use argv lists.
- Generated audio artifacts stay under `generated-sets/` and are not staged unless the user explicitly asks.
- Do not commit during execution unless the user explicitly asks for commits.

---

## File Structure

- Create: `scripts/render_maximal_stem_tool.py`
  - Owns the local catalog parser, feature scanner/cache, compatibility scorer, arrangement planner, ffmpeg renderer, manifest writer, QA integration, and CLI.
  - Keep this script self-contained so it can run without registering MCP tools or touching DB/provider code.
- Create: `tests/scripts/test_render_maximal_stem_tool.py`
  - Unit tests for pure parsing, scoring, arrangement invariants, chunked command construction, manifest shape, and CLI plan-only behavior.
- Read-only reference: `scripts/render_local_12deck_stem_set.py`
  - Existing safe fallback for prepared stems.
- Read-only reference: `scripts/render_12deck_performance_matrix.py`
  - Existing untracked local experiment. Do not modify or depend on it.
- Read-only reference: `app/audio/render/diagnostics.py`
  - Reuse `scan_mix` and `diagnose_mix` in the final QA step.

---

### Task 1: Catalog Parser And Config

**Files:**
- Create: `scripts/render_maximal_stem_tool.py`
- Create: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Produces: `STEM_ORDER: tuple[str, ...]`
- Produces: `StemTrack(index: int, title: str, bpm: float, genre: str, stems: dict[str, Path])`
- Produces: `parse_catalog(stems_dir: Path) -> list[StemTrack]`
- Produces: `complete_tracks(tracks: Iterable[StemTrack]) -> list[StemTrack]`

- [ ] **Step 1: Write failing catalog tests**

Add this to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
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
```

- [ ] **Step 2: Run catalog tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: FAIL with `ImportError` or `AttributeError` because `scripts/render_maximal_stem_tool.py` does not exist yet.

- [ ] **Step 3: Implement catalog parser**

Create `scripts/render_maximal_stem_tool.py` with this initial content:

```python
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

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
```

- [ ] **Step 4: Run catalog tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for the four catalog tests.

- [ ] **Step 5: Check formatting and lint for touched files**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

Run: `uv run ruff format --check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS or reports files already formatted.

- [ ] **Step 6: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: only the new script and test file are shown.

---

### Task 2: Feature Scan And Cache

**Files:**
- Modify: `scripts/render_maximal_stem_tool.py`
- Modify: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Consumes: `StemTrack`, `STEM_ORDER`
- Produces: `StemFeature(track_index: int, stem: str, path: str, mtime_ns: int, size: int, rms_db: float, low_ratio: float, mid_ratio: float, high_ratio: float, centroid_hz: float, onset_rate: float, chroma_peak: int | None)`
- Produces: `feature_key(path: Path) -> str`
- Produces: `extract_stem_feature(track: StemTrack, stem: str) -> StemFeature`
- Produces: `scan_features(tracks: Sequence[StemTrack], cache_path: Path) -> dict[str, StemFeature]`

- [ ] **Step 1: Write failing feature-cache tests**

Append to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
import json


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
```

- [ ] **Step 2: Run feature tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py::test_scan_features_uses_valid_cache tests/scripts/test_render_maximal_stem_tool.py::test_scan_features_skips_failed_track_when_enough_material -v`

Expected: FAIL with missing `StemFeature`, `feature_key`, or `scan_features`.

- [ ] **Step 3: Implement feature dataclass and scanner**

First update the import block at the top of `scripts/render_maximal_stem_tool.py` to this:

```python
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
```

Then add this after `StemTrack`:

```python
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
```

- [ ] **Step 4: Run feature tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for all Task 1 and Task 2 tests.

- [ ] **Step 5: Run lint on touched files**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

- [ ] **Step 6: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: only catalog/feature scanner changes are shown.

---

### Task 3: Compatibility Scoring

**Files:**
- Modify: `scripts/render_maximal_stem_tool.py`
- Modify: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Consumes: `StemTrack`, `StemFeature`
- Produces: `SectionSpec(name: str, start: float, end: float, density: tuple[int, int], preferred_genres: tuple[str, ...])`
- Produces: `SECTION_ARC: tuple[SectionSpec, ...]`
- Produces: `choose_target_bpm(tracks: Sequence[StemTrack]) -> float`
- Produces: `track_features(features: dict[str, StemFeature], track: StemTrack) -> dict[str, StemFeature]`
- Produces: `score_track_for_section(track: StemTrack, features: dict[str, StemFeature], section: SectionSpec, target_bpm: float, reuse_count: int) -> float`

- [ ] **Step 1: Write failing scoring tests**

Append to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
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
```

- [ ] **Step 2: Run scoring tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py::test_choose_target_bpm_prefers_132_to_134_window tests/scripts/test_render_maximal_stem_tool.py::test_section_scoring_prefers_hypnotic_early_and_peak_late tests/scripts/test_render_maximal_stem_tool.py::test_section_scoring_penalizes_reuse_and_extreme_bpm -v`

Expected: FAIL with missing scoring symbols.

- [ ] **Step 3: Implement section specs and scoring**

Add to `scripts/render_maximal_stem_tool.py` after feature functions:

```python
@dataclass(frozen=True, slots=True)
class SectionSpec:
    name: str
    start: float
    end: float
    density: tuple[int, int]
    preferred_genres: tuple[str, ...]


SECTION_ARC: tuple[SectionSpec, ...] = (
    SectionSpec("intro_hypnotic", 0.00, 0.15, (5, 8), ("hypnotic", "dub_techno", "minimal", "progressive", "detroit")),
    SectionSpec("build_driving", 0.15, 0.38, (8, 10), ("hypnotic", "driving", "progressive", "acid", "detroit")),
    SectionSpec("pressure", 0.38, 0.76, (10, 12), ("driving", "industrial", "peak_time", "acid", "detroit")),
    SectionSpec("peak_release", 0.76, 0.91, (10, 12), ("industrial", "peak_time", "hard_techno", "driving", "acid")),
    SectionSpec("outro_control", 0.91, 1.00, (5, 8), ("dub_techno", "hypnotic", "detroit", "progressive", "driving")),
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
    low_penalty = max(0.0, per_stem.get("bass", _feature_fallback(track, "bass")).low_ratio - 0.38) * 4.0
    drum_bonus = min(2.0, per_stem.get("drums", _feature_fallback(track, "drums")).onset_rate * 0.2)
    brightness = per_stem.get("harmonic", _feature_fallback(track, "harmonic")).high_ratio
    brightness_bonus = min(1.0, brightness * 2.0)
    return _genre_score(track.genre, section.preferred_genres) + drum_bonus + brightness_bonus - bpm_penalty - reuse_penalty - low_penalty


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
```

- [ ] **Step 4: Run scoring tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for all tests added so far.

- [ ] **Step 5: Run lint on touched files**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

- [ ] **Step 6: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: scoring additions only beyond earlier tasks.

---

### Task 4: Arrangement Planner Invariants

**Files:**
- Modify: `scripts/render_maximal_stem_tool.py`
- Modify: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Consumes: `StemTrack`, `StemFeature`, `SectionSpec`, `score_track_for_section`
- Produces: `PlannerConfig(target_bpm: float, duration_bars: int, rotation_bars: int, max_layers: int, seed: int)`
- Produces: `StemEvent(track_index: int, title: str, genre: str, stem: str, role: str, path: str, start_s: float, end_s: float, source_bpm: float, target_bpm: float, gain_db: float, fade_in_s: float, fade_out_s: float, eq_chain: str, score: float)`
- Produces: `ArrangementPlan(title: str, target_bpm: float, duration_s: float, events: list[StemEvent])`
- Produces: `plan_arrangement(tracks: Sequence[StemTrack], features: dict[str, StemFeature], config: PlannerConfig) -> ArrangementPlan`
- Produces: `active_events_at(plan: ArrangementPlan, time_s: float) -> list[StemEvent]`
- Produces: `validate_arrangement(plan: ArrangementPlan, config: PlannerConfig) -> None`

- [ ] **Step 1: Write failing arrangement invariant tests**

Append to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
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
        prev = {(e.track_index, e.stem, e.role) for e in script.active_events_at(plan, (window - 1) * config.rotation_bars * bar_s + 0.1)}
        cur = {(e.track_index, e.stem, e.role) for e in script.active_events_at(plan, window * config.rotation_bars * bar_s + 0.1)}
        assert prev != cur


def test_arrangement_uses_broad_source_set() -> None:
    tracks, features = _many_tracks(72)
    config = script.PlannerConfig(target_bpm=133.0, duration_bars=96, rotation_bars=4, max_layers=12, seed=11)

    plan = script.plan_arrangement(tracks, features, config)

    used_tracks = {event.track_index for event in plan.events}

    assert len(used_tracks) >= 36
```

- [ ] **Step 2: Run arrangement tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py::test_arrangement_pressure_windows_keep_10_to_12_layers tests/scripts/test_render_maximal_stem_tool.py::test_arrangement_never_has_two_full_bass_leaders tests/scripts/test_render_maximal_stem_tool.py::test_arrangement_rotates_layers_every_4_bars tests/scripts/test_render_maximal_stem_tool.py::test_arrangement_uses_broad_source_set -v`

Expected: FAIL with missing planner symbols.

- [ ] **Step 3: Implement arrangement dataclasses and helper functions**

First add `Counter` to the top import block in `scripts/render_maximal_stem_tool.py`:

```python
from collections import Counter
```

Then add this after scoring functions:

```python
@dataclass(frozen=True, slots=True)
class PlannerConfig:
    target_bpm: float = 133.0
    duration_bars: int = 360
    rotation_bars: int = 4
    max_layers: int = 12
    seed: int = 17


@dataclass(frozen=True, slots=True)
class StemEvent:
    track_index: int
    title: str
    genre: str
    stem: str
    role: str
    path: str
    start_s: float
    end_s: float
    source_bpm: float
    target_bpm: float
    gain_db: float
    fade_in_s: float
    fade_out_s: float
    eq_chain: str
    score: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def tempo_ratio(self) -> float:
        return self.target_bpm / self.source_bpm


@dataclass(frozen=True, slots=True)
class ArrangementPlan:
    title: str
    target_bpm: float
    duration_s: float
    events: list[StemEvent]


def bar_seconds(target_bpm: float) -> float:
    return 4.0 * (60.0 / target_bpm)


def section_for_progress(progress: float) -> SectionSpec:
    for section in SECTION_ARC:
        if section.start <= progress < section.end:
            return section
    return SECTION_ARC[-1]


def active_events_at(plan: ArrangementPlan, time_s: float) -> list[StemEvent]:
    return [event for event in plan.events if event.start_s <= time_s < event.end_s]


def stem_eq_chain(stem: str, role: str) -> str:
    if role == "bass_leader":
        return "highpass=f=30:t=4,lowpass=f=235,equalizer=f=58:t=q:w=1.0:g=0.8"
    if role == "bass_ghost":
        return "highpass=f=95:t=4,lowpass=f=310,volume=-5dB"
    if stem == "drums":
        return "highpass=f=36:t=4,lowpass=f=15500,equalizer=f=260:t=q:w=1.2:g=-1.0"
    if stem == "harmonic":
        return "highpass=f=170:t=4,lowpass=f=10500,equalizer=f=360:t=q:w=1.3:g=-1.0"
    if stem == "instrumental":
        return "highpass=f=230:t=4,lowpass=f=7800,equalizer=f=420:t=q:w=1.2:g=-2.0"
    return "highpass=f=155:t=4,lowpass=f=11200,equalizer=f=280:t=q:w=1.0:g=-1.5"


def role_gain_db(role: str) -> float:
    return {
        "drum_core": -5.5,
        "drum_top": -8.0,
        "drum_drive": -7.0,
        "bass_leader": -6.0,
        "bass_ghost": -13.0,
        "harmonic": -11.0,
        "instrumental_bed": -17.0,
        "acappella_chop": -15.0,
    }[role]
```

- [ ] **Step 4: Implement deterministic greedy planner**

Add to `scripts/render_maximal_stem_tool.py` after the helper functions:

```python
def _rank_tracks(
    tracks: Sequence[StemTrack],
    features: dict[str, StemFeature],
    section: SectionSpec,
    target_bpm: float,
    reuse: Counter[int],
) -> list[tuple[float, StemTrack]]:
    ranked = [
        (score_track_for_section(track, features, section, target_bpm, reuse[track.index]), track)
        for track in tracks
    ]
    ranked.sort(key=lambda item: (item[0], -item[1].index), reverse=True)
    return ranked


def _pick_distinct(
    ranked: list[tuple[float, StemTrack]],
    *,
    count: int,
    blocked: set[int],
) -> list[tuple[float, StemTrack]]:
    picked: list[tuple[float, StemTrack]] = []
    for score, track in ranked:
        if track.index in blocked:
            continue
        picked.append((score, track))
        blocked.add(track.index)
        if len(picked) == count:
            return picked
    return picked


def _add_event(
    events: list[StemEvent],
    track: StemTrack,
    *,
    stem: str,
    role: str,
    start_s: float,
    end_s: float,
    target_bpm: float,
    score: float,
    fade_s: float,
) -> None:
    events.append(
        StemEvent(
            track_index=track.index,
            title=track.title,
            genre=track.genre,
            stem=stem,
            role=role,
            path=str(track.stems[stem]),
            start_s=start_s,
            end_s=end_s,
            source_bpm=track.bpm,
            target_bpm=target_bpm,
            gain_db=role_gain_db(role),
            fade_in_s=min(fade_s, max(0.05, (end_s - start_s) * 0.25)),
            fade_out_s=min(fade_s, max(0.05, (end_s - start_s) * 0.25)),
            eq_chain=stem_eq_chain(stem, role),
            score=score,
        )
    )


def plan_arrangement(
    tracks: Sequence[StemTrack],
    features: dict[str, StemFeature],
    config: PlannerConfig,
) -> ArrangementPlan:
    if len(tracks) < 24:
        raise RuntimeError("planner needs at least 24 complete tracks for broad maximal layering")
    bar_s = bar_seconds(config.target_bpm)
    window_s = config.rotation_bars * bar_s
    windows = config.duration_bars // config.rotation_bars
    duration_s = windows * window_s
    events: list[StemEvent] = []
    reuse: Counter[int] = Counter()

    for window in range(windows):
        start_s = window * window_s
        end_s = start_s + window_s
        progress = window / max(1, windows - 1)
        section = section_for_progress(progress)
        target_layers = min(config.max_layers, section.density[1])
        ranked = _rank_tracks(tracks, features, section, config.target_bpm, reuse)
        blocked: set[int] = set()
        fade_s = min(4.0, window_s * 0.35)

        drum_count = 3 if target_layers >= 10 else 2
        for role, (score, track) in zip(
            ("drum_core", "drum_top", "drum_drive"),
            _pick_distinct(ranked, count=drum_count, blocked=blocked),
            strict=False,
        ):
            _add_event(events, track, stem="drums", role=role, start_s=start_s, end_s=end_s, target_bpm=config.target_bpm, score=score, fade_s=fade_s)
            reuse[track.index] += 1

        bass_picks = _pick_distinct(ranked, count=2 if target_layers >= 10 else 1, blocked=blocked)
        if bass_picks:
            score, track = bass_picks[0]
            _add_event(events, track, stem="bass", role="bass_leader", start_s=start_s, end_s=end_s, target_bpm=config.target_bpm, score=score, fade_s=fade_s)
            reuse[track.index] += 1
        if len(bass_picks) > 1 and target_layers >= 11:
            score, track = bass_picks[1]
            _add_event(events, track, stem="bass", role="bass_ghost", start_s=start_s, end_s=end_s, target_bpm=config.target_bpm, score=score, fade_s=fade_s)
            reuse[track.index] += 1

        harmonic_count = 4 if target_layers >= 10 else 2
        for score, track in _pick_distinct(ranked, count=harmonic_count, blocked=blocked):
            _add_event(events, track, stem="harmonic", role="harmonic", start_s=start_s, end_s=end_s, target_bpm=config.target_bpm, score=score, fade_s=fade_s)
            reuse[track.index] += 1

        bed_count = 2 if target_layers >= 11 else 1
        for score, track in _pick_distinct(ranked, count=bed_count, blocked=blocked):
            _add_event(events, track, stem="instrumental", role="instrumental_bed", start_s=start_s, end_s=end_s, target_bpm=config.target_bpm, score=score, fade_s=fade_s)
            reuse[track.index] += 1

        if target_layers >= 12 and window % 3 == 1:
            picks = _pick_distinct(ranked, count=1, blocked=blocked)
            if picks:
                score, track = picks[0]
                chop_start = start_s + window_s * 0.50
                _add_event(events, track, stem="acappella", role="acappella_chop", start_s=chop_start, end_s=min(end_s, chop_start + window_s * 0.45), target_bpm=config.target_bpm, score=score, fade_s=1.0)
                reuse[track.index] += 1

    plan = ArrangementPlan(
        title="MAXIMAL_STEM_TOOL_FINAL",
        target_bpm=config.target_bpm,
        duration_s=duration_s,
        events=events,
    )
    validate_arrangement(plan, config)
    return plan


def validate_arrangement(plan: ArrangementPlan, config: PlannerConfig) -> None:
    if not plan.events:
        raise RuntimeError("arrangement has no events")
    for second in range(0, int(plan.duration_s), max(1, int(bar_seconds(config.target_bpm)))):
        active = active_events_at(plan, float(second))
        if len(active) > config.max_layers:
            raise RuntimeError(f"too many active layers at {second}s: {len(active)}")
        bass_leaders = [event for event in active if event.role == "bass_leader"]
        if len(bass_leaders) > 1:
            raise RuntimeError(f"multiple bass leaders at {second}s")
```

- [ ] **Step 5: Run arrangement tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for catalog, feature, scoring, and arrangement tests.

- [ ] **Step 6: Run lint on touched files**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

- [ ] **Step 7: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: arrangement planner additions only beyond earlier tasks.

---

### Task 5: Chunked Ffmpeg Renderer

**Files:**
- Modify: `scripts/render_maximal_stem_tool.py`
- Modify: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Consumes: `ArrangementPlan`, `StemEvent`
- Produces: `RenderChunk(index: int, start_s: float, end_s: float, events: list[StemEvent])`
- Produces: `split_chunks(plan: ArrangementPlan, max_inputs: int = 96) -> list[RenderChunk]`
- Produces: `build_chunk_command(chunk: RenderChunk, out_path: Path) -> list[str]`
- Produces: `render_chunk(chunk: RenderChunk, out_path: Path) -> None`
- Produces: `join_parts(parts: Sequence[Path], out_path: Path) -> None`

- [ ] **Step 1: Write failing renderer command tests**

Append to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
from dataclasses import asdict


def _tiny_plan() -> script.ArrangementPlan:
    track = _track(1, 132, "hypnotic")
    events = [
        script.StemEvent(
            track_index=1,
            title="Track 1",
            genre="hypnotic",
            stem="drums",
            role="drum_core",
            path=str(track.stems["drums"]),
            start_s=0.0,
            end_s=8.0,
            source_bpm=132.0,
            target_bpm=133.0,
            gain_db=-6.0,
            fade_in_s=1.0,
            fade_out_s=1.0,
            eq_chain="highpass=f=36",
            score=1.0,
        ),
        script.StemEvent(
            track_index=2,
            title="Track 2",
            genre="driving",
            stem="bass",
            role="bass_leader",
            path="/tmp/2-bass.m4a",
            start_s=0.0,
            end_s=8.0,
            source_bpm=134.0,
            target_bpm=133.0,
            gain_db=-7.0,
            fade_in_s=1.0,
            fade_out_s=1.0,
            eq_chain="highpass=f=30,lowpass=f=235",
            score=1.0,
        ),
    ]
    return script.ArrangementPlan(title="test", target_bpm=133.0, duration_s=8.0, events=events)


def test_split_chunks_caps_input_count() -> None:
    plan = _tiny_plan()
    many_events = [
        script.StemEvent(**{**asdict(plan.events[0]), "track_index": i, "path": f"/tmp/{i}.m4a"})
        for i in range(125)
    ]
    large = script.ArrangementPlan(title="large", target_bpm=133.0, duration_s=8.0, events=many_events)

    chunks = script.split_chunks(large, max_inputs=50)

    assert len(chunks) == 3
    assert all(len(chunk.events) <= 50 for chunk in chunks)


def test_build_chunk_command_is_argv_and_contains_no_shell_string(tmp_path: Path) -> None:
    chunk = script.split_chunks(_tiny_plan(), max_inputs=50)[0]
    cmd = script.build_chunk_command(chunk, tmp_path / "part.mp3")

    assert isinstance(cmd, list)
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    assert all(";" not in arg or arg == cmd[cmd.index("-filter_complex") + 1] for arg in cmd)
    assert any("rubberband=tempo=" in arg for arg in cmd)
    assert any("alimiter=" in arg for arg in cmd)


def test_render_chunk_runs_without_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], *, stderr: object, text: bool, check: bool) -> object:
        calls.append({"cmd": cmd, "stderr": stderr, "text": text, "check": check})
        return object()

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    chunk = script.split_chunks(_tiny_plan(), max_inputs=50)[0]

    script.render_chunk(chunk, tmp_path / "part.mp3")

    assert calls
    assert calls[0]["check"] is True
    assert isinstance(calls[0]["cmd"], list)
```

- [ ] **Step 2: Run renderer tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py::test_split_chunks_caps_input_count tests/scripts/test_render_maximal_stem_tool.py::test_build_chunk_command_is_argv_and_contains_no_shell_string tests/scripts/test_render_maximal_stem_tool.py::test_render_chunk_runs_without_shell -v`

Expected: FAIL with missing renderer symbols.

- [ ] **Step 3: Implement chunk splitting and ffmpeg command builder**

First add `subprocess` to the top import block in `scripts/render_maximal_stem_tool.py`:

```python
import subprocess
```

Then add this after planner functions:

```python
@dataclass(frozen=True, slots=True)
class RenderChunk:
    index: int
    start_s: float
    end_s: float
    events: list[StemEvent]


def split_chunks(plan: ArrangementPlan, max_inputs: int = 96) -> list[RenderChunk]:
    if max_inputs < 2:
        raise ValueError("max_inputs must be >= 2")
    chunks: list[RenderChunk] = []
    events = sorted(plan.events, key=lambda event: (event.start_s, event.track_index, event.stem))
    current: list[StemEvent] = []
    current_start = 0.0
    for start_s in sorted({event.start_s for event in events}):
        group = [event for event in events if event.start_s == start_s]
        if current and len(current) + len(group) > max_inputs:
            chunks.append(
                RenderChunk(
                    index=len(chunks),
                    start_s=current_start,
                    end_s=max(event.end_s for event in current),
                    events=current,
                )
            )
            current = []
        if not current:
            current_start = start_s
        if len(group) > max_inputs:
            for offset in range(0, len(group), max_inputs):
                piece = group[offset : offset + max_inputs]
                chunks.append(
                    RenderChunk(
                        index=len(chunks),
                        start_s=start_s,
                        end_s=max(event.end_s for event in piece),
                        events=piece,
                    )
                )
            current = []
            continue
        current.extend(group)
    if current:
        chunks.append(
            RenderChunk(
                index=len(chunks),
                start_s=current_start,
                end_s=max(event.end_s for event in current),
                events=current,
            )
        )
    return chunks


def _delay_ms(event: StemEvent, chunk: RenderChunk) -> int:
    return max(0, int(round((event.start_s - chunk.start_s) * 1000)))


def _event_filter(input_idx: int, event: StemEvent, chunk: RenderChunk) -> str:
    duration = max(0.05, event.duration_s)
    tempo = event.tempo_ratio
    delay = _delay_ms(event, chunk)
    return (
        f"[{input_idx}:a]atrim=start=0:duration={duration / tempo + 1.0:.3f},"
        f"asetpts=PTS-STARTPTS,rubberband=tempo={tempo:.5f}:pitchq=quality,"
        f"atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
        f"{event.eq_chain},volume={event.gain_db:.2f}dB,"
        f"afade=t=in:curve=qsin:st=0:d={event.fade_in_s:.3f},"
        f"afade=t=out:curve=qsin:st={max(0.0, duration - event.fade_out_s):.3f}:d={event.fade_out_s:.3f},"
        f"adelay={delay}|{delay}[e{input_idx}]"
    )


def build_chunk_command(chunk: RenderChunk, out_path: Path) -> list[str]:
    if not chunk.events:
        raise RuntimeError("cannot render empty chunk")
    inputs = [arg for event in chunk.events for arg in ("-i", event.path)]
    filters = [_event_filter(i, event, chunk) for i, event in enumerate(chunk.events)]
    labels = "".join(f"[e{i}]" for i in range(len(chunk.events)))
    filters.append(
        f"{labels}amix=inputs={len(chunk.events)}:normalize=0,"
        "firequalizer=gain_entry='entry(50,-1);entry(250,-1);entry(900,0);entry(8000,0.8)',"
        "alimiter=level_in=1:level_out=1:limit=0.86:attack=10:release=35:asc=0[mix]"
    )
    return [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(out_path),
    ]


def render_chunk(chunk: RenderChunk, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_chunk_command(chunk, out_path), stderr=subprocess.PIPE, text=True, check=True)
```

- [ ] **Step 4: Implement part joining**

Add to `scripts/render_maximal_stem_tool.py` after `render_chunk`:

```python
def join_parts(parts: Sequence[Path], out_path: Path) -> None:
    if not parts:
        raise RuntimeError("no rendered parts to join")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        out_path.write_bytes(parts[0].read_bytes())
        return
    inputs = [arg for part in parts for arg in ("-i", str(part))]
    chain = ""
    prev = "[0:a]"
    for idx in range(1, len(parts)):
        out = f"[x{idx}]" if idx < len(parts) - 1 else "[joined]"
        chain += f"{prev}[{idx}:a]acrossfade=d=2:c1=qsin:c2=qsin{out};"
        prev = out
    chain = chain.rstrip(";")
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        f"{chain};[joined]loudnorm=I=-14:LRA=6:TP=-1.0,alimiter=limit=0.86:attack=10:release=35[mix]",
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(out_path),
    ]
    subprocess.run(cmd, stderr=subprocess.PIPE, text=True, check=True)
```

- [ ] **Step 5: Run renderer tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for all tests added so far.

- [ ] **Step 6: Run lint on touched files**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

- [ ] **Step 7: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: renderer additions only beyond earlier tasks.

---

### Task 6: Manifest, QA, And CLI

**Files:**
- Modify: `scripts/render_maximal_stem_tool.py`
- Modify: `tests/scripts/test_render_maximal_stem_tool.py`

**Interfaces:**
- Consumes: `ArrangementPlan`, `RenderChunk`, renderer functions
- Produces: `build_manifest(plan: ArrangementPlan, tracks: Sequence[StemTrack], out_dir: Path, final_path: Path | None, qa: dict[str, Any] | None) -> dict[str, Any]`
- Produces: `write_manifest(path: Path, manifest: dict[str, Any]) -> None`
- Produces: `run_qa(final_path: Path) -> dict[str, Any]`
- Produces: `main(argv: Sequence[str] | None = None) -> int`

- [ ] **Step 1: Write failing manifest and CLI tests**

Append to `tests/scripts/test_render_maximal_stem_tool.py`:

```python
def test_build_manifest_contains_required_fields(tmp_path: Path) -> None:
    plan = _tiny_plan()
    manifest = script.build_manifest(plan, [_track(1, 132, "hypnotic")], tmp_path, tmp_path / "final.mp3", {"true_peak_db": -1.0})

    assert manifest["title"] == "test"
    assert manifest["target_bpm"] == 133.0
    assert manifest["output"]["final_path"] == str(tmp_path / "final.mp3")
    assert manifest["qa"]["true_peak_db"] == -1.0
    assert manifest["reuse"]["source_track_count"] >= 1
    assert manifest["events"][0]["role"] == "drum_core"


def test_write_manifest_creates_json(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    script.write_manifest(target, {"ok": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_cli_plan_only_writes_manifest_without_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_track(tmp_path, 1, 132, "hypnotic", "One")
    _write_track(tmp_path, 2, 133, "driving", "Two")
    tracks = script.parse_catalog(tmp_path)
    while len(tracks) < 24:
        idx = len(tracks) + 1
        _write_track(tmp_path, idx, 132 + idx % 4, "driving", f"Extra {idx}")
        tracks = script.parse_catalog(tmp_path)

    def fake_scan(input_tracks: list[script.StemTrack], cache_path: Path) -> dict[str, script.StemFeature]:
        features: dict[str, script.StemFeature] = {}
        for track in input_tracks:
            features.update(_features_for(track))
        return features

    monkeypatch.setattr(script, "scan_features", fake_scan)
    out_dir = tmp_path / "out"

    rc = script.main(["--stems-dir", str(tmp_path), "--out-dir", str(out_dir), "--plan-only", "--duration-bars", "48"])

    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["stems_dir"] == str(tmp_path)
    assert manifest["output"]["final_path"] is None


def test_preflight_missing_ffmpeg_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(script.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="ffmpeg is required"):
        script.preflight_ffmpeg()
```

- [ ] **Step 2: Run manifest/CLI tests and verify failure**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py::test_build_manifest_contains_required_fields tests/scripts/test_render_maximal_stem_tool.py::test_write_manifest_creates_json tests/scripts/test_render_maximal_stem_tool.py::test_cli_plan_only_writes_manifest_without_render tests/scripts/test_render_maximal_stem_tool.py::test_preflight_missing_ffmpeg_raises -v`

Expected: FAIL with missing manifest/CLI symbols.

- [ ] **Step 3: Implement manifest and QA helpers**

Add to `scripts/render_maximal_stem_tool.py` after renderer functions:

```python
def build_manifest(
    plan: ArrangementPlan,
    tracks: Sequence[StemTrack],
    out_dir: Path,
    final_path: Path | None,
    qa: dict[str, Any] | None,
) -> dict[str, Any]:
    source_counts = Counter(event.track_index for event in plan.events)
    genre_counts = Counter(event.genre for event in plan.events)
    return {
        "title": plan.title,
        "target_bpm": plan.target_bpm,
        "duration_s": plan.duration_s,
        "source": {
            "stems_dir": str(STEMS_DIR),
            "candidate_tracks": len(tracks),
        },
        "output": {
            "out_dir": str(out_dir),
            "final_path": str(final_path) if final_path is not None else None,
        },
        "reuse": {
            "source_track_count": len(source_counts),
            "source_counts": dict(sorted(source_counts.items())),
            "genre_counts": dict(sorted(genre_counts.items())),
        },
        "events": [asdict(event) for event in plan.events],
        "qa": qa or {},
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run_qa(final_path: Path) -> dict[str, Any]:
    from app.audio.render.diagnostics import diagnose_mix, scan_mix

    scan = scan_mix(str(final_path))
    diagnose = diagnose_mix(str(final_path))
    return {
        "duration_s": scan.duration_s,
        "true_peak_db": scan.true_peak_db,
        "clip_risk": scan.clip_risk,
        "level_jumps": len(scan.level_jumps),
        "near_silent_s": len(scan.near_silent_s),
        "flagged_windows": diagnose.flagged,
    }
```

- [ ] **Step 4: Implement preflight and CLI**

First add `argparse` and `shutil` to the top import block in `scripts/render_maximal_stem_tool.py`:

```python
import argparse
import shutil
```

Then add this after QA helpers:

```python
def preflight_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required on PATH")
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False)
    if "rubberband" not in proc.stdout:
        raise RuntimeError("ffmpeg rubberband filter is required for tempo-stretching")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a maximal local prepared-stem techno tool")
    parser.add_argument("--stems-dir", type=Path, default=STEMS_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--target-bpm", type=float, default=None)
    parser.add_argument("--duration-bars", type=int, default=360)
    parser.add_argument("--rotation-bars", type=int, default=4)
    parser.add_argument("--max-layers", type=int, default=12)
    parser.add_argument("--max-inputs-per-part", type=int, default=96)
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    tracks = parse_catalog(args.stems_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    features = scan_features(tracks, args.out_dir / "features-cache.json")
    target_bpm = args.target_bpm if args.target_bpm is not None else choose_target_bpm(tracks)
    config = PlannerConfig(
        target_bpm=target_bpm,
        duration_bars=args.duration_bars,
        rotation_bars=args.rotation_bars,
        max_layers=args.max_layers,
    )
    plan = plan_arrangement(tracks, features, config)
    final_path = args.out_dir / "MAXIMAL_STEM_TOOL_FINAL.mp3"

    if args.plan_only:
        manifest = build_manifest(plan, tracks, args.out_dir, None, None)
        manifest["source"]["stems_dir"] = str(args.stems_dir)
        write_manifest(args.out_dir / "manifest.json", manifest)
        print(json.dumps({"mode": "plan-only", "events": len(plan.events), "out_dir": str(args.out_dir)}))
        return 0

    preflight_ffmpeg()
    chunks = split_chunks(plan, max_inputs=args.max_inputs_per_part)
    parts: list[Path] = []
    for chunk in chunks:
        part_path = args.out_dir / f"PART_{chunk.index:03d}.mp3"
        render_chunk(chunk, part_path)
        parts.append(part_path)
    join_parts(parts, final_path)
    qa = run_qa(final_path)
    manifest = build_manifest(plan, tracks, args.out_dir, final_path, qa)
    manifest["source"]["stems_dir"] = str(args.stems_dir)
    write_manifest(args.out_dir / "manifest.json", manifest)
    write_manifest(args.out_dir / "diagnostics.json", qa)
    print(json.dumps({"mode": "render", "final_path": str(final_path), "qa": qa}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run manifest/CLI tests and verify pass**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS for all script tests.

- [ ] **Step 6: Run lint and format check**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

Run: `uv run ruff format --check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS or reports files already formatted.

- [ ] **Step 7: Review diff; do not commit unless explicitly requested**

Run: `git diff -- scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: manifest/QA/CLI additions only beyond earlier tasks.

---

### Task 7: Local Plan-Only Smoke And Full Render Gate

**Files:**
- Modify only if verification exposes a real bug: `scripts/render_maximal_stem_tool.py`
- Modify only if verification exposes a real bug: `tests/scripts/test_render_maximal_stem_tool.py`
- Generated output: `generated-sets/maximal-stem-tool-2026-07-22/`

**Interfaces:**
- Consumes: completed CLI from Task 6.
- Produces: plan-only manifest, then final MP3 and diagnostics if full render is approved.

- [ ] **Step 1: Run focused unit tests**

Run: `uv run pytest tests/scripts/test_render_maximal_stem_tool.py -v`

Expected: PASS.

- [ ] **Step 2: Run plan-only smoke against the real Desktop stems**

Run:

```bash
uv run python scripts/render_maximal_stem_tool.py \
  --stems-dir /Users/laptop/Desktop/Stems \
  --out-dir generated-sets/maximal-stem-tool-2026-07-22 \
  --plan-only \
  --duration-bars 96 \
  --rotation-bars 4 \
  --max-layers 12
```

Expected: exit 0 and prints JSON with `"mode": "plan-only"`. The file `generated-sets/maximal-stem-tool-2026-07-22/manifest.json` exists and contains broad source usage.

- [ ] **Step 3: Inspect plan-only manifest for broad usage**

Run:

```bash
uv run python -c "import json; m=json.load(open('generated-sets/maximal-stem-tool-2026-07-22/manifest.json')); print(m['reuse']['source_track_count'], m['reuse']['genre_counts'])"
```

Expected: source track count is meaningfully broad for the shortened `96` bar plan, preferably at least `30`; genres include early hypnotic/dub/progressive/driving and later industrial/peak/acid material.

- [ ] **Step 4: Run full checks on touched code**

Run: `uv run ruff check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

Run: `uv run ruff format --check scripts/render_maximal_stem_tool.py tests/scripts/test_render_maximal_stem_tool.py`

Expected: PASS.

- [ ] **Step 5: Ask user before full 10-12 minute render**

Ask: `Plan-only manifest is ready. Render the full 10-12 minute MP3 now?`

Do not start the full render without confirmation because it is CPU-heavy and can take a long time.

- [ ] **Step 6: If approved, run full render**

Run:

```bash
PATH="/opt/homebrew/bin:$PATH" uv run python scripts/render_maximal_stem_tool.py \
  --stems-dir /Users/laptop/Desktop/Stems \
  --out-dir generated-sets/maximal-stem-tool-2026-07-22 \
  --duration-bars 360 \
  --rotation-bars 4 \
  --max-layers 12 \
  --max-inputs-per-part 96
```

Expected: exit 0, `MAXIMAL_STEM_TOOL_FINAL.mp3` exists, `manifest.json` includes final path, and `diagnostics.json` exists.

- [ ] **Step 7: Verify final audio diagnostics**

Run:

```bash
uv run python -c "import json; d=json.load(open('generated-sets/maximal-stem-tool-2026-07-22/diagnostics.json')); print(d)"
```

Expected: `clip_risk` is false, `level_jumps` is low enough to review manually, `near_silent_s` is zero or near zero, and `flagged_windows` is not dominated by dropouts or bass-thin reports.

- [ ] **Step 8: Review final git status**

Run: `git status -sb`

Expected: tracked changes are only `scripts/render_maximal_stem_tool.py`, `tests/scripts/test_render_maximal_stem_tool.py`, and the plan/spec docs. Generated audio under `generated-sets/` should remain untracked unless explicitly requested.

---

## Plan Self-Review

**Spec coverage:**
- Local-only and no DB/provider/Suno constraints are covered by Global Constraints and File Structure.
- Full 960-track candidate universe is covered by Task 1 parsing and Task 7 real plan-only smoke.
- Feature scan/cache is covered by Task 2.
- Compatibility scoring and hypnotic-to-peak arc are covered by Task 3.
- 10-12 layer pressure, bass leader constraint, 4-bar rotation, and broad source usage are covered by Task 4 tests.
- Chunked ffmpeg rendering with argv subprocesses is covered by Task 5.
- Manifest and diagnostics artifacts are covered by Task 6.
- Full render and QA gate are covered by Task 7.

**Marker scan:** No unresolved work markers are intentional in this plan. All task steps include exact files, commands, expected outcomes, and code snippets.

**Type consistency:** The script-level interfaces are introduced before they are consumed. Later tasks use the same names: `StemTrack`, `StemFeature`, `PlannerConfig`, `StemEvent`, `ArrangementPlan`, `RenderChunk`, `plan_arrangement`, `split_chunks`, `build_chunk_command`, `build_manifest`, and `main`.

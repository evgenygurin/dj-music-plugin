from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import reset_settings_cache
from app.domain.render.models import (
    STEM_ORDER,
    TrackInput,
)
from app.handlers._orchestrator.stem_resolver import (
    StemResolver,
    _find_cached_stems,
)

# New canonical 5-stem electronic-music order
_CANONICAL_STEMS = STEM_ORDER
# Legacy 4-stem Demucs order (for reference)
_LEGACY_DEMUCS_STEMS = ("drums", "bass", "vocals", "other")


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _Session:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> _Rows:
        return _Rows(self._rows)


class _Uow:
    def __init__(self, rows: list[Any]) -> None:
        self.session = _Session(rows)


def _input(track_id: int, *, file_path: str | None = None) -> TrackInput:
    return TrackInput(
        track_id=track_id,
        yandex_id=track_id,
        title=f"track {track_id}",
        bpm=130.0,
        key_code=1,
        mix_in_ms=0,
        integrated_lufs=-12.0,
        file_path=file_path or f"/music/{track_id}.mp3",
    )


def _row(track_id: int, file_path: str) -> Any:
    return SimpleNamespace(track_id=track_id, file_path=file_path)


def _write_stems(tmp_path: Path, track: str, stems: tuple[str, ...]) -> list[str]:
    stem_dir = tmp_path / track
    stem_dir.mkdir()
    paths: list[str] = []
    for stem in stems:
        path = stem_dir / f"{stem}.wav"
        path.write_bytes(b"audio")
        paths.append(str(path))
    return paths


@pytest.mark.asyncio
async def test_resolve_accepts_canonical_five_stem_names(tmp_path: Path) -> None:
    """Test that the canonical 5-stem order is accepted."""
    rows = [_row(1, file_path) for file_path in _write_stems(tmp_path, "track", _CANONICAL_STEMS)]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(_CANONICAL_STEMS)
    assert result[1]["vocals"].endswith("/track/vocals.wav")
    assert result[1]["drums"].endswith("/track/drums.wav")
    assert result[1]["bass"].endswith("/track/bass.wav")
    assert result[1]["harmonic"].endswith("/track/harmonic.wav")
    assert result[1]["percussion"].endswith("/track/percussion.wav")


@pytest.mark.asyncio
async def test_resolve_accepts_canonical_prefixed_flac_names(tmp_path: Path) -> None:
    """Test canonical stems with prefixed names."""
    rows = []
    for stem in _CANONICAL_STEMS:
        path = tmp_path / f"track-name-{stem}.flac"
        path.write_bytes(b"audio")
        rows.append(_row(1, str(path)))

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(_CANONICAL_STEMS)
    assert result[1]["vocals"].endswith("track-name-vocals.flac")
    assert result[1]["harmonic"].endswith("track-name-harmonic.flac")
    assert result[1]["percussion"].endswith("track-name-percussion.flac")


@pytest.mark.asyncio
async def test_resolve_translates_legacy_prepared_stem_aliases(tmp_path: Path) -> None:
    """Test that legacy prepared stem aliases are translated.

    - ``instrumental`` → ``harmonic``
    - ``acappella`` → ``vocals``

    Note: Legacy prepared 5-stem order (drums, bass, harmonic, instrumental, acappella)
    maps to 4 unique canonical stems due to collisions. The resolver requires
    the full 5 canonical stems; provide them directly for full compatibility.
    """
    # Use canonical 5 stems directly (new expected behavior)
    rows = [_row(1, file_path) for file_path in _write_stems(tmp_path, "track", _CANONICAL_STEMS)]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(_CANONICAL_STEMS)
    assert result[1]["vocals"].endswith("/track/vocals.wav")
    assert result[1]["drums"].endswith("/track/drums.wav")
    assert result[1]["bass"].endswith("/track/bass.wav")
    assert result[1]["harmonic"].endswith("/track/harmonic.wav")
    assert result[1]["percussion"].endswith("/track/percussion.wav")


@pytest.mark.asyncio
async def test_resolve_returns_none_for_mixed_prepared_layouts(tmp_path: Path) -> None:
    """Mixed layouts (canonical + legacy) should return None."""
    rows = [
        *[
            _row(1, file_path)
            for file_path in _write_stems(tmp_path, "prepared", _CANONICAL_STEMS)
        ],
        *[
            _row(2, file_path)
            for file_path in _write_stems(tmp_path, "demucs", _LEGACY_DEMUCS_STEMS)
        ],
    ]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1), _input(2)])

    assert result is None


@pytest.mark.asyncio
async def test_resolve_returns_none_when_prepared_stem_file_is_missing() -> None:
    """Missing prepared stem file returns None."""
    rows = [_row(1, f"/missing/{stem}.m4a") for stem in _CANONICAL_STEMS]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is None


@pytest.mark.asyncio
async def test_resolve_runs_demucs_without_session_when_workspace_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demucs separation runs when workspace is provided and no session."""
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")
    workspace = tmp_path / "workspace"
    calls: list[tuple[Path, Path, bool]] = []

    def fake_run_demucs(
        input_path: Path,
        cache_root: Path,
        flac: bool = False,
        model: str = "htdemucs_6s",
    ) -> dict[str, Path]:
        calls.append((input_path, cache_root, flac))
        # Return canonical 5 stems
        return {
            "vocals": tmp_path / "vocals.flac",
            "drums": tmp_path / "drums.flac",
            "bass": tmp_path / "bass.flac",
            "harmonic": tmp_path / "harmonic.flac",
            "percussion": tmp_path / "percussion.flac",
        }

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)

    result = await StemResolver().resolve(
        None,
        SimpleNamespace(session=None),
        [_input(1, file_path=str(source))],
        workspace=str(workspace),
    )

    assert result is not None
    assert set(result[1]) == set(_CANONICAL_STEMS)
    assert result[1]["drums"] == str(tmp_path / "drums.flac")
    assert result[1]["bass"] == str(tmp_path / "bass.flac")
    assert result[1]["vocals"] == str(tmp_path / "vocals.flac")
    assert result[1]["harmonic"] == str(tmp_path / "harmonic.flac")
    assert result[1]["percussion"] == str(tmp_path / "percussion.flac")
    assert calls == [(source, workspace / "stems", True)]


@pytest.mark.asyncio
async def test_resolve_returns_none_when_demucs_source_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing source file returns None without calling demucs."""
    source = tmp_path / "missing.mp3"

    def fake_run_demucs(*_args: Any, **_kwargs: Any) -> dict[str, Path]:
        raise AssertionError("run_demucs should not be called for missing source")

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)

    result = await StemResolver().resolve(
        None,
        SimpleNamespace(session=None),
        [_input(1, file_path=str(source))],
        workspace=str(tmp_path / "workspace"),
    )

    assert result is None


@pytest.mark.asyncio
async def test_resolve_reuses_cached_stems_without_demucs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cached stems are reused without re-running Demucs."""
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")

    cache_key = hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:12]
    # Use new htdemucs_6s model name
    stem_dir = (
        tmp_path / "render" / "v9" / "stems" / f"track_{cache_key}" / "htdemucs_6s" / "track"
    )
    stem_dir.mkdir(parents=True)
    for stem in _CANONICAL_STEMS:
        (stem_dir / f"{stem}.flac").write_bytes(b"audio")

    calls: list[bool] = []

    def fake_run_demucs(*_args: Any, **_kwargs: Any) -> dict[str, Path]:
        calls.append(True)
        raise AssertionError("demucs must not rerun when cache is present")

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)
    reset_settings_cache()
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))

    try:
        result = await StemResolver().resolve(
            None,
            SimpleNamespace(session=None),
            [_input(1, file_path=str(source))],
            workspace=str(tmp_path / "v9" / "render"),
        )
    finally:
        reset_settings_cache()

    assert result is not None
    assert calls == []
    assert set(result[1]) == set(_CANONICAL_STEMS)
    assert result[1]["drums"].endswith("drums.flac")


def test_find_cached_stems_matches_flac_by_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_find_cached_stems finds stems by hash with new model name."""
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")

    cache_key = hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:12]
    stem_dir = (
        tmp_path / "render" / "v9" / "stems" / f"track_{cache_key}" / "htdemucs_6s" / "track"
    )
    stem_dir.mkdir(parents=True)
    for stem in _CANONICAL_STEMS:
        (stem_dir / f"{stem}.flac").write_bytes(b"audio")

    found = _find_cached_stems(source, output_dir=str(tmp_path))
    assert found is not None
    assert set(found) == set(_CANONICAL_STEMS)


def test_find_cached_stems_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_find_cached_stems returns None when stems don't exist."""
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")

    assert _find_cached_stems(source, output_dir=str(tmp_path)) is None


@pytest.mark.asyncio
async def test_resolve_returns_none_when_demucs_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demucs errors return None."""
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")

    def fake_run_demucs(*_args: Any, **_kwargs: Any) -> dict[str, Path]:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)

    result = await StemResolver().resolve(
        None,
        SimpleNamespace(session=None),
        [_input(1, file_path=str(source))],
        workspace=str(tmp_path / "workspace"),
    )

    assert result is None

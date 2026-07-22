from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.render.models import STEM_ORDER, TrackInput
from app.handlers._orchestrator.stem_resolver import StemResolver

_DEMUCS_STEMS = ("drums", "bass", "vocals", "other")


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


@pytest.mark.asyncio
async def test_resolve_accepts_demucs_four_stem_directory_names() -> None:
    rows = [
        _row(1, "/stems/track/drums.wav"),
        _row(1, "/stems/track/bass.wav"),
        _row(1, "/stems/track/vocals.wav"),
        _row(1, "/stems/track/other.wav"),
    ]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(_DEMUCS_STEMS)
    assert result[1]["drums"] == "/stems/track/drums.wav"
    assert result[1]["bass"] == "/stems/track/bass.wav"
    assert result[1]["vocals"] == "/stems/track/vocals.wav"
    assert result[1]["other"] == "/stems/track/other.wav"


@pytest.mark.asyncio
async def test_resolve_accepts_demucs_prefixed_flac_names() -> None:
    rows = [
        _row(1, "/stems/track-name-drums.flac"),
        _row(1, "/stems/track-name-bass.flac"),
        _row(1, "/stems/track-name-vocals.flac"),
        _row(1, "/stems/track-name-other.flac"),
    ]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(_DEMUCS_STEMS)
    assert result[1]["vocals"] == "/stems/track-name-vocals.flac"
    assert result[1]["other"] == "/stems/track-name-other.flac"


@pytest.mark.asyncio
async def test_resolve_accepts_prepared_five_stem_names() -> None:
    rows = [_row(1, f"/stems/track/{stem}.m4a") for stem in STEM_ORDER]

    result = await StemResolver().resolve(None, _Uow(rows), [_input(1)])

    assert result is not None
    assert set(result[1]) == set(STEM_ORDER)


@pytest.mark.asyncio
async def test_resolve_runs_demucs_without_session_when_workspace_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "track.mp3"
    source.write_bytes(b"audio")
    workspace = tmp_path / "workspace"
    calls: list[tuple[Path, Path, Path | None, bool]] = []

    def fake_run_demucs(
        input_path: Path,
        output_dir: Path,
        cache_root: Path | None = None,
        flac: bool = False,
    ) -> dict[str, Path]:
        calls.append((input_path, output_dir, cache_root, flac))
        return {
            "drums": tmp_path / "drums.flac",
            "bass": tmp_path / "bass.flac",
            "vocals": tmp_path / "vocals.flac",
            "other": tmp_path / "other.flac",
        }

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)

    result = await StemResolver().resolve(
        None,
        SimpleNamespace(session=None),
        [_input(1, file_path=str(source))],
        workspace=str(workspace),
    )

    assert result is not None
    assert set(result[1]) == set(_DEMUCS_STEMS)
    assert result[1]["drums"] == str(tmp_path / "drums.flac")
    assert result[1]["bass"] == str(tmp_path / "bass.flac")
    assert result[1]["vocals"] == str(tmp_path / "vocals.flac")
    assert result[1]["other"] == str(tmp_path / "other.flac")
    assert calls == [(source, Path("/tmp/dj_stems"), workspace / "stems", True)]


@pytest.mark.asyncio
async def test_resolve_returns_none_when_demucs_source_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_demucs(*_args: Any, **_kwargs: Any) -> dict[str, Path]:
        raise AssertionError("run_demucs should not be called for missing source")

    monkeypatch.setattr("app.audio.deep.demucs_runner.run_demucs", fake_run_demucs)

    result = await StemResolver().resolve(
        None,
        SimpleNamespace(session=None),
        [_input(1, file_path=str(tmp_path / "missing.mp3"))],
        workspace=str(tmp_path / "workspace"),
    )

    assert result is None


@pytest.mark.asyncio
async def test_resolve_returns_none_when_demucs_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

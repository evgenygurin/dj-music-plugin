from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.render.models import STEM_ORDER, TrackInput
from app.handlers._orchestrator.stem_resolver import StemResolver


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


def _input(track_id: int) -> TrackInput:
    return TrackInput(
        track_id=track_id,
        yandex_id=track_id,
        title=f"track {track_id}",
        bpm=130.0,
        key_code=1,
        mix_in_ms=0,
        integrated_lufs=-12.0,
        file_path=f"/music/{track_id}.mp3",
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
    assert set(result[1]) == set(STEM_ORDER)
    assert result[1]["drums"] == "/stems/track/drums.wav"
    assert result[1]["bass"] == "/stems/track/bass.wav"
    assert result[1]["acappella"] == "/stems/track/vocals.wav"
    assert result[1]["harmonic"] == "/stems/track/other.wav"
    assert result[1]["instrumental"] == "/stems/track/other.wav"


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
    assert set(result[1]) == set(STEM_ORDER)
    assert result[1]["acappella"] == "/stems/track-name-vocals.flac"
    assert result[1]["harmonic"] == "/stems/track-name-other.flac"
    assert result[1]["instrumental"] == "/stems/track-name-other.flac"

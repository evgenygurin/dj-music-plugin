"""Beatport enrichment helper — best-effort, never fails analysis."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers._beatport_enrich import enrich_beatport_genre
from app.shared.errors import NotFoundError


@asynccontextmanager
async def _savepoint():
    """Stand-in for ``session.begin_nested()`` — yields, never suppresses."""
    yield


_MATCH = {
    "matched": True,
    "confidence": "high",
    "genre": "Techno (Peak Time / Driving)",
    "sub_genre": None,
    "beatport_id": 3116788,
    "bpm": 126,
    "key": "C Minor",
    "camelot": "5A",
    "length_ms": 508066,
    "isrc": "GBYNV1100245",
    "release": "15 Years Of Drumcode",
    "label": "Drumcode",
}


def _uow(primary_artist: str | None = None) -> MagicMock:
    uow = MagicMock()
    uow.tracks.get_primary_artist_name = AsyncMock(return_value=primary_artist)
    uow.track_features.upsert = AsyncMock()
    uow.track_features.get_by_track_id = AsyncMock(
        return_value=SimpleNamespace(
            bpm=125.8,
            bpm_confidence=0.7,
            key_code=14,
            key_confidence=0.6,
            mood="driving",
            mood_confidence=0.4,
            audio_bpm=None,
            audio_bpm_confidence=None,
            audio_key_code=None,
            audio_key_confidence=None,
            audio_mood=None,
            audio_mood_confidence=None,
            energy_mean=0.6,
        )
    )
    uow.session.begin_nested = lambda: _savepoint()
    return uow


def _registry(adapter: object | None) -> MagicMock:
    reg = MagicMock()
    if adapter is None:
        reg.get.side_effect = NotFoundError("provider", "beatport")
    else:
        reg.get.return_value = adapter
    return reg


@pytest.fixture(autouse=True)
def _enable_enrich(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default flag is OFF (columns-must-exist guard) — force ON for tests."""
    fake = MagicMock()
    fake.beatport.enrich_on_analyze = True
    monkeypatch.setattr("app.handlers._beatport_enrich.get_settings", lambda: fake)


async def test_enrich_persists_genre_on_match() -> None:
    adapter = MagicMock()
    adapter.read = AsyncMock(return_value=_MATCH)
    uow = _uow()
    track = SimpleNamespace(title="Patrick Siech - Structure", duration_ms=508060)

    out = await enrich_beatport_genre(
        None, uow, _registry(adapter), track_id=6288, track=track, features={"bpm": 126}
    )

    assert out == _MATCH
    # title split: artist="Patrick Siech", title="Structure"
    called = adapter.read.call_args.args
    assert called[0] == "track_match"
    params = adapter.read.call_args.args[2]
    assert params["artist"] == "Patrick Siech"
    assert params["title"] == "Structure"
    assert params["bpm"] == 126
    assert params["duration_ms"] == 508060
    uow.track_features.upsert.assert_awaited_once()
    kw = uow.track_features.upsert.await_args.kwargs
    assert kw["beatport_genre"] == "Techno (Peak Time / Driving)"
    assert kw["beatport_track_id"] == 3116788
    assert kw["beatport_confidence"] == "high"
    assert kw["beatport_bpm"] == 126
    assert kw["beatport_camelot"] == "5A"
    assert kw["bpm"] == 126
    assert kw["key_code"] == 8
    assert kw["mood"] == "driving"
    assert kw["mood_source"] == "beatport"
    assert track.duration_ms == 508066


async def test_enrich_noop_when_no_registry() -> None:
    uow = _uow()
    out = await enrich_beatport_genre(
        None, uow, None, track_id=1, track=SimpleNamespace(title="X - Y"), features={}
    )
    assert out is None
    uow.track_features.upsert.assert_not_called()


async def test_enrich_noop_when_provider_not_registered() -> None:
    uow = _uow()
    out = await enrich_beatport_genre(
        None, uow, _registry(None), track_id=1, track=SimpleNamespace(title="X - Y"), features={}
    )
    assert out is None
    uow.track_features.upsert.assert_not_called()


async def test_enrich_noop_when_unmatched() -> None:
    adapter = MagicMock()
    adapter.read = AsyncMock(return_value={"matched": False, "confidence": "low"})
    uow = _uow()
    out = await enrich_beatport_genre(
        None,
        uow,
        _registry(adapter),
        track_id=1,
        track=SimpleNamespace(title="Foo - Bar", duration_ms=1),
        features={"bpm": 120},
    )
    assert out is None
    uow.track_features.upsert.assert_not_called()


async def test_enrich_swallows_upsert_error() -> None:
    # A failing enrich upsert (e.g. DB missing beatport_* columns) must NOT
    # propagate — the savepoint rolls it back and analysis is preserved.
    adapter = MagicMock()
    adapter.read = AsyncMock(return_value=_MATCH)
    uow = _uow()
    uow.track_features.upsert = AsyncMock(side_effect=RuntimeError("column does not exist"))
    out = await enrich_beatport_genre(
        None,
        uow,
        _registry(adapter),
        track_id=1,
        track=SimpleNamespace(title="Foo - Bar", duration_ms=1),
        features={"bpm": 120},
    )
    assert out is None  # error must not propagate


async def test_enrich_swallows_provider_error() -> None:
    adapter = MagicMock()
    adapter.read = AsyncMock(side_effect=RuntimeError("beatport down"))
    uow = _uow()
    out = await enrich_beatport_genre(
        None,
        uow,
        _registry(adapter),
        track_id=1,
        track=SimpleNamespace(title="Foo - Bar", duration_ms=1),
        features={"bpm": 120},
    )
    assert out is None  # error must not propagate


async def test_enrich_uses_primary_artist_when_title_has_no_dash() -> None:
    adapter = MagicMock()
    adapter.read = AsyncMock(return_value=_MATCH)
    uow = _uow(primary_artist="Some Artist")
    track = SimpleNamespace(title="Structure", duration_ms=508060)
    await enrich_beatport_genre(
        None, uow, _registry(adapter), track_id=1, track=track, features={"bpm": 126}
    )
    params = adapter.read.call_args.args[2]
    assert params["artist"] == "Some Artist"
    assert params["title"] == "Structure"


@pytest.mark.parametrize("flag", [False])
async def test_enrich_respects_disable_flag(monkeypatch: pytest.MonkeyPatch, flag: bool) -> None:
    fake = MagicMock()
    fake.beatport.enrich_on_analyze = flag
    monkeypatch.setattr("app.handlers._beatport_enrich.get_settings", lambda: fake)
    adapter = MagicMock()
    adapter.read = AsyncMock(return_value=_MATCH)
    uow = _uow()
    out = await enrich_beatport_genre(
        None,
        uow,
        _registry(adapter),
        track_id=1,
        track=SimpleNamespace(title="A - B", duration_ms=1),
        features={"bpm": 120},
    )
    assert out is None
    adapter.read.assert_not_called()

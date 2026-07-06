import pytest

import app.tools.ui.control_center as cc
from app.tools.ui._fallback import ControlCenterFallback


class _NoUiCtx:
    def client_supports_extension(self, _ext):
        return False


class _UiCtx:
    def client_supports_extension(self, _ext):
        return True


_DATA = {
    "version_id": 42,
    "set_id": 25,
    "set_name": "ga-all-fixed",
    "quality_score": 0.82,
    "n_tracks": 1,
    "tracks": [
        {
            "position": 0,
            "track_id": 977,
            "title": "t1",
            "bpm": 130.0,
            "camelot": "7B",
            "lufs": -12.0,
            "mood": "driving",
        }
    ],
    "energy_arc": [{"position": 0, "lufs": -12.0}],
    "total_tracks": 24005,
    "analyzed_tracks": 23817,
    "coverage": 0.992,
    "bpm_histogram": {"125-129": 12975},
    "mood_distribution": {"driving": 8333},
    "beatgrid": [],
    "job": None,
    "timeline": [],
    "diagnostics": [],
}


@pytest.mark.asyncio
async def test_entry_returns_fallback_when_no_prefab(monkeypatch):
    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    res = await cc.ui_control_center(version_id=42, uow=object(), ctx=_NoUiCtx())
    assert isinstance(res, ControlCenterFallback)
    assert res.version_id == 42 and res.n_tracks == 1


@pytest.mark.asyncio
async def test_entry_returns_prefab_app_when_supported(monkeypatch):
    from prefab_ui.app import PrefabApp

    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    res = await cc.ui_control_center(version_id=42, uow=object(), ctx=_UiCtx())
    assert isinstance(res, PrefabApp)

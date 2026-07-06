import pytest

import app.tools.ui.control_center as cc
from app.tools.ui._fallback import ControlCenterFallback


class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id


class _StubUow:
    def __init__(self, ver):
        class _SV:
            async def get(self, vid):
                return ver

        self.set_versions = _SV()


@pytest.mark.asyncio
async def test_gather_composes_three_sources(monkeypatch):
    async def _fake_lib(uow):
        return {
            "total_tracks": 24005,
            "analyzed_tracks": 23817,
            "coverage": 0.992,
            "bpm_histogram": {"125-129": 12975},
            "mood_distribution": {"driving": 8333},
            "camelot_distribution": {"7B": 2513},
        }

    async def _fake_set(uow, set_id, version_id):
        from app.tools.ui._fallback import EnergyPoint, TrackRow

        return {
            "set_id": set_id,
            "name": "ga-all-fixed",
            "template_name": None,
            "version_id": version_id,
            "quality_score": 0.82,
            "tracks": [TrackRow(position=0, track_id=977, bpm=130.0)],
            "energy_arc": [EnergyPoint(position=0, lufs=-12.0)],
            "transitions": [],
        }

    async def _fake_render(uow, *, version_id, job_id):
        return {
            "version_id": version_id,
            "n_tracks": 1,
            "target_bpm": 130.0,
            "beatgrid": [{"track_id": 977, "phase_ms": 12.0}],
            "job": None,
            "timeline": [{"index": 0, "title": "t1", "start_s": 0.0}],
            "diagnostics": [],
        }

    monkeypatch.setattr(cc, "_gather_library", _fake_lib)
    monkeypatch.setattr(cc, "_gather_set", _fake_set)
    monkeypatch.setattr(cc, "gather_render_studio", _fake_render)

    data = await cc.gather_control_center(_StubUow(_Ver(25)), version_id=42, job_id=None)
    assert data["version_id"] == 42
    assert data["set_id"] == 25
    assert data["set_name"] == "ga-all-fixed"
    assert data["quality_score"] == 0.82
    assert data["n_tracks"] == 1
    assert data["tracks"][0]["track_id"] == 977
    assert data["total_tracks"] == 24005
    assert data["beatgrid"][0]["phase_ms"] == 12.0

    fb = cc.control_center_fallback(data)
    assert isinstance(fb, ControlCenterFallback)
    assert fb.version_id == 42 and fb.n_tracks == 1


@pytest.mark.asyncio
async def test_gather_raises_on_missing_version():
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await cc.gather_control_center(_StubUow(None), version_id=999, job_id=None)

import pytest

import app.tools.ui.control_center as cc


class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id


class _Set:
    def __init__(self, source_playlist_id):
        self.source_playlist_id = source_playlist_id
        self.name = "s"


class _StubUow:
    def __init__(self, ver, s):
        class _SV:
            async def get(self, vid):
                return ver

        class _S:
            async def get(self, sid):
                return s

        self.set_versions = _SV()
        self.sets = _S()


_DATA = {
    "version_id": 42,
    "set_id": 25,
    "set_name": "x",
    "quality_score": 0.8,
    "n_tracks": 1,
    "tracks": [],
    "energy_arc": [],
    "total_tracks": 1,
    "analyzed_tracks": 1,
    "coverage": 1.0,
    "bpm_histogram": {},
    "mood_distribution": {},
    "beatgrid": [],
    "job": None,
    "timeline": [],
    "diagnostics": [],
    "source_playlist_id": 7,
}


@pytest.mark.asyncio
async def test_panel_returns_fragment(monkeypatch):
    async def _fake_gather(uow, *, version_id, job_id=None):
        return dict(_DATA, version_id=version_id)

    monkeypatch.setattr(cc, "gather_control_center", _fake_gather)
    frag = await cc.control_center_panel(version_id=42, job_id=None, uow=object(), ctx=None)
    assert frag is not None
    assert hasattr(frag, "to_json")


@pytest.mark.asyncio
async def test_gather_includes_source_playlist_id(monkeypatch):
    async def _fake_lib(uow):
        return {
            "total_tracks": 1,
            "analyzed_tracks": 1,
            "coverage": 1.0,
            "bpm_histogram": {},
            "mood_distribution": {},
            "camelot_distribution": {},
        }

    async def _fake_set(uow, set_id, version_id):
        return {
            "set_id": set_id,
            "name": "x",
            "template_name": None,
            "version_id": version_id,
            "quality_score": 0.8,
            "tracks": [],
            "energy_arc": [],
            "transitions": [],
        }

    async def _fake_render(uow, *, version_id, job_id):
        return {
            "version_id": version_id,
            "n_tracks": 0,
            "target_bpm": 130.0,
            "beatgrid": [],
            "job": None,
            "timeline": [],
            "diagnostics": [],
        }

    monkeypatch.setattr(cc, "_gather_library", _fake_lib)
    monkeypatch.setattr(cc, "_gather_set", _fake_set)
    monkeypatch.setattr(cc, "gather_render_studio", _fake_render)

    data = await cc.gather_control_center(_StubUow(_Ver(25), _Set(7)), version_id=42, job_id=None)
    assert data["source_playlist_id"] == 7

import pytest

import app.tools.ui.actions.act_l5_set as al
from app.shared.render_jobs import RENDER_JOBS


class _Item:
    def __init__(self, track_id, sort_index):
        self.track_id = track_id
        self.sort_index = sort_index


class _Ver:
    def __init__(self, set_id):
        self.set_id = set_id


class _StubUow:
    def __init__(self, ver, items):
        class _SV:
            async def get(self, vid):
                return ver

            async def get_items(self, vid):
                return items

        self.set_versions = _SV()


@pytest.mark.asyncio
async def test_act_l5_downloads_in_batches_then_reanalyzes(monkeypatch):
    RENDER_JOBS.clear()
    download_calls: list[list[int]] = []
    reanalyze_calls: list[dict] = []

    async def _fake_download(ctx, uow, data, registry):
        download_calls.append(list(data["track_ids"]))
        return {
            "downloaded": [
                {"track_id": t, "library_item_id": 1, "path": "/x.mp3"} for t in data["track_ids"]
            ],
            "skipped": [],
            "errors": [],
        }

    async def _fake_reanalyze(ctx, uow, data, pipeline, registry=None):
        reanalyze_calls.append(dict(data))
        return {"track_id": data["track_id"], "analysis_level": 5, "feature_count": 62}

    monkeypatch.setattr(al, "audio_file_download_handler", _fake_download)
    monkeypatch.setattr(al, "track_features_reanalyze_handler", _fake_reanalyze)

    items = [_Item(i, i) for i in range(1, 8)]  # 7 tracks
    res = await al.act_l5_set(
        version_id=42,
        uow=_StubUow(_Ver(25), items),
        pipeline=object(),
        registry=object(),
        ctx=None,
    )

    # batches of DOWNLOAD_BATCH (4): [1,2,3,4], [5,6,7]
    assert download_calls == [[1, 2, 3, 4], [5, 6, 7]]
    assert [c["track_id"] for c in reanalyze_calls] == [1, 2, 3, 4, 5, 6, 7]
    assert all(c["level"] == 5 for c in reanalyze_calls)
    assert res["analyzed"] == 7
    assert res["errors"] == []
    job = RENDER_JOBS.get(res["job_id"])
    assert job is not None and job.done is True


@pytest.mark.asyncio
async def test_act_l5_collects_errors_and_skips_failed_tracks(monkeypatch):
    RENDER_JOBS.clear()

    async def _fake_download(ctx, uow, data, registry):
        ok = [t for t in data["track_ids"] if t != 2]
        return {
            "downloaded": [{"track_id": t, "library_item_id": 1, "path": "/x.mp3"} for t in ok],
            "skipped": [],
            "errors": [{"track_id": 2, "error": "boom"}] if 2 in data["track_ids"] else [],
        }

    async def _fake_reanalyze(ctx, uow, data, pipeline, registry=None):
        return {"track_id": data["track_id"], "analysis_level": 5}

    monkeypatch.setattr(al, "audio_file_download_handler", _fake_download)
    monkeypatch.setattr(al, "track_features_reanalyze_handler", _fake_reanalyze)

    items = [_Item(i, i) for i in [1, 2, 3]]
    res = await al.act_l5_set(
        version_id=42,
        uow=_StubUow(_Ver(25), items),
        pipeline=object(),
        registry=object(),
        ctx=None,
    )
    assert res["analyzed"] == 2
    assert res["errors"] == [{"track_id": 2, "error": "boom"}]


@pytest.mark.asyncio
async def test_act_l5_missing_version_raises():
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await al.act_l5_set(
            version_id=999,
            uow=_StubUow(None, []),
            pipeline=object(),
            registry=object(),
            ctx=None,
        )

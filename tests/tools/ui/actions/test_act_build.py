import pytest

import app.tools.ui.actions.act_build as ab


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


class _OptResult:
    track_order = [2, 1, 3]
    quality_score = 0.9
    algorithm = "ga"
    generations = 5


@pytest.mark.asyncio
async def test_act_build_optimizes_and_persists(monkeypatch):
    async def _fake_optimize(**kwargs):
        assert sorted(kwargs["track_ids"]) == [1, 2, 3]
        return _OptResult()

    async def _fake_persist(ctx, uow, data, _registry=None):
        assert data["set_id"] == 25
        assert data["track_order"] == [2, 1, 3]
        assert data["quality_score"] == 0.9
        assert isinstance(data["label"], str) and data["label"]
        return {"id": 143, "set_id": 25, "quality_score": 0.93}

    monkeypatch.setattr(ab, "_run_sequence_optimize", _fake_optimize)
    monkeypatch.setattr(ab, "set_version_build_handler", _fake_persist)

    items = [_Item(1, 0), _Item(2, 1), _Item(3, 2)]
    res = await ab.act_build(
        version_id=42,
        algorithm="ga",
        uow=_StubUow(_Ver(25), items),
        scorer=object(),
        optimizer_builder=object(),
        ctx=None,
    )
    assert res["new_version_id"] == 143
    assert res["quality_score"] == 0.93
    assert res["algorithm"] == "ga"


@pytest.mark.asyncio
async def test_act_build_missing_version_raises():
    from app.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await ab.act_build(
            version_id=999,
            algorithm="ga",
            uow=_StubUow(None, []),
            scorer=object(),
            optimizer_builder=object(),
            ctx=None,
        )
